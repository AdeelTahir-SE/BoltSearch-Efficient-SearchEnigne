"""Resumable indexing with bounded retries and an operating-system writer lock."""
import os
import time
from contextlib import contextmanager
from pathlib import Path
from embeddings import TransientEmbeddingError


@contextmanager
def indexing_lock(database):
    path = Path(str(Path(database).resolve()) + '.embedding.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if path.stat().st_size == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError('Another embedding worker already owns this database. Wait for it to finish.') from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def build_index(store, embedding, *, on_event=None, sleep=time.sleep, max_attempts=6):
    if not embedding.configured:
        raise ValueError('Configure an embedding provider and model before indexing.')
    local = getattr(embedding, 'provider', '') == 'ollama'
    batch_size = int(os.environ.get('EMBEDDING_BATCH_SIZE', '4' if local else '16'))
    if not 1 <= batch_size <= (4 if local else 128):
        raise ValueError('EMBEDDING_BATCH_SIZE must be 1–4 for Ollama or 1–128 for a cloud provider.')
    failures = completed = 0
    emit = on_event or (lambda event: None)
    while True:
        batch = store.missing(embedding.space, batch_size)
        if not batch:
            status = store.status(embedding.space)
            if status['pendingChunks']:
                raise ValueError('Index still has missing passages but no batch could be selected.')
            emit({'phase': 'complete', **status})
            return {'embedded': completed, **status}
        try:
            vectors = embedding.embed([row['embedding_text'] for row in batch])
        except TransientEmbeddingError as error:
            failures += 1
            if failures >= max_attempts:
                emit({'phase': 'failed', 'attempt': failures, 'error': str(error)})
                raise TransientEmbeddingError(f'Indexing stopped after {max_attempts} consecutive temporary failures. Saved progress is intact; check the embedding provider and resume.') from None
            if local:
                batch_size = max(1, batch_size // 2)
            delay = min(30, 2 ** failures)
            emit({'phase': 'retrying', 'attempt': failures, 'retryInSeconds': delay,
                  'batchSize': batch_size, 'error': str(error)})
            sleep(delay)
            continue
        # Validate and commit only a complete successful batch. Configuration/data errors fail fast.
        store.save_vectors(embedding.space, [row['text_hash'] for row in batch], vectors)
        completed += len(batch)
        failures = 0
        emit({'phase': 'embedding', 'embeddedThisRun': completed, 'batchSize': batch_size,
              **store.status(embedding.space)})
