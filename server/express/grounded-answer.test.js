import assert from 'node:assert/strict';
import { test } from 'node:test';
import { validateGroundedAnswer } from './grounded-answer.js';
import { generateAnswer } from './rag.js';

const sources = [{ id: 1, text: 'Binary search halves a sorted interval.', title: 'Search' }];
const config = { configured: true, model: 'test', baseURL: 'https://provider.example/v1', apiKey: 'fake' };
const valid = { answerable: true, claims: [{ text: 'Binary search halves the interval.', source_id: 1, quote: 'halves a sorted interval' }] };
const response = (content, finish_reason = 'stop') => Response.json({ choices: [{ finish_reason, message: { content: JSON.stringify(content) } }] });

test('grounded validation requires real source IDs, copied quotes and citation-free claims', () => {
  assert.equal(validateGroundedAnswer(JSON.stringify(valid), sources).valid, true);
  for (const claim of [
    { ...valid.claims[0], source_id: 9 },
    { ...valid.claims[0], source_id: '1' },
    { ...valid.claims[0], quote: 'An invented source quote.' },
    { ...valid.claims[0], text: 'A claim 【1】' },
    { ...valid.claims[0], text: 'A claim [9]' },
  ]) assert.equal(validateGroundedAnswer(JSON.stringify({ answerable: true, claims: [claim] }), sources).valid, false);
  assert.equal(validateGroundedAnswer('{', sources).error, 'invalid_json');
  assert.equal(validateGroundedAnswer(JSON.stringify({ answerable: false, claims: [] }), sources).valid, true);
  assert.equal(validateGroundedAnswer(JSON.stringify({ answerable: false, claims: valid.claims }), sources).valid, false);
});

test('server renders citations and does not expose raw final output by default', async () => {
  const result = await generateAnswer('How?', sources, { config, fetcher: async () => response(valid) });
  assert.equal(result.status, 'answered');
  assert.ok(result.answer.endsWith('[1]'));
  assert.equal(result.generation.semanticEntailmentVerified, false);
  assert.equal('finalOutput' in result.generation.diagnostics[0], false);
});

test('exactly one repair reuses original evidence and records failure diagnostics for evaluation', async () => {
  let calls = 0;
  const result = await generateAnswer('How?', sources, { config, diagnostics: true, fetcher: async (url, options) => {
    calls++;
    const body = JSON.parse(options.body);
    if (calls === 1) return response({ ...valid, claims: [{ ...valid.claims[0], source_id: 99 }] });
    const input = JSON.parse(body.messages[1].content);
    assert.equal(input.repair.validation_error, 'unknown_source');
    assert.equal(input.document_excerpts[0].text, sources[0].text);
    return response(valid);
  } });
  assert.equal(calls, 2);
  assert.equal(result.generation.repaired, true);
  assert.equal(result.generation.diagnostics[0].validationError, 'unknown_source');
  assert.equal(typeof result.generation.diagnostics[0].finalOutput, 'string');
});

test('repeated unsupported quotes remain unverified; truncation is never accepted', async () => {
  let calls = 0;
  const invalid = { ...valid, claims: [{ ...valid.claims[0], quote: 'fabricated unsupported quote' }] };
  const result = await generateAnswer('How?', sources, { config, fetcher: async () => { calls++; return response(invalid); } });
  assert.equal(calls, 2);
  assert.equal(result.status, 'unverified');
  const truncated = await generateAnswer('How?', sources, { config, fetcher: async () => response(valid, 'length') });
  assert.equal(truncated.status, 'unverified');
  assert.equal(truncated.generation.diagnostics[0].validationError, 'truncated');
});

test('empty truncated final content gets one bounded repair', async () => {
  let calls = 0;
  const result = await generateAnswer('How?', sources, { config, fetcher: async () => {
    calls++;
    if (calls === 1) return Response.json({ choices: [{ finish_reason: 'length', message: { content: null } }] });
    return response(valid);
  } });
  assert.equal(calls, 2);
  assert.equal(result.status, 'answered');
  assert.equal(result.generation.diagnostics[0].validationError, 'truncated');
});
