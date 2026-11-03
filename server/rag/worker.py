"""JSON stdin/stdout bridge used by Express and the local administration CLI."""
import csv
import json
import math
import os
import sys
from pathlib import Path
from embeddings import Embeddings
from store import open_store, fuse
from import_archive import import_archive
from indexing import build_index, indexing_lock
from query_parser import parse_query

ROOT = Path(__file__).resolve().parents[1]
csv.field_size_limit(16 * 1024 * 1024)


def retrieve(store, embedding, query, limit=8, mode='hybrid', query_parsing='off'):
    if mode not in ('bm25', 'semantic', 'hybrid'):
        raise ValueError('Retrieval mode must be bm25, semantic or hybrid.')
    if query_parsing not in ('off', 'on'):
        raise ValueError('Query parsing must be off or on.')
    parsed = parse_query(query) if query_parsing == 'on' else None
    warnings = []
    status = store.status(embedding.space)
    vector = None
    if mode != 'bm25' and embedding.configured and status['embeddedChunks']:
        try:
            vector = store.cached_query(embedding.space, query)
            if vector is None:
                vector = embedding.embed([query], query=True)[0]
                store.cache_query(embedding.space, query, vector)
        except (ValueError, KeyError, TypeError) as error:
            warnings.append(str(error))
    elif mode != 'bm25' and not embedding.configured:
        warnings.append('Semantic retrieval is not configured; using BM25 only.')
    elif mode != 'bm25' and status['chunks']:
        warnings.append('Build the semantic index to enable hybrid retrieval.')
    if mode != 'bm25' and status['pendingChunks'] and status['embeddedChunks']:
        warnings.append(f"{status['pendingChunks']} chunks still need embeddings; semantic coverage is partial.")
    # One consistent SQLite snapshot for both ranked lists and their source text.
    store.db.execute('BEGIN')
    try:
        candidates = max(60, min(limit * 2, 400))
        lexical = store.lexical(query, candidates, terms=parsed['lexical_terms'] if parsed else None) if mode != 'semantic' else []
        semantic = []
        if vector:
            try:
                minimum = float(os.environ.get('RAG_MIN_SIMILARITY', '0.25'))
                if not math.isfinite(minimum) or not -1 <= minimum <= 1:
                    raise ValueError('RAG_MIN_SIMILARITY must be between -1 and 1.')
                semantic = store.semantic(embedding.space, vector, candidates, minimum)
            except ValueError as error:
                warnings.append(str(error))
                vector = None
        if mode == 'semantic' and vector is None:
            raise ValueError('Semantic-only retrieval is unavailable; no lexical fallback is allowed for this evaluation mode.')
        sources = store.sources(fuse(lexical, semantic, candidates))[:limit]
        for index, source in enumerate(sources, 1):
            source['id'] = index
        ids = list(dict.fromkeys(source['documentId'] for source in sources))
        documents = [store.document(doc_id) for doc_id in ids]
    finally:
        store.db.rollback()
    return {'sources': sources, 'documents': documents,
            'retrieval': {'mode': ('semantic' if mode == 'semantic' else 'hybrid') if vector else 'bm25', 'fusion': 'rrf' if vector and mode == 'hybrid' else None,
                          'warnings': warnings, 'revision': status['revision'],
                          'query_parsing': query_parsing, 'parsed_query': parsed}}


def embed_batch(store, embedding):
    if not embedding.configured:
        raise ValueError('Configure EMBEDDING_BASE_URL, EMBEDDING_API_KEY and EMBEDDING_MODEL first.')
    completed = 0
    # Smaller Ollama batches keep local query latency and CPU request duration bounded.
    batch_size = 4 if getattr(embedding, 'provider', '') == 'ollama' else 16
    # At most two provider calls per HTTP operation; CLI repeats this resumably.
    for _ in range(2):
        batch = store.missing(embedding.space, batch_size)
        if not batch:
            break
        vectors = embedding.embed([row['embedding_text'] for row in batch])
        store.save_vectors(embedding.space, [row['text_hash'] for row in batch], vectors)
        completed += len(batch)
    return {'embedded': completed, **store.status(embedding.space)}


def run(command, request, database=None, embedding=None):
    embedding = embedding or Embeddings()
    database = database or os.environ.get('RAG_DB_PATH') or str(ROOT / 'dataset/rag.sqlite3')
    with open_store(database) as store:
        if command == 'status':
            return {**store.status(embedding.space), 'semanticConfigured': embedding.configured,
                    'embeddingSpace': embedding.space,
                    'embeddingModel': embedding.model or None, 'embeddingProvider': getattr(embedding, 'provider', 'openai'),
                    'storage': 'sqlite', 'vectorSearch': 'exact-cosine'}
        if command == 'ingest':
            with Path(request['path']).open(encoding='utf-8-sig') as stream:
                data = json.load(stream)
            result = store.ingest(data)
            return {**result, **store.status(embedding.space)}
        if command == 'search':
            return store.search_documents(request['query'], request.get('limit', 10), request.get('page', 1))
        if command == 'retrieve':
            return retrieve(store, embedding, request['query'], request.get('limit', 8), request.get('mode', 'hybrid'), request.get('query_parsing', 'off'))
        if command == 'document':
            return store.document(request['id'])
        if command == 'embed':
            with indexing_lock(database):
                return embed_batch(store, embedding)
        if command == 'import-archive':
            archive = request.get('path') or str(ROOT.parent / 'archive.zip')
            result = import_archive(store, archive, request.get('split', 'train.csv'),
                                    lambda rows: print(f'Imported {rows} training rows...', file=sys.stderr) if rows % 5000 == 0 else None)
            return {**result, **store.status(embedding.space)}
        if command == 'embed-all':
            if getattr(embedding, 'provider', '') == 'ollama':
                embedding.document_timeout = 180
            def report(event):
                print('INDEX_EVENT ' + json.dumps(event), file=sys.stderr, flush=True)
            with indexing_lock(database):
                return build_index(store, embedding, on_event=report)
        if command == 'import-legacy':
            indexed = skipped = 0
            paths = sorted((ROOT / 'dataset/DocumentBarrels').glob('*.csv'))
            if not paths:
                raise ValueError('No legacy document barrels found in server/dataset/DocumentBarrels.')
            for path in paths:
                with path.open(encoding='utf-8-sig', newline='') as stream:
                    batch = []
                    for row in csv.DictReader(stream):
                        row['id'] = int(row.get('Id') or row.get('id'))
                        try:
                            row['Score'] = float(row.get('Score') or 0)
                            if not math.isfinite(row['Score']):
                                row['Score'] = 0
                        except ValueError:
                            row['Score'] = 0
                        batch.append(row)
                        if len(batch) == 100:
                            result = store.ingest(batch)
                            indexed += result['indexed']; skipped += result['skipped']
                            batch = []
                    if batch:
                        result = store.ingest(batch)
                        indexed += result['indexed']; skipped += result['skipped']
            return {'indexed': indexed, 'skipped': skipped, **store.status(embedding.space)}
        raise ValueError('Unknown RAG operation.')


if __name__ == '__main__':
    try:
        request = json.load(sys.stdin) if len(sys.argv) < 3 else {}
        print(json.dumps(run(sys.argv[1], request), ensure_ascii=True, allow_nan=False))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
