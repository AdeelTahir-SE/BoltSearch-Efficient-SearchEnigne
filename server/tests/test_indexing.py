import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rag'))
from store import Store
from embeddings import Embeddings, TransientEmbeddingError
from indexing import build_index, indexing_lock
from unittest.mock import patch
from urllib.error import HTTPError, URLError


class LocalModel:
    configured, provider, space = True, 'ollama', 'retry-fixture'
    def __init__(self, failures):
        self.failures = list(failures)
        self.batch_sizes = []
    def embed(self, texts):
        self.batch_sizes.append(len(texts))
        if self.failures:
            error = self.failures.pop(0)
            if error:
                raise error
        return [[1.0, 0.0] for _ in texts]


class IndexingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.path = Path(self.temp.name) / 'index.sqlite3'
        self.store = Store(self.path)
        self.store.ingest([{'id': index, 'Title': f'Document {index}', 'Body': f'Distinct passage number {index}.'} for index in range(4)])
    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_timeout_retries_smaller_batches_and_completes_without_losing_vectors(self):
        model = LocalModel([TransientEmbeddingError('timeout'), TransientEmbeddingError('timeout')])
        waits, events = [], []
        result = build_index(self.store, model, sleep=waits.append, on_event=events.append)
        self.assertEqual(model.batch_sizes[:3], [4, 2, 1])
        self.assertEqual(waits, [2, 4])
        self.assertEqual(result['pendingChunks'], 0)
        self.assertEqual(result['embeddedChunks'], 4)
        self.assertEqual(events[-1]['phase'], 'complete')

    def test_committed_vectors_survive_exhaustion_and_next_run_resumes(self):
        # First request saves all four; extend corpus so a later call can fail.
        first = LocalModel([])
        build_index(self.store, first, sleep=lambda _: None)
        self.store.ingest([{'id': 8, 'Title': 'Additional', 'Body': 'New passage.'}])
        failing = LocalModel([TransientEmbeddingError('offline')] * 3)
        with self.assertRaises(TransientEmbeddingError):
            build_index(self.store, failing, max_attempts=3, sleep=lambda _: None)
        self.assertEqual(self.store.status(failing.space)['embeddedChunks'], 4)
        resumed = LocalModel([])
        result = build_index(self.store, resumed, sleep=lambda _: None)
        self.assertEqual(result['embedded'], 1)
        self.assertEqual(result['pendingChunks'], 0)

    def test_configuration_and_invalid_vector_errors_fail_without_retries(self):
        model = LocalModel([ValueError('invalid model')])
        waits = []
        with self.assertRaises(ValueError):
            build_index(self.store, model, sleep=waits.append)
        self.assertEqual(waits, [])
        self.assertEqual(len(model.batch_sizes), 1)
        self.assertEqual(self.store.status(model.space)['embeddedChunks'], 0)

    def test_database_lock_prevents_duplicate_workers_and_releases_on_exception(self):
        with self.assertRaisesRegex(RuntimeError, 'simulated'):
            with indexing_lock(self.path):
                with self.assertRaisesRegex(ValueError, 'already owns'):
                    with indexing_lock(self.path):
                        pass
                raise RuntimeError('simulated')
        with indexing_lock(self.path):
            pass

    def test_transport_distinguishes_temporary_errors_from_bad_credentials(self):
        model = Embeddings({'EMBEDDING_API_KEY': 'fake', 'EMBEDDING_BASE_URL': 'https://example.test/v1', 'EMBEDDING_MODEL': 'fake'})
        for error in [URLError('offline'), TimeoutError(), HTTPError('https://example.test', 503, 'busy', {}, None), HTTPError('https://example.test', 429, 'rate limit', {}, None)]:
            with patch('urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(TransientEmbeddingError):
                    model.embed(['text'])
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect = HTTPError('https://example.test', 401, 'bad key', {}, None)
            with self.assertRaises(ValueError) as caught:
                model.embed(['text'])
            self.assertNotIsInstance(caught.exception, TransientEmbeddingError)

    def test_malformed_provider_json_is_retryable(self):
        model = Embeddings({'EMBEDDING_API_KEY': 'fake', 'EMBEDDING_BASE_URL': 'https://example.test/v1', 'EMBEDDING_MODEL': 'fake'})
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{"data":['
            with self.assertRaises(TransientEmbeddingError):
                model.embed(['text'])


if __name__ == '__main__':
    unittest.main()
