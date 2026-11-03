import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evaluation'))
from compare_parsing import compare
from score import summarize


class ParsingComparisonTests(unittest.TestCase):
    def report(self, arm):
        cases = [json.loads(line) for line in (Path(__file__).resolve().parents[1] / 'evaluation/sets/stacksample-50.jsonl').read_text(encoding='utf-8').splitlines()]
        names = ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall', 'known_source_recall', 'known_source_mrr', 'known_source_ndcg']
        rows = [{**case, 'query_parsing': arm, 'parsed_query': {'semantic_query': case['user_input']},
                 'case_hash': case['id'], 'prompt_policy_hash': 'same', 'parser_hash': 'same', 'embedding_space': 'same',
                 'index_revision': 1, 'answer_model': 'same', 'generation_status': 'answered' if case['answerable'] else 'insufficient_evidence',
                 'duration_seconds': 1, 'retrieved_document_ids': case['relevant_document_ids'],
                 'scores': {name: 1.0 if case['answerable'] else None for name in names}, 'metric_errors': {}}
                for case in cases]
        return {'scoring_complete': True, 'summary': summarize(rows), 'results': rows,
                'judge_model': 'same', 'judge_matches_answer_model': True}

    def test_paired_report_keeps_false_positive_negatives_out_of_answerable_coverage(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder)
            off, on = self.report('off'), self.report('on')
            negative = next(row for row in on['results'] if not row['answerable'])
            negative['generation_status'] = 'answered'
            on['summary'] = summarize(on['results'])
            paths = [root / 'off.json', root / 'on.json']
            for path, report in zip(paths, [off, on]):
                path.write_text(json.dumps(report), encoding='utf-8')
            result = compare(*paths, root / 'comparison.json')
            self.assertEqual(result['groups']['all']['on']['accepted_answerable_cases'], 40)
            self.assertEqual(result['groups']['all']['on']['unsupported_answers'], 1)
            self.assertEqual(result['groups']['holdout']['off']['cases'], 20)
            self.assertEqual(result['paired_metric_deltas']['faithfulness']['paired_scored_cases'], 40)
            on['results'][0]['embedding_space'] = 'different'
            paths[1].write_text(json.dumps(on), encoding='utf-8')
            with self.assertRaises(AssertionError):
                compare(*paths, root / 'invalid.json')


if __name__ == '__main__':
    unittest.main()
