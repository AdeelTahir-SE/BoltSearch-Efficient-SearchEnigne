"""Transactional BM25/chunk/vector storage. No external database or NLP downloads."""
import hashlib
import heapq
import json
import math
import re
import sqlite3
import struct
import time
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        elif not self.hidden and tag in ('p', 'br', 'div', 'li', 'pre', 'h1', 'h2', 'h3'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden:
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value):
    parser = TextExtractor()
    parser.feed(str(value or ''))
    return re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()


def chunks(text, size=1200, overlap=180):
    """Character-bounded chunks; Unicode and code survive, with word boundaries."""
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(' ', start + size // 2, end)
            if boundary > start:
                end = boundary
        yield text[start:end], start, end
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
        while start < end and start > 0 and not text[start - 1].isspace():
            start += 1


def fingerprint(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def normalize(vector):
    if not isinstance(vector, list) or not vector or len(vector) > 32768:
        raise ValueError('Invalid embedding vector shape.')
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector):
        raise ValueError('Embeddings must contain finite numbers.')
    norm = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(norm) or norm == 0:
        raise ValueError('Embedding vector has zero or invalid magnitude.')
    return [value / norm for value in vector]


def fuse(lexical, semantic, limit=8, k=60):
    scores, reasons = {}, {}
    for name, ranking in [('bm25', lexical), ('semantic', semantic)]:
        for rank, chunk_id in enumerate(ranking, 1):
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank)
            reasons.setdefault(chunk_id, []).append(name)
    ranked = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))[:limit]
    return [(chunk_id, scores[chunk_id], reasons[chunk_id]) for chunk_id in ranked]


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY, payload TEXT NOT NULL, content_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                title TEXT NOT NULL, tags TEXT NOT NULL, text TEXT NOT NULL, section TEXT NOT NULL,
                ordinal INTEGER NOT NULL, start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
                embedding_text TEXT NOT NULL, text_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS chunks_search_mapping ON chunks(id,document_id);
            CREATE INDEX IF NOT EXISTS chunks_hash ON chunks(text_hash);
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                title, tags, text, content='chunks', content_rowid='id', tokenize='porter unicode61'
            );
            CREATE TRIGGER IF NOT EXISTS chunks_insert AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid,title,tags,text) VALUES(new.id,new.title,new.tags,new.text);
            END;
            CREATE TRIGGER IF NOT EXISTS chunks_delete AFTER DELETE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts,rowid,title,tags,text) VALUES('delete',old.id,old.title,old.tags,old.text);
            END;
            CREATE TABLE IF NOT EXISTS embeddings (
                space TEXT NOT NULL, text_hash TEXT NOT NULL, dimensions INTEGER NOT NULL, vector BLOB NOT NULL,
                PRIMARY KEY(space,text_hash)
            );
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS query_embeddings (
                space TEXT NOT NULL, query_hash TEXT NOT NULL, dimensions INTEGER NOT NULL,
                vector BLOB NOT NULL, expires REAL NOT NULL, PRIMARY KEY(space,query_hash)
            );
            INSERT OR IGNORE INTO metadata VALUES('revision',0);
        ''')

    def close(self):
        self.db.close()

    def ingest(self, documents):
        indexed = skipped = 0
        with self.db:
            for doc in documents:
                doc_id = doc.get('id', doc.get('Id'))
                if isinstance(doc_id, bool) or not isinstance(doc_id, int) or not 0 <= doc_id <= 9007199254740991:
                    raise ValueError('Document id must be a nonnegative safe integer.')
                if not isinstance(doc.get('Title'), str) or not doc['Title'].strip():
                    raise ValueError('Document Title is required.')
                payload = {key: doc.get(key, '') for key in ('Title', 'Body', 'Answer', 'Tag', 'Score', 'CreationDate')}
                payload['Id'] = doc_id
                content = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
                digest = fingerprint(content)
                previous = self.db.execute('SELECT content_hash FROM documents WHERE id=?', (doc_id,)).fetchone()
                if previous and previous[0] == digest:
                    skipped += 1
                    continue
                self.db.execute('DELETE FROM chunks WHERE document_id=?', (doc_id,))
                self.db.execute('INSERT INTO documents VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,content_hash=excluded.content_hash', (doc_id, content, digest))
                title = plain_text(doc['Title'])[:500]
                tags = re.sub(r'[<>]', ' ', str(doc.get('Tag') or ''))[:2000]
                sections = [('question', plain_text(doc.get('Body')))]
                sections.extend((f'answer {index + 1}', plain_text(answer)) for index, answer in enumerate(str(doc.get('Answer') or '').split(',,,,,')) if plain_text(answer))
                if not any(text for _, text in sections):
                    sections = [('title', title)]
                for section, text in sections:
                    for ordinal, (part, start, end) in enumerate(chunks(text)):
                        embedding_text = f'{title}\n{tags}\n{section}: {part}'
                        self.db.execute('''INSERT INTO chunks(document_id,title,tags,text,section,ordinal,start_offset,end_offset,embedding_text,text_hash)
                            VALUES(?,?,?,?,?,?,?,?,?,?)''', (doc_id, title, tags, part, section, ordinal, start, end, embedding_text, fingerprint(embedding_text)))
                indexed += 1
            if indexed:
                self.bump_revision()
        return {'indexed': indexed, 'skipped': skipped}

    def bump_revision(self):
        self.db.execute("UPDATE metadata SET value=value+1 WHERE key='revision'")

    def status(self, space):
        total = self.db.execute('SELECT count(*) FROM chunks').fetchone()[0]
        embedded = self.db.execute('SELECT count(*) FROM chunks c JOIN embeddings e ON e.text_hash=c.text_hash AND e.space=?', (space,)).fetchone()[0] if space else 0
        return {'documents': self.db.execute('SELECT count(*) FROM documents').fetchone()[0], 'chunks': total,
                'embeddedChunks': embedded, 'pendingChunks': total - embedded,
                'revision': self.db.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()[0]}

    def missing(self, space, limit=32):
        return self.db.execute('''SELECT DISTINCT c.text_hash,c.embedding_text FROM chunks c
            LEFT JOIN embeddings e ON e.text_hash=c.text_hash AND e.space=?
            WHERE e.text_hash IS NULL LIMIT ?''', (space, limit)).fetchall()

    def save_vectors(self, space, hashes, vectors):
        if len(hashes) != len(vectors):
            raise ValueError('Embedding count does not match input count.')
        normalized = [normalize(vector) for vector in vectors]
        dimensions = {len(vector) for vector in normalized}
        existing = self.db.execute('SELECT dimensions FROM embeddings WHERE space=? LIMIT 1', (space,)).fetchone()
        if len(dimensions) != 1 or (existing and existing[0] not in dimensions):
            raise ValueError('Embedding dimensions changed. Use a new model/version and reindex.')
        with self.db:
            for digest, vector in zip(hashes, normalized):
                self.db.execute('INSERT OR REPLACE INTO embeddings VALUES(?,?,?,?)', (space, digest, len(vector), struct.pack(f'<{len(vector)}f', *vector)))
            self.bump_revision()

    def lexical(self, query, limit=40, terms=None):
        terms = list(dict.fromkeys(re.findall(r'\w+', query.lower(), re.UNICODE)))[:64] if terms is None else terms
        if not terms:
            return []
        expression = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms)
        return [row[0] for row in self.db.execute('SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts,4,2,1),rowid LIMIT ?', (expression, limit))]

    def search_documents(self, query, limit=10, page=1):
        terms = list(dict.fromkeys(re.findall(r'\w+', query.lower(), re.UNICODE)))[:64]
        if not terms:
            return {'documents': [], 'hasMore': False, 'page': page}
        expression = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms)
        rows = self.db.execute("""WITH scored AS MATERIALIZED (
            SELECT rowid AS chunk_id,bm25(chunks_fts,4,2,1) AS score
            FROM chunks_fts WHERE chunks_fts MATCH ?
        ), ranked AS (
            SELECT c.document_id,min(s.score) AS score FROM scored s
            JOIN chunks c ON c.id=s.chunk_id GROUP BY c.document_id
        ) SELECT document_id FROM ranked ORDER BY score,document_id LIMIT ? OFFSET ?""",
            (expression, limit + 1, (page - 1) * limit)).fetchall()
        return {'documents': [self.document(row['document_id']) for row in rows[:limit]],
                'hasMore': len(rows) > limit, 'page': page}

    def cached_query(self, space, query):
        row = self.db.execute('SELECT dimensions,vector FROM query_embeddings WHERE space=? AND query_hash=? AND expires>?', (space, fingerprint(query), time.time())).fetchone()
        return list(struct.unpack(f"<{row['dimensions']}f", row['vector'])) if row else None

    def cache_query(self, space, query, vector):
        vector = normalize(vector)
        with self.db:
            self.db.execute('DELETE FROM query_embeddings WHERE expires<=?', (time.time(),))
            self.db.execute('INSERT OR REPLACE INTO query_embeddings VALUES(?,?,?,?,?)', (space, fingerprint(query), len(vector), struct.pack(f'<{len(vector)}f', *vector), time.time() + 300))
            self.db.execute('DELETE FROM query_embeddings WHERE rowid IN (SELECT rowid FROM query_embeddings ORDER BY expires DESC LIMIT -1 OFFSET 500)')

    def semantic(self, space, vector, limit=40, minimum=0.25):
        query = normalize(vector)
        def candidates():
            rows = self.db.execute('SELECT c.id,e.dimensions,e.vector FROM chunks c JOIN embeddings e ON c.text_hash=e.text_hash WHERE e.space=?', (space,))
            try:
                import numpy as np
            except ImportError:
                np = None
            if np is None:
                for row in rows:
                    if row['dimensions'] != len(query):
                        raise ValueError('Query embedding dimensions do not match the index.')
                    stored = struct.unpack(f'<{len(query)}f', row['vector'])
                    score = sum(a * b for a, b in zip(query, stored))
                    if score >= minimum:
                        yield score, -row['id']
                return
            # Bound memory while preserving exhaustive cosine ranking and float64 arithmetic.
            query_array = np.asarray(query, dtype=np.float64)
            while batch := rows.fetchmany(256):
                if any(row['dimensions'] != len(query) for row in batch):
                    raise ValueError('Query embedding dimensions do not match the index.')
                matrix = np.stack([np.frombuffer(row['vector'], dtype='<f4') for row in batch]).astype(np.float64)
                scores = np.einsum('ij,j->i', matrix, query_array)
                for row, score in zip(batch, scores):
                    if score >= minimum:
                        yield float(score), -row['id']
        return [-negative_id for _, negative_id in heapq.nlargest(limit, candidates())]

    def sources(self, ranking):
        result = []
        # Limit repeated chunks from the same document so one long file cannot occupy every citation.
        per_document = {}
        for chunk_id, score, methods in ranking:
            row = self.db.execute('SELECT * FROM chunks WHERE id=?', (chunk_id,)).fetchone()
            if per_document.get(row['document_id'], 0) >= 2:
                continue
            per_document[row['document_id']] = per_document.get(row['document_id'], 0) + 1
            result.append({'id': len(result) + 1, 'chunkId': chunk_id, 'documentId': row['document_id'],
                           'title': row['title'], 'text': row['text'], 'section': row['section'],
                           'startOffset': row['start_offset'], 'endOffset': row['end_offset'],
                           'score': score, 'methods': methods})
        return result

    def document(self, doc_id):
        row = self.db.execute('SELECT payload FROM documents WHERE id=?', (doc_id,)).fetchone()
        return json.loads(row[0]) if row else None


@contextmanager
def open_store(path):
    store = Store(path)
    try:
        yield store
    finally:
        store.close()
