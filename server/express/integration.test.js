import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createServer } from 'node:http';
import { mkdtemp, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import app from './app.js';

test('HTTP upload → BM25 → embeddings → semantic-only retrieval → cited answer → document update', { timeout: 60000 }, async () => {
  const temporary = await mkdtemp(fileURLToPath(new URL('../tests/rag-http-', import.meta.url)));
  let answerCalls = 0, embeddingCalls = 0, failEmbeddings = false;
  const provider = createServer(async (req, res) => {
    let input = '';
    for await (const part of req) input += part;
    const body = JSON.parse(input);
    assert.equal(req.headers.authorization, 'Bearer local-test-key');
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/v1/embeddings') {
      embeddingCalls++;
      if (failEmbeddings) { res.statusCode = 503; res.end('{}'); return; }
      assert.equal(body.model, 'embedding-test');
      res.end(JSON.stringify({ data: body.input.map((text, index) => ({ index, embedding: /automobile|engine|car/.test(text) ? [1, 0] : [0, 1] })).reverse() }));
    } else if (req.url === '/v1/chat/completions') {
      answerCalls++;
      assert.equal(body.model, 'chat-test');
      assert.ok(JSON.parse(body.messages[1].content).document_excerpts.length);
      const source = JSON.parse(body.messages[1].content).document_excerpts[0];
      res.end(JSON.stringify({ choices: [{ finish_reason: 'stop', message: { content: JSON.stringify({ answerable: true, claims: [{ text: 'Inspect the engine regularly.', source_id: source.source_id, quote: source.text.slice(0, 150) }] }) } }] }));
    } else { res.statusCode = 404; res.end('{}'); }
  });
  await new Promise(resolve => provider.listen(0, '127.0.0.1', resolve));
  const providerURL = `http://127.0.0.1:${provider.address().port}/v1`;
  const env = { RAG_DB_PATH: join(temporary, 'test.sqlite3'), RAG_PROVIDER: 'custom', RAG_BASE_URL: providerURL,
    RAG_API_KEY: 'local-test-key', RAG_MODEL: 'chat-test', EMBEDDING_BASE_URL: providerURL,
    EMBEDDING_PROVIDER: 'openai', EMBEDDING_API_KEY: 'local-test-key', EMBEDDING_MODEL: 'embedding-test', EMBEDDING_QUERY_PREFIX: '', EMBEDDING_DOCUMENT_PREFIX: '' };
  const previous = Object.fromEntries(Object.keys(env).map(key => [key, process.env[key]]));
  Object.assign(process.env, env);
  const server = app.listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  const base = `http://127.0.0.1:${server.address().port}/api`;
  const post = async (endpoint, body) => {
    const response = await fetch(base + endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const result = await response.json();
    assert.equal(response.status, 200, JSON.stringify(result));
    return result;
  };
  const upload = async data => {
    const body = new FormData(); body.append('file', new Blob([JSON.stringify(data)], { type: 'application/json' }), 'docs.json');
    const response = await fetch(base + '/documents', { method: 'POST', body });
    assert.equal(response.status, 200);
    return response.json();
  };
  try {
    let status = await (await fetch(base + '/rag/status')).json();
    assert.equal(status.documents, 0);
    assert.equal(status.answerConfigured, true);
    assert.ok(!JSON.stringify(status).includes('local-test-key'));
    const imported = await upload([{ id: 1, Title: 'Vehicle care', Body: '<p>Inspect the car engine regularly.</p>' }, { id: 2, Title: 'Gardening', Body: 'Water your flowers.' }]);
    assert.equal(imported.indexed, 2);
    const lexicalResponse = await fetch(base + '/documents?args=engine');
    assert.equal(lexicalResponse.headers.get('X-Retrieval-Mode'), 'bm25');
    assert.equal((await lexicalResponse.json())[0].Id, 1);
    assert.equal((await post('/ask', { question: 'automobile' })).status, 'insufficient_evidence');
    assert.equal(answerCalls, 0);
    assert.equal((await (await fetch(base + '/documents?args=engine')).json())[0].Id, 1);
    assert.equal(embeddingCalls, 0);
    const indexed = await post('/rag/index', {});
    assert.equal(indexed.pendingChunks, 0);
    assert.equal(embeddingCalls, 1);
    const answer = await post('/ask', { question: 'automobile' });
    assert.equal(answer.status, 'answered');
    assert.equal(answer.retrieval.mode, 'hybrid');
    assert.equal(answer.sources[0].documentId, 1);
    assert.deepEqual(answer.sources[0].methods, ['semantic']);
    assert.equal(answerCalls, 1);
    failEmbeddings = true;
    const degraded = await post('/ask', { question: 'engine maintenance' });
    assert.equal(degraded.retrieval.mode, 'bm25');
    assert.ok(degraded.retrieval.warnings.some(warning => warning.includes('HTTP 503')));
    failEmbeddings = false;
    const document = await (await fetch(base + '/documents/1')).json();
    assert.equal(document.Title, 'Vehicle care');
    assert.equal((await upload([{ id: 1, Title: 'Vehicle care', Body: '<p>Inspect the car engine regularly.</p>' }])).skipped, 1);
    await upload([{ id: 1, Title: 'New subject', Body: 'A changed passage.' }]);
    status = await (await fetch(base + '/rag/status')).json();
    assert.equal(status.documents, 2);
    assert.equal(status.pendingChunks, 1);
    assert.deepEqual(await (await fetch(base + '/documents?args=engine')).json(), []);
    assert.equal((await (await fetch(base + '/documents?args=changed')).json())[0].Id, 1);
    const invalid = await fetch(base + '/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{' });
    assert.equal(invalid.status, 400);
  } finally {
    server.closeAllConnections(); provider.closeAllConnections();
    await Promise.all([new Promise(resolve => server.close(resolve)), new Promise(resolve => provider.close(resolve))]);
    for (const key of Object.keys(env)) { if (previous[key] === undefined) delete process.env[key]; else process.env[key] = previous[key]; }
    await rm(temporary, { recursive: true, force: true });
  }
});
