import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { validateCases } from '../evaluation/capture.js';

test('evaluation seeds have explicit evidence labels and unique IDs', async () => {
  const rows = (await readFile(new URL('../evaluation/cases.jsonl', import.meta.url), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
  assert.equal(validateCases(rows).length, 10);
  assert.equal(rows.filter(row => !row.answerable).length, 1);
});
test('contradictory abstention labels and duplicate IDs fail before paid capture', () => {
  const row = { id: 'one', user_input: 'Question?', reference: '', answerable: false, relevant_document_ids: [] };
  assert.throws(() => validateCases([row, row]));
  assert.throws(() => validateCases([{ ...row, relevant_document_ids: [1] }]));
});

test('expanded set has 50 valid cases and disjoint source groups across splits', async () => {
  const read = async name => (await readFile(new URL(`../evaluation/sets/${name}`, import.meta.url), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
  const rows = validateCases(await read('stacksample-50.jsonl'));
  const development = await read('stacksample-50-dev.jsonl');
  const holdout = await read('stacksample-50-holdout.jsonl');
  assert.equal(rows.length, 50);
  assert.equal(rows.filter(row => row.category === 'direct').length, 30);
  assert.equal(rows.filter(row => row.category === 'harder').length, 10);
  assert.equal(rows.filter(row => !row.answerable).length, 10);
  assert.equal(development.length, 30);
  assert.equal(holdout.length, 20);
  const sources = items => new Set(items.flatMap(row => [...row.relevant_document_ids, ...(row.context_document_ids || [])]));
  const devSources = sources(development);
  assert.equal([...sources(holdout)].filter(id => devSources.has(id)).length, 0);
  assert.deepEqual(new Set([...development, ...holdout].map(row => row.id)), new Set(rows.map(row => row.id)));
  assert.ok(rows.filter(row => row.answerable).every(row => row.evidence_quotes?.length));
});
