import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const serverRoot = fileURLToPath(new URL('../', import.meta.url));
const cache = new Map();
const pending = new Map();
let generation = 0;
let uploadQueue = Promise.resolve();
function runPython(script, args, timeout = 30000) {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(process.env.PYTHON || 'python', [resolve(serverRoot, script), ...args.map(String)], { cwd: serverRoot, windowsHide: true });
    let output = '', errors = '';
    const timer = setTimeout(() => { child.kill(); reject(new Error('Document processing timed out.')); }, timeout);
    child.on('error', error => { clearTimeout(timer); reject(error); });
    child.stdout.on('data', data => {
      output += data.toString();
      if (output.length > 16 * 1024 * 1024) { child.kill(); reject(new Error('Search response is too large.')); }
    });
    child.stderr.on('data', data => { errors = (errors + data.toString()).slice(-8000); });
    child.on('close', code => {
      clearTimeout(timer);
      if (code !== 0) return reject(new Error(errors.trim() || `Document processing exited with code ${code}.`));
      try { resolvePromise(JSON.parse(output)); } catch { reject(new Error('Invalid response from document processor.')); }
    });
  });
}
export function uploadDocument(filePath) {
  // Serialize index writes; overlapping CSV rewrites can otherwise lose documents.
  const task = uploadQueue.then(() => runPython('file-upload/uploadFile.py', [filePath], 120000));
  uploadQueue = task.catch(() => {});
  return task.finally(() => { generation++; cache.clear(); pending.clear(); });
}
export async function searchDocuments(query, limit = 10) {
  const normalized = query.toLowerCase().trim().replace(/\s+/g, ' ');
  const key = JSON.stringify([generation, normalized, limit]);
  const hit = cache.get(key);
  if (hit && hit.expires > Date.now()) return hit.documents;
  if (pending.has(key)) return pending.get(key);
  const currentGeneration = generation;
  const task = runPython('search-query/searchDos.py', [normalized, limit]).then(documents => {
    if (!Array.isArray(documents)) throw new Error('Invalid search result.');
    if (currentGeneration === generation) {
      if (cache.size >= 100) cache.delete(cache.keys().next().value);
      cache.set(key, { documents, expires: Date.now() + 30000 });
    }
    return documents;
  }).finally(() => pending.delete(key));
  pending.set(key, task);
  return task;
}
