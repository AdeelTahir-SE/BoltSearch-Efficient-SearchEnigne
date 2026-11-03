import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rag'))
from query_parser import parse_query
from store import Store
from worker import retrieve


class QueryParserTests(unittest.TestCase):
    def test_preserves_intent_technical_identifiers_and_literals(self):
        query = 'According to the answer, how does C++ differ from C# without .NET before version 2.5 using `a or b`?'
        parsed = parse_query(query)
        self.assertEqual(parsed['semantic_query'], query)
        for token in ('C++', 'C#', '.NET', 'without', 'before', '2.5', 'a or b'):
            self.assertIn(token, parsed['lexical_terms'])
        self.assertNotIn('According', parsed['lexical_terms'])

    def test_keeps_negation_and_falls_back_for_filler_only(self):
        self.assertIn('not', parse_query('What is not available?')['lexical_terms'])
        self.assertTrue(parse_query('what is the')['lexical_terms'])
        self.assertEqual(parse_query('???')['lexical_terms'], [])

    def test_parser_mode_is_opt_in_and_fts_syntax_is_escaped(self):
        class NoEmbeddings:
            configured = False
            space = ''
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            store = Store(Path(folder) / 'test.sqlite3')
            try:
                store.ingest([{'id': 1, 'Title': 'Python dictionaries', 'Body': 'A dictionary maps keys to values.'}])
                baseline = retrieve(store, NoEmbeddings(), 'Which dictionary maps keys?', mode='bm25')
                parsed = retrieve(store, NoEmbeddings(), 'Which dictionary maps keys?', mode='bm25', query_parsing='on')
                self.assertEqual(baseline['retrieval']['query_parsing'], 'off')
                self.assertIsNone(baseline['retrieval']['parsed_query'])
                self.assertEqual(parsed['sources'][0]['documentId'], 1)
                retrieve(store, NoEmbeddings(), '"dictionary" OR -- *', mode='bm25', query_parsing='on')
                with self.assertRaises(ValueError):
                    retrieve(store, NoEmbeddings(), 'dictionary', query_parsing='invalid')
            finally:
                store.close()


if __name__ == '__main__':
    unittest.main()
