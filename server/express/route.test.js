import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseSearch, validateDocuments } from './route.js';
test('search input rejects absent, array, empty, oversized queries and invalid limits', () => {
  for (const args of [undefined, [], '', '   ', 'x'.repeat(501)]) assert.throws(() => parseSearch({ args }));
  for (const limit of ['0', '-1', '101', '2.5', 'nope']) assert.throws(() => parseSearch({ args: 'search', limit }));
  for (const page of ['0', '-1', '1.5', '10001', 'nope']) assert.throws(() => parseSearch({ args: 'search', page }));
  assert.deepEqual(parseSearch({ args: '  binary search  ', limit: '20' }), { query: 'binary search', limit: 20, page: 1 });
});
test('upload validation rejects malformed and duplicate documents', () => {
  for (const data of [{}, [], [{ id: -1, Title: 'a' }], [{ id: 1, Title: '' }], [{ id: 1, Title: 'a' }, { id: 1, Title: 'b' }], [{ id: 1, Title: 'a', Body: {} }]]) assert.throws(() => validateDocuments(data));
  assert.doesNotThrow(() => validateDocuments([{ id: 1, Title: 'Binary search', Score: 3 }]));
});
