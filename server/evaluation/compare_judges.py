"""Compare judges on identical saved RAG responses, without additional model calls."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import statistics

METRICS = ('faithfulness', 'answer_relevancy', 'context_precision', 'context_recall')
IDENTITY = ('id', 'user_input', 'response', 'reference', 'answerable', 'generation_status',
            'retrieved_contexts', 'retrieved_document_ids', 'relevant_document_ids', 'answer_model',
            'case_hash', 'prompt_policy_hash', 'embedding_space', 'index_revision')


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def literal_block(text):
    fence = '`' * max(3, 1 + max((len(match) for match in re.findall(r'`+', text)), default=0))
    return f'{fence}\n{text}\n{fence}'


def metric_summary(rows, name, ids=None):
    values = [row['scores'].get(name) for row in rows if ids is None or row['id'] in ids]
    values = [value for value in values if finite(value)]
    return {'mean': statistics.mean(values) if values else None, 'scored_cases': len(values)}


def paired_agreement(reference, other, name):
    pairs = [(row['scores'].get(name), other[identifier]['scores'].get(name)) for identifier, row in reference.items()]
    pairs = [(left, right) for left, right in pairs if finite(left) and finite(right)]
    if not pairs:
        return {'cases': 0, 'mean_delta_other_minus_self': None, 'mean_absolute_difference': None, 'within_0_10': None}
    deltas = [right - left for left, right in pairs]
    return {'cases': len(pairs), 'mean_self_on_paired_cases': statistics.mean(left for left, right in pairs),
            'mean_other_on_paired_cases': statistics.mean(right for left, right in pairs),
            'mean_delta_other_minus_self': statistics.mean(deltas),
            'mean_absolute_difference': statistics.mean(abs(delta) for delta in deltas),
            'within_0_10': sum(abs(delta) <= .1 + 1e-9 for delta in deltas) / len(deltas),
            'higher': sum(delta > 1e-8 for delta in deltas), 'lower': sum(delta < -1e-8 for delta in deltas),
            'tied': sum(abs(delta) <= 1e-8 for delta in deltas)}


def compare(self_path, others, output_directory, expected_cases=50):
    assert 'self_gpt_oss' not in others, 'Use a distinct label for each independent judge'
    paths = {'self_gpt_oss': self_path, **others}
    reports = {label: json.loads(path.read_text(encoding='utf-8')) for label, path in paths.items()}
    indexed = {}
    for label, report in reports.items():
        assert report.get('scoring_complete'), f'Incomplete report: {label}'
        rows = report['results']
        assert len(rows) == expected_cases and len({row['id'] for row in rows}) == expected_cases
        indexed[label] = {row['id']: row for row in rows}
    baseline = indexed['self_gpt_oss']
    generator_models = {row['answer_model'] for row in baseline.values()}
    assert generator_models == {reports['self_gpt_oss']['judge_model']}, 'Baseline must use the generator as judge'
    judge_models = [report['judge_model'] for report in reports.values()]
    assert len(set(judge_models)) == len(judge_models), 'Each judge must be a different model'
    for label, rows in indexed.items():
        assert rows.keys() == baseline.keys(), f'Different cases: {label}'
        assert reports[label]['ragas_version'] == reports['self_gpt_oss']['ragas_version']
        assert reports[label]['evaluation_embedding_model'] == reports['self_gpt_oss']['evaluation_embedding_model']
        assert reports[label].get('judge_max_tokens', 2048) == reports['self_gpt_oss'].get('judge_max_tokens', 2048), 'Judge output budgets differ'
        for identifier, original in baseline.items():
            for field in IDENTITY:
                assert original[field] == rows[identifier][field], f'Different {field}: {label}/{identifier}'
    judges = {}
    for label, report in reports.items():
        rows = report['results']
        errors = Counter(error for row in rows for error in row.get('metric_errors', {}).values())
        judges[label] = {'model': report['judge_model'], 'matches_generator': report['judge_matches_answer_model'],
                         'cases': len(rows), 'metric_errors': sum(errors.values()), 'error_types': dict(errors),
                         'failed_metrics': dict(Counter(name for row in rows for name in row.get('metric_errors', {}))),
                         'metrics': {name: metric_summary(rows, name) for name in METRICS},
                         'failed_cases': [{'id': row['id'], 'errors': row.get('metric_errors', {})} for row in rows if row.get('metric_errors')]}
        attempted = sum(item['scored_cases'] for item in judges[label]['metrics'].values()) + sum(errors.values())
        judges[label]['attempted_metric_values'] = attempted
        judges[label]['metric_value_failure_rate'] = sum(errors.values()) / attempted if attempted else None
    common = {}
    for name in METRICS:
        ids = {identifier for identifier in baseline if all(finite(rows[identifier]['scores'].get(name)) for rows in indexed.values())}
        common[name] = {'cases': len(ids), 'judges': {label: metric_summary(list(rows.values()), name, ids) for label, rows in indexed.items()}}
    paired = {label: {name: paired_agreement(baseline, rows, name) for name in METRICS} for label, rows in indexed.items() if label != 'self_gpt_oss'}
    groups = {}
    for group in ('development', 'holdout', 'direct', 'harder', 'unanswerable'):
        groups[group] = {label: {name: metric_summary([row for row in rows.values() if row['split'] == group or row['category'] == group], name) for name in METRICS} for label, rows in indexed.items()}
    disagreements = []
    for identifier, original in baseline.items():
        ranges = {}
        for name in METRICS:
            scores = {label: rows[identifier]['scores'].get(name) for label, rows in indexed.items()}
            values = [value for value in scores.values() if finite(value)]
            if len(values) >= 2:
                ranges[name] = {'range': max(values) - min(values), 'scores': scores}
        maximum = max((item['range'] for item in ranges.values()), default=0)
        if maximum >= .25 - 1e-9:
            disagreements.append({'id': identifier, 'split': original['split'], 'category': original['category'], 'max_metric_range': maximum, 'metrics': ranges})
    disagreements.sort(key=lambda row: (-row['max_metric_range'], row['id']))
    rows = list(baseline.values())
    fixed = {'cases': len(rows), 'answerable_cases': sum(row['answerable'] for row in rows),
             'accepted_answerable': sum(row['answerable'] and row['generation_status'] == 'answered' for row in rows),
             'answerable_refusals': sum(row['answerable'] and row['generation_status'] == 'insufficient_evidence' for row in rows),
             'unverified': sum(row['generation_status'] == 'unverified' for row in rows),
             'correct_missing_evidence_refusals': sum(not row['answerable'] and row['generation_status'] == 'insufficient_evidence' for row in rows)}
    judge_budget = reports['self_gpt_oss'].get('judge_max_tokens', 2048)
    result = {'judge_max_tokens': judge_budget, 'fixed_generation_outcomes': fixed,
              'fixed_retrieval_metrics': {name: metric_summary(rows, name) for name in ('known_source_recall', 'known_source_mrr', 'known_source_ndcg')}, 'judges': judges, 'common_scored_cases': common, 'paired_vs_self': paired,
              'groups': groups, 'large_disagreements': disagreements, 'review_range_threshold': .25,
              'limitations': ['Same-model judge may favor its own answers; disagreement alone does not prove this bias.',
                              'Different models can share biases; none is human-adjudicated ground truth.',
                              'Missing metrics may concentrate on harder cases; even common-case comparisons cannot fully remove that selection bias.',
                              'One pass per judge on 50 agent-labeled cases does not establish statistical reliability.',
                              'Reports contain one pass per judge and may have been scored at different times; repeated-run uncertainty was not estimated.',
                              'Means exclude skipped/failed scores; use common-case means and paired differences when coverage differs.',
                              'Answer relevance also depends on questions generated by each judge and the fixed Nomic embedding model.',
                              'Saved duration_seconds describes original answer generation, not judge speed. No complete judge cost/speed comparison was recorded.',
                              f'The fixed {judge_budget}-token budget and bounded retries can affect different models differently; failures describe this configuration, not inherent model ability.']}
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / 'comparison.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    labels = list(judges)
    lines = ['# Same-model versus different-model Ragas judges', '',
             f'All judges assess the same 50 saved parsing-off hybrid outputs from GPT-OSS 120B, with the same references, excerpts and metric settings, and a {judge_budget}-token judge budget. No answers were regenerated, no retrieval was rerun, and production configuration was unchanged.', '',
             f"Fixed outcomes: {fixed['accepted_answerable']}/{fixed['answerable_cases']} accepted supported answers, {fixed['unverified']} unverified response, {fixed['answerable_refusals']} answerable refusal, and {fixed['correct_missing_evidence_refusals']}/10 correct missing-evidence refusals. Judge choice cannot change these generation outcomes.", '',
             '## Scores using all available cases', '', '| Judge | Faithfulness | Answer relevance | Context precision | Context recall | Metric errors |', '|---|---:|---:|---:|---:|---:|']
    for label in labels:
        judge = judges[label]
        values = [f"{judge['metrics'][name]['mean']:.3f} (n={judge['metrics'][name]['scored_cases']})" if judge['metrics'][name]['mean'] is not None else 'Not scored' for name in METRICS]
        lines.append('| ' + ' | '.join([judge['model'] + (' — self' if judge['matches_generator'] else ' — different model'), *values, str(judge['metric_errors'])]) + ' |')
    lines += ['', '## Like-for-like means: cases scored by every judge', '', '| Metric | Common cases | ' + ' | '.join(labels) + ' |', '|---|---:|' + '---:|' * len(labels)]
    for name, item in common.items():
        values = [f"{item['judges'][label]['mean']:.3f}" if item['judges'][label]['mean'] is not None else '—' for label in labels]
        lines.append('| ' + ' | '.join([name, str(item['cases']), *values]) + ' |')
    lines += ['', '## Paired differences from the self-judge', '', '| Judge / metric | Matched cases | Mean difference | Mean absolute difference | Within 0.10 |', '|---|---:|---:|---:|---:|']
    for label, metrics in paired.items():
        for name, item in metrics.items():
            if item['cases']:
                lines.append(f"| {label} / {name} | {item['cases']} | {item['mean_delta_other_minus_self']:+.3f} | {item['mean_absolute_difference']:.3f} | {item['within_0_10']:.1%} |")
    lines += ['', '## Review and interpretation', '',
              f"{len(disagreements)} cases have an observed score range of at least 0.25 on one or more metrics. This is a preselected triage threshold, not a validated definition of judge error. The top ten appear in review-cases.md with the exact answer, reference and full retrieved excerpts. Development/holdout/category breakdowns are in comparison.json.", '',
              'A stricter judge is not automatically a more accurate judge. Check disagreements against the evidence before declaring a self-judge inflated, an independent judge correct, or averaging their scores into a truth label.', '',
              *['- ' + item for item in result['limitations']]]
    (output_directory / 'comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    review = ['# Judge-disagreement review packet', '', 'These are review candidates, not confirmed system or judge mistakes. Final model outputs are included; hidden reasoning is not recorded.']
    for entry in disagreements[:10]:
        original = baseline[entry['id']]
        review += ['', '## ' + entry['id'], '', '**Question:**', '', literal_block(original['user_input']), '', '**Saved answer:**', '', literal_block(original['response']), '', '**Reference:**', '', literal_block(original['reference']), '', '**Scores:**', '', literal_block(json.dumps(entry['metrics'], indent=2)), '', '**Retrieved excerpts:**']
        for i, context in enumerate(original['retrieved_contexts'], 1):
            review += ['', f'### Excerpt {i}', '', literal_block(context)]
    (output_directory / 'review-cases.md').write_text('\n'.join(review) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-report', type=Path, required=True)
    parser.add_argument('--other', action='append', required=True, help='label=report.json; repeat for each different judge')
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args()
    others = {label: Path(path) for label, path in (item.split('=', 1) for item in args.other)}
    result = compare(args.self_report, others, args.output_directory)
    print(json.dumps({'judges': result['judges'], 'disagreement_cases': len(result['large_disagreements'])}, indent=2))
