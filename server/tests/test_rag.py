import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rag'))
from store import Store, chunks, fuse, normalize, plain_text
from embeddings import Embeddings
from worker import retrieve, embed_batch
from import_archive import import_archive
import zipfile


class FakeEmbeddings:
    configured, space, model = True, 'test-space', 'fake-model'
    def __init__(self):
        self.calls = []
    def embed(self, texts, query=False):
        self.calls.append((texts, query))
        return [[1, 0] if ('automobile' in text or 'car' in text) else [0, 1] for text in texts]


class RagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.store = Store(Path(self.temp.name) / 'rag.sqlite3')
        self.embedding = FakeEmbeddings()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def ingest(self):
        return self.store.ingest([
            {'id': 1, 'Title': 'Vehicle care', 'Body': '<p>Maintain your automobile engine.</p>', 'Answer': 'Check the oil.'},
            {'id': 2, 'Title': 'Gardening', 'Body': 'Water the flowers.'},
        ])

    def test_bm25_covers_body_answers_and_safe_query_syntax(self):
        self.ingest()
        self.assertTrue(self.store.lexical('engine'))
        self.assertTrue(self.store.lexical('oil'))
        self.assertEqual(self.store.lexical('" OR -- *'), [])
        self.assertEqual(self.store.lexical('unfindableword'), [])

    def test_semantic_synonym_is_found_without_lexical_match(self):
        self.ingest()
        self.assertFalse(self.store.lexical('car'))
        embed_batch(self.store, self.embedding)
        result = retrieve(self.store, self.embedding, 'car')
        self.assertEqual(result['retrieval']['mode'], 'hybrid')
        self.assertEqual(result['sources'][0]['documentId'], 1)
        self.assertEqual(result['sources'][0]['methods'], ['semantic'])

    def test_vectorized_cosine_matches_scalar_ranking_across_batches(self):
        import random
        rng = random.Random(42)
        self.store.ingest([{'id': i, 'Title': f'Entry {i}', 'Body': f'Unique passage {i}.'} for i in range(300)])
        rows = self.store.missing('parity-space', 400)
        vectors = [[rng.uniform(-1, 1) for _ in range(16)] for _ in rows]
        self.store.save_vectors('parity-space', [row['text_hash'] for row in rows], vectors)
        query = vectors[0]
        fast = self.store.semantic('parity-space', query, limit=40, minimum=0.1)
        with patch.dict(sys.modules, {'numpy': None}):
            scalar = self.store.semantic('parity-space', query, limit=40, minimum=0.1)
        self.assertEqual(fast, scalar)
        self.assertTrue(fast)

    def test_search_paginates_unique_documents_without_embedding_calls(self):
        self.store.ingest([{'id': i, 'Title': 'Pagination example', 'Body': ('matching text ' * 150) + str(i)} for i in range(7)])
        pages = [self.store.search_documents('matching', limit=3, page=page) for page in (1, 2, 3, 4)]
        ids = [doc['Id'] for page in pages for doc in page['documents']]
        self.assertEqual(len(ids), 7)
        self.assertEqual(len(set(ids)), 7)
        self.assertEqual([page['hasMore'] for page in pages], [True, True, False, False])
        self.assertEqual(self.store.search_documents('unfindable')['documents'], [])
        self.assertEqual(self.store.search_documents('" OR -- *')['documents'], [])

    def test_rrf_rewards_agreement_and_is_deterministic(self):
        ranking = fuse([1, 2], [3, 2])
        self.assertEqual(ranking[0][0], 2)
        self.assertEqual(ranking[0][2], ['bm25', 'semantic'])

    def test_ablation_modes_do_not_silently_mix_retrievers(self):
        self.ingest()
        embed_batch(self.store, self.embedding)
        calls = len(self.embedding.calls)
        lexical = retrieve(self.store, self.embedding, 'engine', mode='bm25')
        self.assertEqual(lexical['retrieval']['mode'], 'bm25')
        self.assertEqual(len(self.embedding.calls), calls)
        semantic = retrieve(self.store, self.embedding, 'car', mode='semantic')
        self.assertEqual(semantic['retrieval']['mode'], 'semantic')
        self.assertTrue(all(source['methods'] == ['semantic'] for source in semantic['sources']))
        with self.assertRaises(ValueError):
            retrieve(self.store, Embeddings({}), 'car', mode='semantic')

    def test_ingestion_rolls_back_entire_batch_on_invalid_document(self):
        with self.assertRaises(ValueError):
            self.store.ingest([{'id': 1, 'Title': 'Valid'}, {'id': -1, 'Title': 'Invalid'}])
        self.assertEqual(self.store.status('')['documents'], 0)
        self.assertFalse(self.store.lexical('Valid'))

    def test_updates_remove_stale_chunks_and_reuse_unchanged_embeddings(self):
        self.ingest()
        embed_batch(self.store, self.embedding)
        calls = len(self.embedding.calls)
        self.assertEqual(self.ingest()['skipped'], 2)
        embed_batch(self.store, self.embedding)
        self.assertEqual(len(self.embedding.calls), calls)
        self.store.ingest([{'id': 1, 'Title': 'New topic', 'Body': 'Completely changed.'}])
        self.assertFalse(self.store.lexical('engine'))
        self.assertGreater(self.store.status(self.embedding.space)['pendingChunks'], 0)

    def test_model_spaces_and_dimensions_do_not_mix(self):
        self.ingest()
        row = self.store.missing('space-a')[0]
        self.store.save_vectors('space-a', [row['text_hash']], [[1, 0]])
        self.assertEqual(self.store.status('space-b')['embeddedChunks'], 0)
        with self.assertRaises(ValueError):
            self.store.save_vectors('space-a', ['other'], [[1, 0, 0]])
        with self.assertRaises(ValueError):
            self.store.semantic('space-a', [1, 0, 0])
        for vector in [[0, 0], [math.nan, 1], [True, 1], []]:
            with self.assertRaises(ValueError):
                normalize(vector)

    def test_provider_failure_is_visible_keyword_fallback(self):
        self.ingest()
        embed_batch(self.store, self.embedding)
        class Broken(FakeEmbeddings):
            def embed(self, texts, query=False):
                raise ValueError('Provider unavailable')
        result = retrieve(self.store, Broken(), 'engine')
        self.assertEqual(result['retrieval']['mode'], 'bm25')
        self.assertIn('Provider unavailable', result['retrieval']['warnings'])
        self.assertTrue(result['sources'])

    def test_unconfigured_embeddings_are_explicit(self):
        self.ingest()
        result = retrieve(self.store, Embeddings({}), 'engine')
        self.assertEqual(result['retrieval']['mode'], 'bm25')
        self.assertTrue(result['retrieval']['warnings'])

    def test_query_vectors_are_cached_and_namespaced(self):
        self.ingest()
        embed_batch(self.store, self.embedding)
        retrieve(self.store, self.embedding, 'car')
        calls = len(self.embedding.calls)
        retrieve(self.store, self.embedding, 'car')
        self.assertEqual(len(self.embedding.calls), calls)
        self.assertIsNone(self.store.cached_query('another-model', 'car'))

    def test_embedding_transport_prefixes_order_and_response_validation(self):
        client = Embeddings({'EMBEDDING_API_KEY': 'fake', 'EMBEDDING_BASE_URL': 'http://localhost:1234/v1', 'EMBEDDING_MODEL': 'embed', 'EMBEDDING_QUERY_PREFIX': 'query: ', 'EMBEDDING_DOCUMENT_PREFIX': 'passage: '})
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = io.BytesIO(json.dumps({'data': [{'index': 1, 'embedding': [0, 2]}, {'index': 0, 'embedding': [2, 0]}]}).encode())
            self.assertEqual(client.embed(['a', 'b']), [[1, 0], [0, 1]])
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(json.loads(request.data)['input'], ['passage: a', 'passage: b'])
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = io.BytesIO(json.dumps({'data': [{'index': 0, 'embedding': [2, 0]}]}).encode())
            client.embed(['question'], query=True)
            self.assertEqual(json.loads(opener.return_value.open.call_args.args[0].data)['input'], ['query: question'])
        for response in [[], {'data': {}}, {'data': ['bad']}, {'data': [{'index': 9, 'embedding': [1]}]}, {'data': [{'index': 0, 'embedding': [0, 0]}]}]:
            with patch('urllib.request.build_opener') as opener:
                opener.return_value.open.return_value = io.BytesIO(json.dumps(response).encode())
                with self.assertRaises(ValueError):
                    client.embed(['question'])

    def test_local_ollama_has_no_cloud_key_and_uses_native_batch_endpoint(self):
        client = Embeddings({'EMBEDDING_PROVIDER': 'ollama', 'EMBEDDING_MODEL': 'nomic-embed-text', 'FIREWORKS_API_KEY': 'never-forward-this'})
        self.assertTrue(client.configured)
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = io.BytesIO(json.dumps({'embeddings': [[2, 0], [0, 2]]}).encode())
            self.assertEqual(client.embed(['a', 'b']), [[1, 0], [0, 1]])
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, 'http://127.0.0.1:11434/api/embed')
            self.assertNotIn('Authorization', request.headers)
            self.assertFalse(json.loads(request.data)['truncate'])
        remote = Embeddings({'EMBEDDING_PROVIDER': 'ollama', 'EMBEDDING_MODEL': 'nomic', 'EMBEDDING_BASE_URL': 'https://cloud.example'})
        with self.assertRaisesRegex(ValueError, 'loopback'):
            remote.embed(['private text'])

    def test_archive_import_maps_tags_and_keeps_validation_out(self):
        archive = Path(self.temp.name) / 'archive.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('train.csv', 'Id,Title,Body,Tags,Y\n1,Training question,Question text,<python>,HQ\n')
            output.writestr('valid.csv', 'Id,Title,Body,Tags,Y\n2,Validation question,Holdout text,<java>,HQ\n')
        result = import_archive(self.store, archive)
        self.assertEqual(result['indexed'], 1)
        self.assertEqual(self.store.document(1)['Tag'], '<python>')
        self.assertEqual(self.store.document(1)['Answer'], '')
        self.assertIsNone(self.store.document(2))
        self.assertEqual(import_archive(self.store, archive)['skipped'], 1)

    def test_chunk_bounds_and_html_extraction(self):
        text = 'example text ' * 500
        result = list(chunks(text))
        self.assertGreater(len(result), 1)
        self.assertEqual(result[0][1], 0)
        self.assertEqual(result[-1][2], len(text))
        for part, start, end in result:
            self.assertEqual(part, text[start:end])
            self.assertLessEqual(len(part), 1200)
        self.assertEqual(plain_text('<p>Hello &amp; world</p><script>steal()</script><style>bad</style>'), 'Hello & world')

    def test_reopening_database_preserves_index(self):
        self.ingest()
        other = Store(Path(self.temp.name) / 'rag.sqlite3')
        try:
            self.assertTrue(other.lexical('engine'))
            self.assertEqual(other.document(1)['Title'], 'Vehicle care')
        finally:
            other.close()


if __name__ == '__main__':
    unittest.main()
