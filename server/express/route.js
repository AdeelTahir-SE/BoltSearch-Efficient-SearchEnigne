import { Router } from 'express';
import { searchDocuments } from './search.js';
import { mkdir, readFile, rm } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import multer from 'multer';
import { runRag, askDocuments, embedDocuments, chatConfig, backgroundIndexing } from './rag.js';

const uploadPath = fileURLToPath(new URL('../file-upload/uploads/', import.meta.url));
const upload = multer({
  storage: multer.diskStorage({
    destination: (req, file, cb) => { mkdir(uploadPath, { recursive: true }).then(() => cb(null, uploadPath), cb); },
    filename: (req, file, cb) => cb(null, `${randomUUID()}.json`),
  }),
  limits: { fileSize: 10 * 1024 * 1024, files: 1, fields: 0 },
  fileFilter: (req, file, cb) => cb(null, file.originalname.toLowerCase().endsWith('.json')),
});
export function parseSearch(query) {
  if (typeof query.args !== 'string' || !query.args.trim() || query.args.length > 500) throw new Error('Enter a search query between 1 and 500 characters.');
  const limit = query.limit === undefined ? 10 : Number(query.limit);
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new Error('Result limit must be an integer between 1 and 100.');
  if ((query.args.match(/\b\w+\b/g) || []).length > 32) throw new Error('Use at most 32 search terms.');
  const page = query.page === undefined ? 1 : Number(query.page);
  if (!Number.isSafeInteger(page) || page < 1 || page > 10000) throw new Error('Page must be an integer between 1 and 10,000.');
  return { query: query.args.trim(), limit, page };
}
export function validateDocuments(data) {
  if (!Array.isArray(data) || !data.length || data.length > 10000) throw new Error('Provide a JSON array of 1 to 10,000 documents.');
  const ids = new Set();
  for (const doc of data) {
    if (!doc || !Number.isSafeInteger(doc.id) || doc.id < 0 || typeof doc.Title !== 'string' || !doc.Title.trim() || doc.Title.length > 500) throw new Error('Each document needs a nonnegative integer id and a Title between 1 and 500 characters.');
    if (ids.has(doc.id)) throw new Error('Document IDs must be unique within the upload.');
    ids.add(doc.id);
    for (const field of ['Body', 'Answer', 'Tag', 'CreationDate']) if (doc[field] != null && typeof doc[field] !== 'string') throw new Error(`${field} must be a string.`);
    if (doc.Tag?.length > 2000) throw new Error('Tag must be at most 2,000 characters.');
    if (doc.Score != null && (typeof doc.Score !== 'number' || !Number.isFinite(doc.Score))) throw new Error('Score must be a finite number.');
  }
}
const router = Router();
function requestSignal(res) {
  const controller = new AbortController();
  res.on('close', () => { if (!res.writableEnded) controller.abort(); });
  return controller.signal;
}
function fail(res, error) {
  console.error('RAG request failed:', error.message);
  if (!res.destroyed) res.status(error.status || 503).json({ error: error.message });
}
export function parseQuestion(body) {
  if (!body || typeof body.question !== 'string' || !body.question.trim() || body.question.length > 2000) throw new Error('Ask a question between 1 and 2,000 characters.');
  const limit = body.limit ?? 6;
  if (!Number.isInteger(limit) || limit < 1 || limit > 10) throw new Error('Source limit must be an integer between 1 and 10.');
  return { question: body.question.trim(), limit };
}
router.get('/rag/status', async (req, res) => {
  try {
    const config = chatConfig();
    return res.json({ ...await runRag('status', {}, requestSignal(res)), backgroundIndexing: await backgroundIndexing(), answerConfigured: config.configured, provider: config.provider, model: config.model || null });
  } catch (error) { fail(res, error); }
});
router.post('/rag/index', async (req, res) => {
  try { return res.json(await embedDocuments(requestSignal(res))); }
  catch (error) { fail(res, error); }
});
router.post('/ask', async (req, res) => {
  let input;
  try { input = parseQuestion(req.body); } catch (error) { return res.status(400).json({ error: error.message }); }
  try { return res.json(await askDocuments(input.question, input.limit, requestSignal(res))); }
  catch (error) { fail(res, error); }
});
router.get('/documents/:id', async (req, res) => {
  const id = Number(req.params.id);
  if (!/^\d+$/.test(req.params.id) || !Number.isSafeInteger(id)) return res.status(400).json({ error: 'Invalid document ID.' });
  try {
    const document = await runRag('document', { id }, requestSignal(res));
    return document ? res.json(document) : res.status(404).json({ error: 'Document not found.' });
  } catch (error) { fail(res, error); }
});
router.get('/documents', async (req, res) => {
  let input;
  try { input = parseSearch(req.query); } catch (error) { return res.status(400).json({ error: error.message }); }
  try {
    const result = searchDocuments(input);
    res.set('X-Retrieval-Mode', 'bm25');
    res.set('X-Has-More', String(result.hasMore));
    res.set('X-Page', String(result.page));
    return res.json(result.documents);
  } catch (error) { fail(res, error); }
});
router.post('/documents', upload.single('file'), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'Choose a JSON file to upload.' });
  try {
    let data;
    try { data = JSON.parse(await readFile(req.file.path, 'utf8')); validateDocuments(data); }
    catch (error) { return res.status(400).json({ error: error instanceof SyntaxError ? 'The file contains invalid JSON.' : error.message }); }
    const response = await runRag('ingest', { path: req.file.path }, requestSignal(res));
    return res.json({ message: 'Documents processed successfully.', ...response });
  } catch (error) { console.error('Upload failed:', error.message); return res.status(500).json({ error: 'Indexing failed. Check server logs before retrying.' }); }
  finally { await rm(req.file.path, { force: true }); }
});
router.use((error, req, res, next) => {
  if (error instanceof multer.MulterError) return res.status(400).json({ error: error.code === 'LIMIT_FILE_SIZE' ? 'Maximum file size is 10 MB.' : 'Upload one JSON file at a time.' });
  next(error);
});
export default router;
