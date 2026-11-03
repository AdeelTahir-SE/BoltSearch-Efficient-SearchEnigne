import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('search', Path(__file__).resolve().parents[1] / 'search-query/searchDos.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        (self.root / 'barrels').mkdir()
        (self.root / 'DocumentBarrels').mkdir()
        self.write('barrels/0-3999.csv', ['Token_ID', 'Document_IDs'], [
            {'Token_ID': '1#', 'Document_IDs': '1,2,3'}, {'Token_ID': '2', 'Document_IDs': '3'}])
        self.write('DocumentBarrels/barrel_0_to_3999.csv', ['Id', 'Title', 'Score'], [
            {'Id': 1, 'Title': 'First', 'Score': 1}, {'Id': 2, 'Title': 'Best score', 'Score': 100}, {'Id': 3, 'Title': 'Both terms', 'Score': 2}])
    def tearDown(self):
        self.temp.cleanup()
    def write(self, name, fields, rows):
        with (self.root / name).open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    def search(self, query, limit=10):
        return module.search(query, limit, self.root, lambda term: term, lambda term: {'alpha': 1, 'beta': 2}.get(term, 99))
    def test_numeric_tokens_and_rank_before_limit(self):
        self.assertEqual(self.search('alpha', 1)[0]['Id'], 2)
    def test_multiword_and_duplicate_terms(self):
        self.assertEqual(self.search('alpha alpha beta', 1)[0]['Id'], 3)
        self.assertEqual(self.search('alpha alpha beta', 1)[0]['occurrence'], 2)
    def test_empty_results_are_an_array(self):
        self.assertEqual(self.search('unknown'), [])
    def test_missing_dataset_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            module.search('alpha', dataset=self.root / 'missing', normalize=str, tokenize=lambda term: 1)

if __name__ == '__main__':
    unittest.main()
