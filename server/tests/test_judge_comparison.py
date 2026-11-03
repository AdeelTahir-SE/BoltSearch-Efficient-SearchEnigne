import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evaluation'))
from compare_judges import compare, METRICS


class JudgeComparisonTests(unittest.TestCase):
    def fixture(self, model):
        rows = []
        for number in range(3):
            answerable = number < 2
            rows.append({'id': str(number), 'user_input': 'Question ' + str(number), 'response': 'Fixed answer',
                         'reference': 'Reference' if answerable else '', 'answerable': answerable,
                         'generation_status': 'answered' if answerable else 'insufficient_evidence',
                         'retrieved_contexts': ['Stored evidence'], 'retrieved_document_ids': [1],
                         'relevant_document_ids': [1] if answerable else [], 'answer_model': 'generator',
                         'case_hash': str(number), 'prompt_policy_hash': 'same', 'embedding_space': 'same', 'index_revision': 1,
                         'split': 'holdout' if number == 1 else 'development', 'category': 'direct' if answerable else 'unanswerable',
                         'scores': {name: 1.0 if answerable else None for name in METRICS}, 'metric_errors': {}})
        return {'results': rows, 'scoring_complete': True, 'judge_model': model, 'judge_matches_answer_model': model == 'generator',
                'ragas_version': 'same', 'evaluation_embedding_model': 'same'}

    def test_common_case_means_errors_and_identity_guards(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder)
            baseline, other = self.fixture('generator'), self.fixture('different')
            baseline['judge_max_tokens'] = other['judge_max_tokens'] = 4096
            other['results'][0]['scores']['faithfulness'] = .5
            other['results'][1]['scores']['faithfulness'] = None
            other['results'][1]['metric_errors']['faithfulness'] = 'TimeoutError'
            paths = [root / 'self.json', root / 'other.json']
            for path, report in zip(paths, [baseline, other]):
                path.write_text(json.dumps(report), encoding='utf-8')
            result = compare(paths[0], {'other': paths[1]}, root / 'out', expected_cases=3)
            self.assertEqual(result['judge_max_tokens'], 4096)
            self.assertEqual(result['common_scored_cases']['faithfulness']['cases'], 1)
            self.assertEqual(result['paired_vs_self']['other']['faithfulness']['mean_delta_other_minus_self'], -.5)
            self.assertEqual(result['judges']['other']['metric_errors'], 1)
            self.assertEqual(result['fixed_generation_outcomes']['accepted_answerable'], 2)
            self.assertTrue((root / 'out/review-cases.md').exists())
            other['results'][0]['response'] = 'Regenerated answer'
            paths[1].write_text(json.dumps(other), encoding='utf-8')
            with self.assertRaises(AssertionError):
                compare(paths[0], {'other': paths[1]}, root / 'invalid', expected_cases=3)
            other['results'][0]['response'] = 'Fixed answer'
            other['judge_max_tokens'] = 2048
            paths[1].write_text(json.dumps(other), encoding='utf-8')
            with self.assertRaises(AssertionError):
                compare(paths[0], {'other': paths[1]}, root / 'mixed-budgets', expected_cases=3)


if __name__ == '__main__':
    unittest.main()
