import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rag'))
from import_stacksample import import_stacksample
from store import Store


class StackSampleTests(unittest.TestCase):
    def test_join_answer_ranking_sampling_and_resume(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder)
            archive = root / 'sample.zip'
            tables = {
                'Questions.csv': [['Id', 'Title', 'Body', 'Score'],
                                  [1, 'Question one', 'First question', 0],
                                  [2, 'Question two', 'Second question', 1],
                                  [3, 'No answers', 'Absent answer', 0]],
                'Answers.csv': [['Id', 'ParentId', 'Score', 'Body'],
                                [10, 1, 1, 'Low answer'], [11, 1, 8, 'Best answer'],
                                [12, 1, 3, 'Second answer'], [13, 2, 1, 'Another answer']],
                'Tags.csv': [['Id', 'Tag'], [1, 'python'], [2, 'java']]}
            with zipfile.ZipFile(archive, 'w') as z:
                for name, data in tables.items():
                    stream = io.StringIO(); csv.writer(stream).writerows(data)
                    z.writestr(name, stream.getvalue().encode('iso-8859-1'))
            database = root / 'index.sqlite3'
            first = import_stacksample(archive, database, limit=2)
            self.assertEqual(first['selected'], 2)
            self.assertEqual(first['answers'], 3)
            store = Store(database)
            try:
                self.assertEqual(store.document(1)['Answer'], 'Best answer,,,,,Second answer')
                self.assertEqual(store.document(1)['Tag'], '<python>')
                self.assertIsNone(store.document(3))
            finally:
                store.close()
            resumed = import_stacksample(archive, database, limit=2)
            self.assertEqual(resumed['indexed'], 0)
            self.assertEqual(resumed['skipped'], 2)


if __name__ == '__main__':
    unittest.main()
