// Keep the currently served index unchanged while building the staged corpus.
import '../express/env.js';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const directory = new URL('../dataset/stacksample/staged/', import.meta.url);
const config = JSON.parse(readFileSync(new URL('embedding-config.json', directory), 'utf8'));
for (const [key, value] of Object.entries(config)) process.env[key] = String(value);
process.env.RAG_DB_PATH = fileURLToPath(new URL('rag.sqlite3', directory));
await import('./background.js');
