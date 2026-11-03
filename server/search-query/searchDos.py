"""Query all terms in one process, loading each relevant CSV only once."""
import csv
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(16 * 1024 * 1024)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lemmatizer'))


def search(query, limit=10, dataset=None, normalize=None, tokenize=None):
    if normalize is None or tokenize is None:
        from lemmatizerfunctions import lemmatize_word, wordToken
        normalize, tokenize = lemmatize_word, wordToken
    dataset = Path(dataset) if dataset else ROOT / 'dataset'
    inverted, forward = dataset / 'barrels', dataset / 'DocumentBarrels'
    if not inverted.is_dir() or not forward.is_dir():
        raise FileNotFoundError('Search dataset is missing. Import documents or restore server/dataset.')
    terms = list(dict.fromkeys(normalize(term) for term in re.findall(r'\b\w+\b', query.lower())))
    tokens = {str(tokenize(term)) for term in terms}
    matches = defaultdict(set)
    title_matches = defaultdict(set)
    for barrel in sorted(inverted.glob('*.csv')):
        bounds = re.fullmatch(r'(\d+)-(\d+)', barrel.stem)
        if not bounds:
            continue
        lower, upper = map(int, bounds.groups())
        relevant = {token for token in tokens if lower <= int(token) <= upper}
        if not relevant or not barrel.stat().st_size:
            continue
        with barrel.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                token = row['Token_ID'].strip()
                plain = token.rstrip('#')
                if plain not in relevant:
                    continue
                for doc_id in row['Document_IDs'].split(','):
                    doc_id = doc_id.strip()
                    if not doc_id.isdigit():
                        continue
                    matches[int(doc_id)].add(plain)
                    if token.endswith('#'):
                        title_matches[int(doc_id)].add(plain)
    groups = defaultdict(set)
    for doc_id in matches:
        groups[doc_id // 4000 * 4000].add(doc_id)
    results = []
    for start, ids in groups.items():
        barrel = forward / f'barrel_{start}_to_{start + 3999}.csv'
        if not barrel.is_file():
            raise FileNotFoundError(f'Document barrel missing: {barrel.name}')
        with barrel.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                doc_id = int(row.get('Id') or row.get('id'))
                if doc_id not in ids:
                    continue
                try:
                    score = float(row.get('Score') or 0)
                    if not math.isfinite(score):
                        score = 0
                except ValueError:
                    score = 0
                results.append({
                    'Id': doc_id, 'Title': row.get('Title', ''),
                    'Body': row.get('Body', ''), 'Answer': row.get('Answer', ''),
                    'Tag': row.get('Tag', ''), 'Score': score,
                    'CreationDate': row.get('CreationDate', ''),
                    'occurrence': len(matches[doc_id]),
                    'titleMatches': len(title_matches[doc_id]),
                })
    # Rank the entire candidate set before applying the result limit.
    results.sort(key=lambda doc: (-doc['occurrence'], -doc['titleMatches'], -doc['Score'], doc['Id']))
    return results[:limit]


if __name__ == '__main__':
    try:
        print(json.dumps(search(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10), allow_nan=False))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
