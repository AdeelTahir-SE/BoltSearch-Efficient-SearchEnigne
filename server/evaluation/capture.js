import '../express/env.js';
import { parseArgs } from 'node:util';
import { appendFile, mkdir, readFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { answerMessages, chatConfig, generateAnswer, runRag } from '../express/rag.js';

const signature = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');

export function validateCases(cases) {
  const ids = new Set();
  if (!cases.length) throw new Error('Evaluation cases cannot be empty.');
  for (const item of cases) {
    if (!item || typeof item.id !== 'string' || !item.id || ids.has(item.id)) throw new Error('Each case needs a unique nonempty string id.');
    ids.add(item.id);
    if (typeof item.user_input !== 'string' || !item.user_input.trim() || item.user_input.length > 2000) throw new Error('Each case needs a question of 1–2,000 characters.');
    if (typeof item.answerable !== 'boolean' || typeof item.reference !== 'string') throw new Error('Each case needs answerable and reference fields.');
    if (!Array.isArray(item.relevant_document_ids) || item.relevant_document_ids.some(id => !Number.isSafeInteger(id) || id < 0)) throw new Error('Relevant document IDs must be safe nonnegative integers.');
    if (!item.answerable && (item.reference || item.relevant_document_ids.length)) throw new Error('Unanswerable cases cannot contain reference evidence.');
  }
  return cases;
}

async function main() {
  const { values } = parseArgs({ options: { mode: { type: 'string', default: 'hybrid' }, cases: { type: 'string' }, output: { type: 'string' }, limit: { type: 'string', default: '5' }, 'query-parsing': { type: 'string', default: 'off' }, 'allow-partial': { type: 'boolean' }, 'dry-run': { type: 'boolean' }, resume: { type: 'boolean' } } });
  if (!['bm25', 'semantic', 'hybrid'].includes(values.mode)) throw new Error('Mode must be bm25, semantic or hybrid.');
  if (!['off', 'on'].includes(values['query-parsing'])) throw new Error('Query parsing must be off or on.');
  const parserHash = signature(await readFile(new URL('../rag/query_parser.py', import.meta.url), 'utf8'));
  const limit = Number(values.limit);
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new Error('Limit must be between 1 and 100 cases.');
  const path = values.cases || fileURLToPath(new URL('./cases.jsonl', import.meta.url));
  const cases = validateCases((await readFile(path, 'utf8')).replace(/^\uFEFF/, '').split(/\r?\n/).filter(line => line.trim()).map(line => JSON.parse(line))).slice(0, limit);
  const policyHash = signature(answerMessages('', [])[0].content);
  const caseHashes = new Map(cases.map(item => [item.id, signature(item)]));
  const config = chatConfig();
  const index = await runRag('status');
  console.log(JSON.stringify({ cases: cases.length, mode: values.mode, answerConfigured: config.configured, model: config.model, embeddedChunks: index.embeddedChunks, chunks: index.chunks, partial: index.pendingChunks > 0, dryRun: Boolean(values['dry-run']) }));
  if (values['dry-run']) return;
  if (!config.configured) throw new Error('Configure the Fireworks answer key and RAG_MODEL first.');
  if (!index.chunks) throw new Error('The corpus is empty.');
  if (values.mode !== 'bm25' && (!index.semanticConfigured || index.pendingChunks > 0) && !values['allow-partial']) throw new Error('Semantic indexing is incomplete. Wait for completion or explicitly use --allow-partial for a diagnostic run.');
  const output = values.output || fileURLToPath(new URL(`./reports/${new Date().toISOString().replace(/[:.]/g, '-')}-${values.mode}.jsonl`, import.meta.url));
  await mkdir(dirname(output), { recursive: true });
  const completed = new Set();
  try {
    const existing = await readFile(output, 'utf8');
    if (!values.resume) throw new Error('Output already exists. Choose another file or use --resume.');
    for (const line of existing.split(/\r?\n/).filter(Boolean)) {
      const row = JSON.parse(line);
      if ((row.query_parsing || 'off') !== values['query-parsing'] || (row.parser_hash && row.parser_hash !== parserHash) || row.requested_mode !== values.mode || row.answer_model !== config.model || row.embedding_space !== index.embeddingSpace || row.prompt_policy_hash !== policyHash) throw new Error('Existing capture configuration differs; choose a new output file.');
      if (caseHashes.has(row.id) && row.case_hash !== caseHashes.get(row.id)) throw new Error('A completed evaluation case has changed; choose a new output file.');
      completed.add(row.id);
    }
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  for (const item of cases) {
    if (completed.has(item.id)) continue;
    const started = performance.now();
    const retrieved = await runRag('retrieve', { query: item.user_input, limit: 6, mode: values.mode, query_parsing: values['query-parsing'] });
    const generated = await generateAnswer(item.user_input, retrieved.sources, { config, diagnostics: true });
    const row = { ...item, response: generated.answer, generation_status: generated.status, generation: generated.generation,
      retrieved_contexts: retrieved.sources.map(source => `Title: ${source.title}\nSection: ${source.section}\n${source.text}`),
      retrieved_document_ids: retrieved.sources.map(source => source.documentId),
      sources: retrieved.sources, query_parsing: values['query-parsing'], parser_hash: parserHash, parsed_query: retrieved.retrieval.parsed_query, requested_mode: values.mode, actual_mode: retrieved.retrieval.mode,
      case_hash: caseHashes.get(item.id), prompt_policy_hash: policyHash,
      warnings: retrieved.retrieval.warnings, answer_model: config.model, embedding_model: index.embeddingModel,
      embedding_space: index.embeddingSpace, index_revision: retrieved.retrieval.revision,
      partial: index.pendingChunks > 0, duration_seconds: (performance.now() - started) / 1000,
      captured_at: new Date().toISOString() };
    await appendFile(output, JSON.stringify(row) + '\n', 'utf8');
    console.log(`${item.id}: ${generated.status} (${retrieved.retrieval.mode})`);
  }
  console.log(`Capture saved: ${output}`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main().catch(error => { console.error(error.message); process.exitCode = 1; });
