import { DatabaseSync } from 'node:sqlite';
import { fileURLToPath } from 'node:url';
const cache = new Map();
const defaultDatabase = fileURLToPath(new URL('../dataset/rag.sqlite3', import.meta.url));
export function searchDocuments({ query, limit, page }, database = process.env.RAG_DB_PATH || defaultDatabase) {
  const db = new DatabaseSync(database, { readOnly: true });
  try {
    db.exec('PRAGMA busy_timeout=3000; BEGIN');
    const revision = db.prepare("SELECT value FROM metadata WHERE key='revision'").get().value;
    const terms = [...new Set(query.toLowerCase().match(/[\p{L}\p{N}_]+/gu) || [])].slice(0,64);
    const key = JSON.stringify([database,revision,terms,limit,page]);
    const hit = cache.get(key);
    if (hit && hit.expires > Date.now()) return hit.result;
    let rows = [];
    if (terms.length) {
      const expression = terms.map(term => '"' + term.replaceAll('"','""') + '"').join(' OR ');
      rows = db.prepare(`WITH scored AS MATERIALIZED (
        SELECT rowid AS chunk_id,bm25(chunks_fts,4,2,1) AS score FROM chunks_fts WHERE chunks_fts MATCH ?
      ), ranked AS (
        SELECT c.document_id,min(s.score) AS score FROM scored s JOIN chunks c INDEXED BY chunks_search_mapping ON c.id=s.chunk_id GROUP BY c.document_id
      ) SELECT d.payload FROM ranked r JOIN documents d ON d.id=r.document_id
        ORDER BY r.score,r.document_id LIMIT ? OFFSET ?`).all(expression,limit+1,(page-1)*limit);
    }
    const result = {documents:rows.slice(0,limit).map(row=>JSON.parse(row.payload)),hasMore:rows.length>limit,page};
    if (cache.size >= 100) cache.delete(cache.keys().next().value);
    cache.set(key,{result,expires:Date.now()+30000});
    return result;
  } finally { db.close(); }
}
