"""Deterministic answered-question sample, streamed directly from StackSample ZIP."""
import argparse
import csv
import hashlib
import heapq
import io
import json
import os
import time
import zipfile
from pathlib import Path

from indexing import indexing_lock
from store import Store

csv.field_size_limit(16 * 1024 * 1024)


def import_stacksample(archive, database, limit=45000, answers_per_question=2, progress=None):
    emit = progress or (lambda **event: None)
    with indexing_lock(database), zipfile.ZipFile(archive) as source:
        names = {Path(name).name.lower(): name for name in source.namelist()}

        def rows(name):
            with source.open(names[name.lower()]) as stream:
                yield from csv.DictReader(io.TextIOWrapper(stream, encoding='iso-8859-1', newline=''))

        # Only IDs are retained in this pass, never the entire answer corpus.
        eligible = set()
        for number, row in enumerate(rows('Answers.csv'), 1):
            if row.get('Body', '').strip():
                eligible.add(int(row['ParentId']))
            if number % 100000 == 0:
                emit(phase='answer_ids', scanned=number, eligible=len(eligible))
        sample = []
        for number, row in enumerate(rows('Questions.csv'), 1):
            identifier = int(row['Id'])
            if identifier in eligible and row.get('Title', '').strip() and row.get('Body', '').strip():
                priority = int(hashlib.sha256(f'bolt-stacksample-v1:{identifier}'.encode()).hexdigest(), 16)
                item = (-priority, -identifier, row)
                if len(sample) < limit:
                    heapq.heappush(sample, item)
                elif item[:2] > sample[0][:2]:
                    heapq.heapreplace(sample, item)
            if number % 100000 == 0:
                emit(phase='questions', scanned=number, selected=len(sample))
        del eligible
        selected = {int(row['Id']): row for _, _, row in sample}
        del sample
        answers = {identifier: [] for identifier in selected}
        for number, row in enumerate(rows('Answers.csv'), 1):
            parent = int(row['ParentId'])
            if parent in selected and row.get('Body', '').strip():
                bucket = answers[parent]
                bucket.append(row)
                bucket.sort(key=lambda answer: (-int(answer.get('Score') or 0), int(answer['Id'])))
                del bucket[answers_per_question:]
            if number % 100000 == 0:
                emit(phase='answers', scanned=number)
        tags = {identifier: [] for identifier in selected}
        for row in rows('Tags.csv'):
            identifier = int(row['Id'])
            if identifier in tags:
                tags[identifier].append(row['Tag'])
        store = Store(database)
        try:
            imported = skipped = 0
            batch = []
            for identifier in sorted(selected):
                question = selected[identifier]
                batch.append({'id': identifier, 'Title': question['Title'], 'Body': question['Body'],
                              'Answer': ',,,,,'.join(answer['Body'] for answer in answers[identifier]),
                              'Tag': ''.join(f'<{tag}>' for tag in tags[identifier]),
                              'Score': int(question.get('Score') or 0), 'CreationDate': question.get('CreationDate', '')})
                if len(batch) == 100:
                    result = store.ingest(batch)
                    imported += result['indexed']; skipped += result['skipped']; batch = []
                    emit(phase='ingesting', processed=imported + skipped, selected=len(selected))
            if batch:
                result = store.ingest(batch)
                imported += result['indexed']; skipped += result['skipped']
            return {'selected': len(selected), 'indexed': imported, 'skipped': skipped,
                    'answers': sum(len(value) for value in answers.values()), 'chunks': store.status('')['chunks'],
                    'sampling': 'Lowest SHA256(bolt-stacksample-v1:question_id) among questions with nonempty answers; uniform deterministic sample, not tag-balanced.',
                    'answers_per_question': answers_per_question,
                    'answer_order': 'Score descending, answer ID ascending; not accepted-answer status.'}
        finally:
            store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=45000)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100000:
        raise ValueError('Select 1–100,000 questions per staged import.')
    status_path = args.database.parent / 'import-status.json'
    args.database.parent.mkdir(parents=True, exist_ok=True)

    def report(**event):
        state = {'pid': os.getpid(), 'updatedAt': time.time(), **event}
        temporary = status_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
        temporary.replace(status_path)
        print(json.dumps(state), flush=True)

    report(phase='starting')
    try:
        result = import_stacksample(args.archive, args.database, args.limit, progress=report)
        report(phase='complete', **result)
    except Exception as error:
        report(phase='failed', error=type(error).__name__ + ': ' + str(error))
        raise


if __name__ == '__main__':
    main()
