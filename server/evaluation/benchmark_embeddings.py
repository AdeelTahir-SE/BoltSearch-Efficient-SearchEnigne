"""Matched small-corpus quality/speed probe; not a universal embedding ranking."""
import json
import os
from pathlib import Path
import sqlite3
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'rag'))
from embeddings import Embeddings, TransientEmbeddingError
from store import plain_text


def main():
    directory = ROOT / 'dataset/stacksample/staged'
    cases = [json.loads(line) for line in (ROOT / 'evaluation/stacksample-cases.jsonl').read_text().splitlines()]
    cases = [row for row in cases if row['answerable']]
    gold_ids = {row['relevant_document_ids'][0] for row in cases}
    with sqlite3.connect(f'file:{directory / "rag.sqlite3"}?mode=ro', uri=True) as db:
        documents = [json.loads(db.execute('SELECT payload FROM documents WHERE id=?', (identifier,)).fetchone()[0]) for identifier in sorted(gold_ids)]
        for raw, in db.execute('SELECT payload FROM documents ORDER BY id LIMIT 200'):
            doc = json.loads(raw)
            if doc['Id'] not in gold_ids:
                documents.append(doc)
            if len(documents) >= 64:
                break
    texts = [doc['Title'] + '\nanswer 1: ' + plain_text(doc['Answer'].split(',,,,,')[0])[:1200] for doc in documents]
    models = [
        ('nomic-ai/nomic-embed-text-v1.5', 'search_query: ', 'search_document: '),
        ('accounts/fireworks/models/qwen3-embedding-8b', 'Instruct: Given a programming question, retrieve relevant Stack Overflow passages\nQuery: ', '')]
    results = []
    for model, query_prefix, document_prefix in models:
        env = dict(os.environ, EMBEDDING_PROVIDER='openai', EMBEDDING_MODEL=model,
                   EMBEDDING_BASE_URL='https://api.fireworks.ai/inference/v1', EMBEDDING_VERSION='1',
                   EMBEDDING_QUERY_PREFIX=query_prefix, EMBEDDING_DOCUMENT_PREFIX=document_prefix)
        embedding = Embeddings(env)
        timings, query_timings = [], []

        def call(values, query=False):
            for attempt in range(3):
                try:
                    return embedding.embed(values, query=query)
                except TransientEmbeddingError:
                    if attempt == 2:
                        raise
                    time.sleep(2 ** attempt)

        for repeat in range(2):
            vectors = []
            for offset in range(0, len(texts), 16):
                start = time.perf_counter()
                vectors.extend(call(texts[offset:offset + 16]))
                timings.append(time.perf_counter() - start)
        queries = call([case['user_input'] for case in cases], query=True)
        for repeat in range(3):
            start = time.perf_counter()
            call([cases[repeat]['user_input']], query=True)
            query_timings.append(time.perf_counter() - start)
        ranks = []
        for case, query in zip(cases, queries):
            ranking = sorted(range(len(documents)), key=lambda i: (-sum(a * b for a, b in zip(query, vectors[i])), documents[i]['Id']))
            ranks.append(next(rank for rank, i in enumerate(ranking, 1) if documents[i]['Id'] in case['relevant_document_ids']))
        result = {'model': model, 'dimensions': len(vectors[0]), 'cases': len(cases), 'candidate_documents': len(documents),
                  'recall_at_1': sum(rank == 1 for rank in ranks) / len(ranks),
                  'recall_at_5': sum(rank <= 5 for rank in ranks) / len(ranks),
                  'mrr': statistics.mean(1 / rank for rank in ranks), 'ranks': ranks,
                  'document_batch_size': 16, 'document_request_seconds': timings,
                  'median_document_request_seconds': statistics.median(timings),
                  'query_request_seconds': query_timings, 'median_query_seconds': statistics.median(query_timings),
                  'query_prefix': query_prefix, 'document_prefix': document_prefix}
        results.append(result)
        print(json.dumps(result), flush=True)
        (directory / 'embedding-benchmark.json').write_text(json.dumps({'results': results, 'complete': False}, indent=2), encoding='utf-8')
    best_recall = max(row['recall_at_5'] for row in results)
    best_mrr = max(row['mrr'] for row in results)
    candidates = [row for row in results if row['recall_at_5'] >= best_recall and row['mrr'] >= best_mrr - 0.03]
    selected = min(candidates, key=lambda row: row['median_document_request_seconds'] + row['median_query_seconds'])
    report = {'complete': True, 'results': results, 'selected': selected,
              'selection_policy': 'Equal best recall@5 and MRR within 0.03 of best, then lowest sum of median batch/query latency.',
              'limitations': 'Nine manually source-checked seed queries, 64 answer excerpts, sequential model order, two document rounds and three query timings; not corpus-wide or held-out. Pilot cases overlap this development probe.'}
    (directory / 'embedding-benchmark.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
