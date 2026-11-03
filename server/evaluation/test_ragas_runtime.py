"""Real Ragas metric execution with a deterministic in-process judge; no API calls."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ['RAGAS_DO_NOT_TRACK'] = 'true'
from score import score_rows
from ragas.llms.base import InstructorBaseRagasLLM


def fixture(schema, root, field=''):
    if '$ref' in schema:
        return fixture(root['$defs'][schema['$ref'].split('/')[-1]], root, field)
    if 'anyOf' in schema:
        return fixture(next(item for item in schema['anyOf'] if item.get('type') != 'null'), root, field)
    if schema.get('type') == 'object':
        return {key: fixture(value, root, key) for key, value in schema.get('properties', {}).items()}
    if schema.get('type') == 'array':
        return [fixture(schema['items'], root, field)]
    if 'enum' in schema:
        return schema['enum'][0]
    if schema.get('type') in ('integer', 'number'):
        return 0 if 'noncommittal' in field else 1
    if schema.get('type') == 'boolean':
        return 'noncommittal' not in field
    return 'The documented value is seven.'


class FakeJudge(InstructorBaseRagasLLM):
    def generate(self, prompt, response_model):
        schema = response_model.model_json_schema()
        return response_model(**fixture(schema, schema))

    async def agenerate(self, prompt, response_model):
        return self.generate(prompt, response_model)


class RuntimeTest(unittest.TestCase):
    def test_all_four_real_metrics_and_abstention_reporting_without_network(self):
        env = {'EVAL_JUDGE_API_KEY': 'local-fake', 'EVAL_JUDGE_MODEL': 'fake-judge',
               'EMBEDDING_PROVIDER': 'ollama', 'EMBEDDING_MODEL': 'fake-local',
               'EMBEDDING_BASE_URL': 'http://127.0.0.1:11434'}
        base = {'id': 'answer', 'user_input': 'What is the documented value?', 'response': 'The documented value is seven.',
                'reference': 'The documented value is seven.', 'answerable': True, 'generation_status': 'answered',
                'retrieved_contexts': ['The documented value is seven.'], 'retrieved_document_ids': [1],
                'relevant_document_ids': [1], 'answer_model': 'generator'}
        negative = {**base, 'id': 'abstain', 'answerable': False, 'reference': '', 'relevant_document_ids': [],
                    'generation_status': 'insufficient_evidence'}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            output = Path(directory) / 'scores.json'
            with patch.dict(os.environ, env), patch('ragas.llms.llm_factory', return_value=FakeJudge()) as factory, patch('embeddings.Embeddings.embed', side_effect=lambda texts, query=False: [[1.0, 0.0] for _ in texts]):
                report = asyncio.run(score_rows([base, negative], output,
                    ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall'], 30, concurrency=2, judge_max_tokens=4096))
            self.assertEqual(factory.call_args.kwargs['max_tokens'], 4096)
            self.assertEqual(report['judge_max_tokens'], 4096)
            self.assertEqual(report['summary']['metric_errors'], 0, report['results'])
            self.assertEqual(report['summary']['correct_abstentions'], 1)
            self.assertTrue(report['scoring_complete'])
            self.assertEqual([row['id'] for row in report['results']], ['answer', 'abstain'])
            for name in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']:
                self.assertAlmostEqual(report['results'][0]['scores'][name], 1.0, places=5)
                self.assertIsNone(report['results'][1]['scores'][name])
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['summary']['cases'], 2)


if __name__ == '__main__':
    unittest.main()
