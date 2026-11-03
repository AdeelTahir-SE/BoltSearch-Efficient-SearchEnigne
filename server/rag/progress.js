import '../express/env.js';
import { spawnSync } from 'node:child_process';
import { readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const child = spawnSync(process.env.PYTHON || 'python', [fileURLToPath(new URL('./progress.py', import.meta.url))], { encoding: 'utf8', windowsHide: true, timeout: 30000 });
if (child.status !== 0) { console.error('Could not inspect embedding progress. Check Python and database access.'); process.exit(1); }
const result = JSON.parse(child.stdout);
const directory = dirname(process.env.RAG_DB_PATH || fileURLToPath(new URL('../dataset/rag.sqlite3', import.meta.url)));
try {
  const state = JSON.parse(readFileSync(join(directory, 'embedding-job.json'), 'utf8'));
  result.job = state;
  try { process.kill(state.workerPid, 0); result.workerAlive = true; }
  catch (error) { result.workerAlive = error.code === 'EPERM' ? null : false; }
  result.lastProgressAt = statSync(join(directory, 'embedding-progress.log')).mtime.toISOString();
} catch { result.job = null; }
console.log(JSON.stringify(result, null, 2));
