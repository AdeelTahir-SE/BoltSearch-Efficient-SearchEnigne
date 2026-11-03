"""Validated batch ingestion. Forward barrels remain compatible with existing data."""
import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(16 * 1024 * 1024)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lemmatizer'))
from lemmatizerfunctions import lemmatize_word, wordToken
FIELDS = ['Id', 'CreationDate', 'Score', 'Title', 'Body', 'Tag', 'Answer', 'combined_token_ids']


def write_rows(path, fields, rows):
    temporary = path.with_suffix('.tmp')
    try:
        with temporary.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def ingest(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        documents = json.load(stream)
    forward, inverted = ROOT / 'dataset/DocumentBarrels', ROOT / 'dataset/barrels'
    forward.mkdir(parents=True, exist_ok=True)
    inverted.mkdir(parents=True, exist_ok=True)
    groups = defaultdict(list)
    for document in documents:
        groups[document['id'] // 4000 * 4000].append(document)
    planned_forward, postings = [], defaultdict(set)
    indexed = skipped = 0
    for start, docs in groups.items():
        barrel = forward / f'barrel_{start}_to_{start + 3999}.csv'
        rows = []
        if barrel.exists() and barrel.stat().st_size:
            with barrel.open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.DictReader(stream))
            for row in rows:
                row['Id'] = row.pop('id', row.get('Id', ''))
        existing = {int(row['Id']) for row in rows}
        for doc in docs:
            if doc['id'] in existing:
                skipped += 1
                continue
            tokens = set()
            for field, suffix in [('Title', '#'), ('Tag', '')]:
                for term in re.findall(r'\b\w+\b', (doc.get(field) or '').lower()):
                    tokens.add(f'{wordToken(lemmatize_word(term))}{suffix}')
            row = {field: doc.get(field) if doc.get(field) is not None else '' for field in FIELDS}
            row['Id'], row['combined_token_ids'] = doc['id'], ', '.join(sorted(tokens))
            rows.append(row)
            existing.add(doc['id'])
            indexed += 1
            for token in tokens:
                postings[token].add(str(doc['id']))
        planned_forward.append((barrel, rows))
    # Compute all tokenization before writing, so missing NLTK data cannot half-import a batch.
    barrel_postings = defaultdict(dict)
    ranges = []
    for barrel in inverted.glob('*.csv'):
        match = re.fullmatch(r'(\d+)-(\d+)', barrel.stem)
        if match:
            ranges.append((*map(int, match.groups()), barrel))
    for token, ids in postings.items():
        number = int(token.rstrip('#'))
        barrel = next((path for lower, upper, path in sorted(ranges) if lower <= number <= upper), None)
        if barrel is None:
            start = number // 4000 * 4000
            # Exact singleton ranges avoid overlapping legacy nonuniform ranges.
            if any(lower <= start + 3999 and upper >= start for lower, upper, _ in ranges):
                start = number
                end = number
            else:
                end = start + 3999
            barrel = inverted / f'{start}-{end}.csv'
            ranges.append((start, end, barrel))
        barrel_postings[barrel][token] = ids
    for barrel, rows in planned_forward:
        write_rows(barrel, FIELDS, [{key: row.get(key, '') for key in FIELDS} for row in rows])
    for barrel, additions in barrel_postings.items():
        rows = {}
        if barrel.exists() and barrel.stat().st_size:
            with barrel.open(encoding='utf-8-sig', newline='') as stream:
                rows = {row['Token_ID']: set(row['Document_IDs'].split(',')) for row in csv.DictReader(stream)}
        for token, ids in additions.items():
            rows.setdefault(token, set()).update(ids)
        write_rows(barrel, ['Token_ID', 'Document_IDs'], [{'Token_ID': token, 'Document_IDs': ','.join(sorted(ids))} for token, ids in sorted(rows.items())])
    return {'indexed': indexed, 'skipped': skipped}


if __name__ == '__main__':
    try:
        print(json.dumps(ingest(sys.argv[1])))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
