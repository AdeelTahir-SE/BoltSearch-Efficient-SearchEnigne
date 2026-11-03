"""Import only the selected CSV split, directly from a ZIP without extraction."""
import csv
import io
import zipfile
from pathlib import Path


def import_archive(store, archive, split='train.csv', progress=None):
    indexed = skipped = rows = 0
    with zipfile.ZipFile(Path(archive)) as source:
        if split not in source.namelist():
            raise ValueError(f'Archive does not contain {split}.')
        with source.open(split) as stream:
            reader = csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig', newline=''))
            if not {'Id', 'Title', 'Body'}.issubset(reader.fieldnames or []):
                raise ValueError('CSV needs Id, Title and Body columns.')
            batch = []
            for row in reader:
                # Y is a question-quality label, not an answer; never fabricate answer evidence.
                document = {'id': int(row['Id']), 'Title': row['Title'], 'Body': row['Body'],
                            'Tag': row.get('Tags', row.get('Tag', '')), 'CreationDate': row.get('CreationDate', ''),
                            'Answer': row.get('Answer', '')}
                batch.append(document)
                rows += 1
                if len(batch) == 250:
                    result = store.ingest(batch)
                    indexed += result['indexed']; skipped += result['skipped']
                    batch = []
                    if progress:
                        progress(rows)
            if batch:
                result = store.ingest(batch)
                indexed += result['indexed']; skipped += result['skipped']
    return {'indexed': indexed, 'skipped': skipped, 'rows': rows, 'split': split}
