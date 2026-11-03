"""Paired reporting of frozen query-parsing evaluation arms; no model calls."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics

from score import summarize


def aggregate(rows):
    result = summarize(rows)
    answerable = [row for row in rows if row['answerable']]
    negative = [row for row in rows if not row['answerable']]
    times = sorted(row['duration_seconds'] for row in rows)
    result.update(answerable_cases=len(answerable),
                  accepted_answerable_cases=sum(row['generation_status'] == 'answered' for row in answerable),
                  accepted_answer_coverage=sum(row['generation_status'] == 'answered' for row in answerable) / len(answerable) if answerable else None,
                  answerable_refusals=sum(row['generation_status'] == 'insufficient_evidence' for row in answerable),
                  unsupported_answers=sum(row['generation_status'] == 'answered' for row in negative),
                  unverified_cases=sum(row['generation_status'] == 'unverified' for row in rows),
                  repaired_cases=sum(row.get('generation', {}).get('repaired', False) for row in rows),
                  generation_attempts=sum(row.get('generation', {}).get('attempts', 0) for row in rows),
                  mean_seconds=statistics.mean(times), median_seconds=statistics.median(times),
                  p95_seconds=times[max(0, math.ceil(.95 * len(times)) - 1)],
                  metric_error_types=dict(Counter(error for row in rows for error in row.get('metric_errors', {}).values())))
    return result


def compare(off_path, on_path, output):
    reports = {name: json.loads(path.read_text(encoding='utf-8')) for name, path in [('off', off_path), ('on', on_path)]}
    for report in reports.values():
        assert report.get('scoring_complete') and report['summary']['cases'] == 50, 'Wait for complete scoring'
    arms = {name: {row['id']: row for row in report['results']} for name, report in reports.items()}
    assert len(arms['off']) == len(arms['on']) == 50 and arms['off'].keys() == arms['on'].keys()
    paired = []
    for identifier, before in arms['off'].items():
        after = arms['on'][identifier]
        assert before['query_parsing'] == 'off' and after['query_parsing'] == 'on'
        for field in ('user_input', 'case_hash', 'prompt_policy_hash', 'parser_hash', 'embedding_space', 'index_revision', 'answer_model'):
            assert before[field] == after[field], f'Mismatched {field}: {identifier}'
        assert after['parsed_query']['semantic_query'] == after['user_input']
        metrics = {}
        for name in set(before['scores']) | set(after['scores']):
            left, right = before['scores'].get(name), after['scores'].get(name)
            metrics[name] = {'off': left, 'on': right, 'delta': right - left if left is not None and right is not None else None}
        paired.append({'id': identifier, 'category': before['category'], 'split': before['split'],
                       'answerable': before['answerable'], 'off_status': before['generation_status'], 'on_status': after['generation_status'],
                       'retrieved_documents_changed': before['retrieved_document_ids'] != after['retrieved_document_ids'],
                       'retrieved_passages_changed': [(source.get('chunkId'), source.get('text')) for source in before.get('sources', [])] != [(source.get('chunkId'), source.get('text')) for source in after.get('sources', [])], 'metrics': metrics})
    groups = {}
    for group in ('all', 'development', 'holdout', 'direct', 'harder', 'unanswerable'):
        selected = {name: [row for row in rows.values() if group == 'all' or row['split'] == group or row['category'] == group] for name, rows in arms.items()}
        groups[group] = {name: aggregate(rows) for name, rows in selected.items()}
    metric_deltas = {}
    for name in set().union(*(row['metrics'].keys() for row in paired)):
        deltas = [row['metrics'][name]['delta'] for row in paired if row['metrics'].get(name, {}).get('delta') is not None]
        metric_deltas[name] = {'paired_scored_cases': len(deltas), 'mean_delta_on_minus_off': statistics.mean(deltas) if deltas else None,
                               'better': sum(value > 1e-8 for value in deltas), 'worse': sum(value < -1e-8 for value in deltas),
                               'tied': sum(abs(value) <= 1e-8 for value in deltas)}
    result = {'passage_rankings_changed': sum(row['retrieved_passages_changed'] for row in paired),
              'passage_rankings_unchanged': sum(not row['retrieved_passages_changed'] for row in paired), 'groups': groups, 'paired_metric_deltas': metric_deltas, 'paired_cases': paired,
              'judge_models': {name: report['judge_model'] for name, report in reports.items()},
              'judge_bias': {name: report['judge_matches_answer_model'] for name, report in reports.items()},
              'limitations': ['Source labels are agent-reviewed, not human-adjudicated.',
                              'Fifty cases and one run per arm do not establish general accuracy or significance.',
                              'Generation/judgment variability can affect scores independently of parsing.',
                              'Concurrent captures and shared semantic-query cache make latency descriptive, not an isolated parser benchmark.',
                              'Parser changes lexical BM25 only; original semantic query and answer question are unchanged.',
                              'Holdout outcomes have now been observed and must not guide tuning without new held-out validation.',
                              'Citation and quote provenance checks do not prove semantic entailment.']}
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    lines = ['# Expanded 50-case query-parsing comparison', '',
             'Hybrid retrieval, the same frozen 50 questions and corpus, GPT-OSS answer/judge, Nomic embeddings, six evidence passages, and the same structured generation policy. Parsing on removes lexical filler and preserves phrases/technical tokens; parsing off uses the original tokenization. Semantic input is unchanged. No model-based rewriting or production-default change.', '',
             '| Measure | Parsing off | Parsing on |', '|---|---:|---:|']
    for label, key in [('Accepted answers / answerable cases', 'accepted_answerable_cases'), ('Unverified responses', 'unverified_cases'), ('Refused answerable questions', 'answerable_refusals'), ('Correct abstentions / 10 negatives', 'correct_abstentions'), ('Unsupported answers on negatives', 'unsupported_answers'), ('Ragas metric errors', 'metric_errors')]:
        left, right = groups['all']['off'][key], groups['all']['on'][key]
        if key == 'accepted_answerable_cases':
            left, right = f"{left}/40", f"{right}/40"
        lines.append(f'| {label} | {left} | {right} |')
    for name in ('faithfulness', 'answer_relevancy', 'context_precision', 'context_recall', 'known_source_recall', 'known_source_mrr', 'known_source_ndcg'):
        values = []
        for arm in ('off', 'on'):
            metric = groups['all'][arm]['metrics'][name]
            values.append(f"{metric['mean']:.3f} (n={metric['scored_cases']})" if metric['mean'] is not None else 'Not scored')
        lines.append(f"| {name} | {values[0]} | {values[1]} |")
    lines += ['', f"Retrieved passage rankings changed on {result['passage_rankings_changed']}/50 cases and stayed identical on {result['passage_rankings_unchanged']}/50. Answer differences with identical evidence can reflect model variability rather than parsing.", '', '## Paired changes', '', '| Metric | Matched cases | Mean on-minus-off | Better / worse / tied |', '|---|---:|---:|---|']
    for name, item in sorted(metric_deltas.items()):
        delta = item['mean_delta_on_minus_off']
        lines.append(f"| {name} | {item['paired_scored_cases']} | {delta:.3f} | {item['better']} / {item['worse']} / {item['tied']} |" if delta is not None else f'| {name} | 0 | — | — |')
    lines += ['', '## Split and difficulty results', '', '| Group | Accepted off / on | Correct refusals off / on | Recall off / on |', '|---|---|---|---|']
    for group in ('development', 'holdout', 'direct', 'harder', 'unanswerable'):
        left, right = groups[group]['off'], groups[group]['on']
        recall = [item['metrics'].get('known_source_recall', {}).get('mean') for item in (left, right)]
        lines.append(f"| {group} | {left['accepted_answerable_cases']} / {right['accepted_answerable_cases']} | {left['correct_abstentions']} / {right['correct_abstentions']} | {recall[0]} / {recall[1]} |")
    lines += ['', '## Latency and limitations', '']
    for arm in ('off', 'on'):
        group = groups['all'][arm]
        lines.append(f"Parsing {arm}: mean {group['mean_seconds']:.2f}s, median {group['median_seconds']:.2f}s, observed p95 {group['p95_seconds']:.2f}s end-to-end. Repairs: {group['repaired_cases']}. Provider generation attempts: {group['generation_attempts']}.")
    lines += ['', *['- ' + limitation for limitation in result['limitations']], '',
              'Means exclude null/failed/skipped metrics; scored counts and failures are reported rather than silently converted to zero. Compare matched deltas for quality instead of means over different accepted subsets. Negative cases include five synthetic absent identifiers and five missing details in named posts. Do not treat accepted-answer coverage as factual accuracy. Complete case-level and per-group data are in the adjacent JSON report.']
    output.with_suffix('.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--off', type=Path, required=True)
    parser.add_argument('--on', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.off, args.on, args.output)
    print(json.dumps({'all': result['groups']['all'], 'paired': result['paired_metric_deltas']}, indent=2))
