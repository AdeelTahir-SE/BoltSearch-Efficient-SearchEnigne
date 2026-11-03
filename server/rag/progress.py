"""Read-only progress for the currently configured embedding space."""
import json
import os
import sqlite3
from pathlib import Path
from embeddings import Embeddings


def progress():
    embedding = Embeddings()
    path = Path(os.environ.get('RAG_DB_PATH') or Path(__file__).resolve().parents[1] / 'dataset/rag.sqlite3').resolve()
    result = {'databaseExists': path.is_file(), 'semanticConfigured': embedding.configured,
              'embeddingProvider': embedding.provider, 'embeddingModel': embedding.model,
              'embeddingSpace': embedding.space}
    if not path.is_file():
        return result
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=15) as db:
        db.execute('BEGIN')
        total = db.execute('SELECT count(*) FROM chunks').fetchone()[0]
        embedded = db.execute('SELECT count(*) FROM chunks c JOIN embeddings e ON c.text_hash=e.text_hash WHERE e.space=?', (embedding.space,)).fetchone()[0]
        result.update({'documents': db.execute('SELECT count(*) FROM documents').fetchone()[0],
                       'chunks': total, 'embeddedChunks': embedded, 'pendingChunks': total - embedded,
                       'percent': round(100 * embedded / total, 2) if total else 0,
                       'complete': bool(total and embedding.configured and total == embedded)})
    return result


if __name__ == '__main__':
    print(json.dumps(progress()))
