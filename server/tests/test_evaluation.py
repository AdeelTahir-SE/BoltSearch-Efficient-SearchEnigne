import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('evaluation_score', ROOT / 'evaluation/score.py')
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


class EvaluationTests(unittest.TestCase):
    def test_known_source_ranking_deduplicates_documents(self):
        score = scorer.retrieval_metrics([9, 9, 2, 3], [2, 3])
        self.assertEqual(score['known_source_recall'], 1)
        self.assertEqual(score['known_source_mrr'], 0.5)
        self.assertLess(score['known_source_ndcg'], 1)

    def test_no_gold_does_not_become_a_perfect_retrieval_score(self):
        self.assertTrue(all(value is None for value in scorer.retrieval_metrics([1], []).values()))
        self.assertTrue(all(value == 0 for value in scorer.retrieval_metrics([], [1]).values()))

    def test_nonfinite_metric_values_are_not_reported_as_zero(self):
        self.assertIsNone(scorer.finite_score(math.nan))
        self.assertIsNone(scorer.finite_score(math.inf))
        self.assertIsNone(scorer.finite_score(True))
        self.assertEqual(scorer.finite_score(0.7), 0.7)

    def test_abstention_is_reported_separately_from_answer_quality(self):
        rows = [{'answerable': True, 'generation_status': 'answered', 'scores': {'faithfulness': 0.8}},
                {'answerable': False, 'generation_status': 'insufficient_evidence', 'scores': {'faithfulness': None}}]
        result = scorer.summarize(rows)
        self.assertEqual(result['metrics']['faithfulness'], {'mean': 0.8, 'scored_cases': 1})
        self.assertEqual(result['correct_abstentions'], 1)

    def test_malformed_capture_is_rejected_before_model_calls(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            path = Path(directory) / 'bad.jsonl'
            path.write_text(json.dumps({'id': 'bad', 'user_input': 'Question', 'response': 'Answer', 'answerable': True, 'retrieved_contexts': 'not an array'}), encoding='utf-8')
            with self.assertRaises(ValueError):
                scorer.load_rows(path, 5)


if __name__ == '__main__':
    unittest.main()
