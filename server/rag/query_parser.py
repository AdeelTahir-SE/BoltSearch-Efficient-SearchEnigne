"""Conservative deterministic lexical query parsing; semantic intent is unchanged."""
import re

PARSER_VERSION = 'lexical-keywords-v1'
# Keep negations, conditions, comparison words and programming keywords intact.
FILLER = frozenset('a an the according answer answers post question author stored supplied please describe explain tell me what which who how does did do is are was were be been being this that these those it its of to from in on at by as'.split())


def parse_query(query):
    phrases = [value.strip() for match in re.findall(r'`([^`\n]+)`|"([^"\n]+)"', query) for value in match if value.strip()]
    tokens = re.findall(r'[\w]+(?:[.#:/-][\w]+)*(?:\+\+|#)?|\.[A-Za-z]\w*', query, re.UNICODE)
    keywords = [token for token in tokens if token.lower() not in FILLER]
    terms = list(dict.fromkeys(phrases + keywords))[:64]
    # Avoid an accidental empty search for an all-filler or punctuation-only input.
    return {'version': PARSER_VERSION, 'lexical_terms': terms or tokens[:64],
            'semantic_query': query, 'original_query': query}
