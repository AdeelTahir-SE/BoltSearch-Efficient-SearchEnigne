"""Audit the expanded source-grounded set without invoking any models."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import unicodedata

ROOT = Path(__file__).resolve().parent


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def source_ids(row):
    return set(row['relevant_document_ids']) | set(row.get('context_document_ids', []))


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).split())


def validate(database):
    path = ROOT / 'sets/stacksample-50.jsonl'
    rows = read_rows(path)
    assert len(rows) == 50 and len({row['id'] for row in rows}) == 50
    assert Counter(row['category'] for row in rows) == {'direct': 30, 'harder': 10, 'unanswerable': 10}
    assert Counter(row['split'] for row in rows) == {'development': 30, 'holdout': 20}
    by_split = {split: [row for row in rows if row['split'] == split] for split in ('development', 'holdout')}
    assert read_rows(ROOT / 'sets/stacksample-50-dev.jsonl') == by_split['development']
    assert read_rows(ROOT / 'sets/stacksample-50-holdout.jsonl') == by_split['holdout']
    dev_ids = set().union(*(source_ids(row) for row in by_split['development']))
    holdout_ids = set().union(*(source_ids(row) for row in by_split['holdout']))
    assert not dev_ids & holdout_ids, 'Source leakage between development and holdout'
    previous_ids = set()
    for prior in ROOT.glob('*.jsonl'):
        for row in read_rows(prior):
            previous_ids.update(row.get('relevant_document_ids', []))
    assert not (dev_ids | holdout_ids) & previous_ids, 'A source was already used in a previous pilot'
    with sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True) as db:
        for row in rows:
            assert isinstance(row['user_input'], str) and 0 < len(row['user_input']) <= 2000
            assert row['answerable'] == (row['category'] != 'unanswerable')
            if row['answerable']:
                assert row['reference'].strip() and row['relevant_document_ids'] and row['evidence_quotes']
                assert {q['document_id'] for q in row['evidence_quotes']} == set(row['relevant_document_ids'])
            else:
                assert not row['reference'] and not row['relevant_document_ids']
                assert row['unanswerability_reason']
            for identifier in source_ids(row):
                stored = db.execute('SELECT content_hash FROM documents WHERE id=?', (identifier,)).fetchone()
                assert stored and stored[0] == row['source_content_hashes'][str(identifier)], f'Source drift: {identifier}'
            for quote in row.get('evidence_quotes', []):
                passages = db.execute('SELECT text FROM chunks WHERE document_id=? AND section=?', (quote['document_id'], quote['section'])).fetchall()
                assert any(normalized(quote['quote']) in normalized(text) for text, in passages), f'Quote mismatch: {row["id"]}'
            if row.get('absent_marker'):
                assert db.execute('SELECT count(*) FROM documents WHERE instr(payload,?)>0', (row['absent_marker'],)).fetchone()[0] == 0
    manifest = json.loads((ROOT / 'sets/stacksample-50.manifest.json').read_text())
    assert manifest['dataset_file_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    return {'cases': len(rows), 'categories': dict(Counter(row['category'] for row in rows)),
            'splits': dict(Counter(row['split'] for row in rows)), 'reviewed_source_documents': len(dev_ids | holdout_ids),
            'source_overlap_with_prior_pilots': 0, 'development_holdout_source_overlap': 0,
            'source_hashes_and_quotes_valid': True, 'model_calls_made': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.database), indent=2))
