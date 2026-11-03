import '../express/env.js';
import { spawn } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync, renameSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const database = process.env.RAG_DB_PATH || fileURLToPath(new URL('../dataset/rag.sqlite3', import.meta.url));
const directory = dirname(database);
mkdirSync(directory, { recursive: true });
const statePath = join(directory, 'embedding-job.json');
let previous;
try { previous = JSON.parse(readFileSync(statePath, 'utf8')); } catch { /* First job. */ }
if (previous?.state === 'running' && Number.isInteger(previous.pid)) {
  try {
    process.kill(previous.pid, 0);
    console.error('An indexing supervisor is already running. Check npm run rag:progress.');
    process.exit(1);
  } catch (error) {
    if (error.code === 'EPERM') { console.error('Cannot verify the existing indexing supervisor; refusing to create a duplicate.'); process.exit(1); }
  }
}
let state = { state: 'running', phase: 'starting', pid: process.pid, startedAt: new Date().toISOString(), consecutiveRetries: 0 };
const save = () => {
  const temporary = `${statePath}.${process.pid}.tmp`;
  writeFileSync(temporary, JSON.stringify(state, null, 2));
  renameSync(temporary, statePath);
};
const child = spawn(process.env.PYTHON || 'python', [fileURLToPath(new URL('./worker.py', import.meta.url)), 'embed-all', '--cli'], {
  windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
});
state.workerPid = child.pid;
save();
let buffered = '';
child.stdout.on('data', data => process.stdout.write(data));
child.stderr.on('data', data => {
  process.stderr.write(data);
  buffered += data.toString();
  let end;
  while ((end = buffered.indexOf('\n')) !== -1) {
    const line = buffered.slice(0, end).trim();
    buffered = buffered.slice(end + 1);
    if (!line.startsWith('INDEX_EVENT ')) continue;
    try {
      const event = JSON.parse(line.slice('INDEX_EVENT '.length));
      if (!['embedding', 'retrying', 'complete', 'failed'].includes(event.phase)) continue;
      state.phase = event.phase;
      state.updatedAt = new Date().toISOString();
      if (event.phase === 'retrying' || event.phase === 'failed') {
        state.consecutiveRetries = event.attempt;
        state.retryInSeconds = event.retryInSeconds ?? null;
        state.lastError = event.error;
      } else {
        state.consecutiveRetries = 0;
        state.retryInSeconds = null;
        state.lastError = null;
        state.lastProgressAt = state.updatedAt;
      }
      for (const key of ['embeddedChunks', 'pendingChunks', 'chunks', 'documents', 'batchSize']) {
        if (Number.isInteger(event[key]) && event[key] >= 0) state[key] = event[key];
      }
      save();
    } catch { /* Keep raw logs; malformed progress never fabricates completion. */ }
  }
  if (buffered.length > 16000) buffered = '';
});
child.on('error', () => {
  Object.assign(state, { state: 'failed', phase: 'failed', finishedAt: new Date().toISOString(), lastError: 'Could not start the indexing worker.' });
  save(); process.exitCode = 1;
});
child.on('close', code => {
  const complete = code === 0 && state.phase === 'complete' && state.pendingChunks === 0;
  Object.assign(state, { state: complete ? 'complete' : 'failed', finishedAt: new Date().toISOString(), exitCode: code });
  if (!complete && !state.lastError) state.lastError = 'Indexing worker stopped; check embedding-progress.log.';
  save(); process.exitCode = complete ? 0 : 1;
});
