"""Offline Ragas scoring of captured responses, with independent judge settings."""
import argparse
import asyncio
import importlib.metadata
import importlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ['RAGAS_DO_NOT_TRACK'] = 'true'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['DO_NOT_TRACK'] = '1'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'rag'))
from embeddings import Embeddings


def retrieval_metrics(retrieved, relevant):
    """Known-source metrics, deduplicated by document; gold sets may be incomplete."""
    ranked = list(dict.fromkeys(retrieved))
    gold = set(relevant)
    if not gold:
        return {name: None for name in ('known_source_recall', 'known_source_mrr', 'known_source_ndcg')}
    hits = [1 if doc_id in gold else 0 for doc_id in ranked]
    recall = len(set(ranked) & gold) / len(gold)
    mrr = next((1 / (index + 1) for index, hit in enumerate(hits) if hit), 0)
    dcg = sum(hit / math.log2(index + 2) for index, hit in enumerate(hits))
    ideal = sum(1 / math.log2(index + 2) for index in range(min(len(gold), len(ranked))))
    return {'known_source_recall': recall, 'known_source_mrr': mrr, 'known_source_ndcg': dcg / ideal if ideal else 0}


def finite_score(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def summarize(rows):
    metrics = {}
    names = set().union(*(row.get('scores', {}).keys() for row in rows))
    for name in sorted(names):
        values = [row['scores'][name] for row in rows if row.get('scores', {}).get(name) is not None]
        metrics[name] = {'mean': sum(values) / len(values) if values else None, 'scored_cases': len(values)}
    negatives = [row for row in rows if not row['answerable']]
    return {'cases': len(rows), 'fixture_cases': sum(bool(row.get('fixture_only')) for row in rows), 'metrics': metrics,
            'answered_cases': sum(row['generation_status'] == 'answered' for row in rows),
            'unverified_cases': sum(row['generation_status'] == 'unverified' for row in rows),
            'expected_abstention_cases': len(negatives),
            'correct_abstentions': sum(row['generation_status'] == 'insufficient_evidence' for row in negatives),
            'metric_errors': sum(len(row.get('metric_errors', {})) for row in rows),
            'partial_index': any(row.get('partial', False) for row in rows)}


def judge_config():
    return {'base_url': os.environ.get('EVAL_JUDGE_BASE_URL') or os.environ.get('RAG_BASE_URL') or os.environ.get('BASE_URL') or 'https://api.fireworks.ai/inference/v1',
            'api_key': os.environ.get('EVAL_JUDGE_API_KEY') or os.environ.get('RAG_API_KEY') or os.environ.get('FIREWORKS_API_KEY', ''),
            'model': os.environ.get('EVAL_JUDGE_MODEL') or os.environ.get('RAG_MODEL', '')}


def load_rows(path, limit):
    rows = [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if not rows:
        raise ValueError('Capture is empty.')
    seen = set()
    for row in rows:
        if not isinstance(row.get('id'), str) or row['id'] in seen:
            raise ValueError('Capture IDs must be unique strings.')
        seen.add(row['id'])
        if not isinstance(row.get('answerable'), bool) or not isinstance(row.get('response'), str) or not isinstance(row.get('user_input'), str):
            raise ValueError('Capture is missing question, response or answerable fields.')
        if not isinstance(row.get('retrieved_contexts'), list) or any(not isinstance(text, str) for text in row['retrieved_contexts']):
            raise ValueError('retrieved_contexts must contain strings.')
        if row.get('generation_status') not in ('answered', 'unverified', 'insufficient_evidence'):
            raise ValueError('Unknown generation status.')
        if not isinstance(row.get('retrieved_document_ids'), list) or not isinstance(row.get('relevant_document_ids'), list):
            raise ValueError('Capture must include retrieved and reference document IDs.')
    return rows[:limit]


async def score_rows(rows, output, selected, timeout, concurrency=1, judge_max_tokens=2048):
    # Imports are lazy: schema and deterministic metric tests need no Ragas installation.
    import httpx
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory
    from ragas.embeddings.base import BaseRagasEmbedding
    from ragas.metrics.collections import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness

    local = Embeddings()
    if not local.configured:
        raise ValueError('Configure an embedding provider for evaluation.')
    config = judge_config()
    if not config['api_key'] or not config['model']:
        raise ValueError('Configure a Fireworks judge key and EVAL_JUDGE_MODEL (or RAG_MODEL).')

    class ConfiguredEmbeddings(BaseRagasEmbedding):
        def embed_text(self, text, **kwargs):
            return local.embed([text], query=True)[0]
        async def aembed_text(self, text, **kwargs):
            return await asyncio.to_thread(self.embed_text, text)
        def embed_texts(self, texts, **kwargs):
            result = []
            for offset in range(0, len(texts), 4):
                result.extend(local.embed(texts[offset:offset + 4], query=True))
            return result
        async def aembed_texts(self, texts, **kwargs):
            return await asyncio.to_thread(self.embed_texts, texts)

    from urllib.parse import urlparse
    url = urlparse(config['base_url'])
    if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('localhost', '127.0.0.1', '::1')):
        raise ValueError('Judge endpoint must use HTTPS, except on localhost.')
    results = []
    judge_model = config['model']
    same_judge = any(row.get('answer_model') == judge_model for row in rows)
    # No retries hidden by the HTTP client; Ragas structured-output retries are bounded below.
    async with AsyncOpenAI(api_key=config['api_key'], base_url=config['base_url'], max_retries=0,
                          http_client=httpx.AsyncClient(timeout=60, follow_redirects=False)) as client:
        llm = llm_factory(judge_model, provider='openai', client=client, max_tokens=judge_max_tokens, temperature=0, max_retries=1)
        order = {row['id']: i for i, row in enumerate(rows)}
        report = None
        semaphore = asyncio.Semaphore(concurrency)
        async def evaluate(row):
            nonlocal report
            metrics = {'faithfulness': Faithfulness(llm=llm),
                       'answer_relevancy': AnswerRelevancy(llm=llm, embeddings=ConfiguredEmbeddings(), strictness=3),
                       'context_precision': ContextPrecision(llm=llm), 'context_recall': ContextRecall(llm=llm)}
            result = {**row, 'scores': retrieval_metrics(row['retrieved_document_ids'], row['relevant_document_ids']), 'metric_errors': {}, 'skipped_metrics': {}}
            for name in selected:
                if name in ('faithfulness', 'answer_relevancy') and row['generation_status'] != 'answered':
                    result['scores'][name] = None
                    result['skipped_metrics'][name] = 'Abstention/unverified answer is evaluated separately.'
                    continue
                if not row['retrieved_contexts']:
                    result['scores'][name] = None
                    result['skipped_metrics'][name] = 'No retrieved contexts.'
                    continue
                args = {'user_input': row['user_input']}
                if name in ('faithfulness', 'answer_relevancy'):
                    args['response'] = row['response']
                if name != 'answer_relevancy':
                    args['retrieved_contexts'] = row['retrieved_contexts']
                if name in ('context_precision', 'context_recall'):
                    if not row.get('reference') or not row['answerable']:
                        result['scores'][name] = None
                        result['skipped_metrics'][name] = 'Reference-supported answer required.'
                        continue
                    args['reference'] = row['reference']
                try:
                    metric = await asyncio.wait_for(metrics[name].ascore(**args), timeout)
                    result['scores'][name] = finite_score(metric.value)
                    if result['scores'][name] is None:
                        result['metric_errors'][name] = 'Non-finite score; excluded from means.'
                except Exception as error:
                    result['scores'][name] = None
                    # Provider exceptions may contain prompts; never dump them or credentials.
                    result['metric_errors'][name] = type(error).__name__
            results.append(result)
            results.sort(key=lambda item: order[item['id']])
            report = {'created_at': datetime.now(timezone.utc).isoformat(),
                      'purpose': 'synthetic_fixture_check' if all(row.get('fixture_only') for row in rows) else 'pipeline_evaluation',
                      'ragas_version': importlib.metadata.version('ragas'),
                      'judge_model': judge_model, 'judge_matches_answer_model': same_judge,
                      'evaluation_embedding_model': local.model, 'requested_cases': len(rows), 'scoring_concurrency': concurrency,
                      'judge_max_tokens': judge_max_tokens, 'judge_temperature': 0, 'metric_timeout_seconds': timeout,
                      'requested_metrics': selected, 'answer_relevancy_strictness': 3,
                      'scoring_complete': len(results) == len(rows), 'summary': summarize(results), 'results': results}
            temporary = output.with_suffix('.tmp')
            temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            temporary.replace(output)
            print(f"Scored {row['id']}: {len(result['metric_errors'])} metric errors", flush=True)
        async def bounded(row):
            async with semaphore:
                await evaluate(row)
        await asyncio.gather(*(bounded(row) for row in rows))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Inspect dependencies/settings without model calls.')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--metrics', default='faithfulness,answer_relevancy,context_precision,context_recall')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--concurrency', type=int, default=1, help='Concurrent cases, 1–4; provider calls remain bounded.')
    parser.add_argument('--judge-max-tokens', type=int, default=2048, help='Judge output budget, 512–8192 tokens.')
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    if not 512 <= args.judge_max_tokens <= 8192:
        raise ValueError('Judge output budget must be 512–8192 tokens.')
    if not 1 <= args.concurrency <= 4:
        raise ValueError('Scoring concurrency must be 1–4.')
    if not 1 <= args.limit <= 100 or not 1 <= args.timeout <= 600:
        raise ValueError('Limit must be 1–100 and per-metric timeout 1–600 seconds.')
    if args.check:
        config, embedding = judge_config(), Embeddings()
        versions = {}
        for name in ('ragas', 'openai'):
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = None
        try:
            importlib.import_module('ragas.metrics.collections')
            runtime_ready, runtime_error = True, None
        except Exception as error:
            runtime_ready, runtime_error = False, type(error).__name__
        print(json.dumps({'dependencies': versions, 'judgeConfigured': bool(config['api_key'] and config['model']),
                          'runtimeImportsReady': runtime_ready, 'runtimeImportError': runtime_error,
                          'judgeModel': config['model'], 'judgeMatchesAnswerModel': config['model'] == os.environ.get('RAG_MODEL'),
                          'localEmbeddingsConfigured': embedding.provider == 'ollama' and embedding.configured,
                          'embeddingsConfigured': embedding.configured,
                          'embeddingProvider': embedding.provider, 'embeddingModel': embedding.model,
                          'modelCallsMade': 0}, indent=2))
        if not runtime_ready:
            sys.exit(1)
        return
    if args.input is None:
        parser.error('--input capture.jsonl is required unless using --check.')
    selected = args.metrics.split(',')
    if not selected or set(selected) - {'faithfulness', 'answer_relevancy', 'context_precision', 'context_recall'}:
        raise ValueError('Unknown Ragas metric.')
    rows = load_rows(args.input, args.limit)
    if any(row.get('partial') for row in rows) and not args.allow_partial:
        raise ValueError('Partial-index captures are diagnostic. Use --allow-partial explicitly.')
    output = args.output or args.input.with_suffix('.scores.json')
    if output.exists():
        raise ValueError('Output exists; choose a new output path to preserve previous results.')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(score_rows(rows, output, selected, args.timeout, args.concurrency, args.judge_max_tokens))
    print(json.dumps(report['summary'], indent=2))
    print(f'Report saved: {output}')
    if report['summary']['metric_errors']:
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Report configuration/schema errors without exposing provider response bodies.
        if isinstance(error, (ValueError, FileNotFoundError)):
            print(str(error), file=sys.stderr)
        else:
            print(f'Evaluation failed ({type(error).__name__}); check dependencies and provider configuration.', file=sys.stderr)
        sys.exit(1)
