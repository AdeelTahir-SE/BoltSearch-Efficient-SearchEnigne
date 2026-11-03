import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

fake = types.ModuleType('lemmatizerfunctions')
fake.lemmatize_word = lambda word: word
fake.wordToken = lambda word: sum(map(ord, word))
spec = importlib.util.spec_from_file_location('ingestion', Path(__file__).resolve().parents[1] / 'file-upload/uploadFile.py')
ingestion = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'lemmatizerfunctions': fake}):
    spec.loader.exec_module(ingestion)
search_spec = importlib.util.spec_from_file_location('retrieval', Path(__file__).resolve().parents[1] / 'search-query/searchDos.py')
retrieval = importlib.util.module_from_spec(search_spec)
search_spec.loader.exec_module(retrieval)

class IngestionTests(unittest.TestCase):
    def test_batch_across_barrels_indexes_every_document_and_skips_duplicates(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            root = Path(directory)
            source = root / 'batch.json'
            source.write_text(json.dumps([{'id': 1, 'Title': 'alpha', 'Body': 'Unicode: café'}, {'id': 4001, 'Title': 'beta'}]), encoding='utf-8')
            with patch.object(ingestion, 'ROOT', root):
                self.assertEqual(ingestion.ingest(source), {'indexed': 2, 'skipped': 0})
                self.assertEqual(ingestion.ingest(source), {'indexed': 0, 'skipped': 2})
            for term, expected in [('alpha', 1), ('beta', 4001)]:
                docs = retrieval.search(term, dataset=root / 'dataset', normalize=str, tokenize=fake.wordToken)
                self.assertEqual(docs[0]['Id'], expected)
            self.assertEqual(retrieval.search('alpha', dataset=root / 'dataset', normalize=str, tokenize=fake.wordToken)[0]['Body'], 'Unicode: café')

if __name__ == '__main__':
    unittest.main()
