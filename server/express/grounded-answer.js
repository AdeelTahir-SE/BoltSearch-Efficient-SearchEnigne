export function groundedSchema(sources) {
  return { type: 'object', additionalProperties: false, required: ['answerable', 'claims'], properties: {
    answerable: { type: 'boolean' },
    claims: { type: 'array', maxItems: 6, items: {
      type: 'object', additionalProperties: false, required: ['text', 'source_id', 'quote'], properties: {
        text: { type: 'string', minLength: 1, maxLength: 600 },
        source_id: { type: 'integer', enum: sources.map(source => source.id) },
        quote: { type: 'string', minLength: 8, maxLength: 500 },
      },
    } },
  } };
}

const normalized = text => text.normalize('NFKC').replace(/\s+/gu, ' ').trim();

// Quote provenance is deterministic; this does not prove semantic entailment.
export function validateGroundedAnswer(content, sources) {
  let data;
  try { data = JSON.parse(content); } catch { return { valid: false, error: 'invalid_json' }; }
  if (!data || typeof data.answerable !== 'boolean' || !Array.isArray(data.claims) || data.claims.length > 6 || Object.keys(data).some(key => !['answerable', 'claims'].includes(key))) return { valid: false, error: 'invalid_schema' };
  if (!data.answerable) return data.claims.length ? { valid: false, error: 'abstention_has_claims' } : { valid: true, answerable: false, claims: [] };
  if (!data.claims.length) return { valid: false, error: 'missing_claims' };
  const byId = new Map(sources.map(source => [source.id, source]));
  for (const claim of data.claims) {
    if (!claim || typeof claim.text !== 'string' || !claim.text.trim() || claim.text.length > 600 || typeof claim.quote !== 'string' || claim.quote.trim().length < 8 || claim.quote.length > 500 || Object.keys(claim).some(key => !['text', 'source_id', 'quote'].includes(key))) return { valid: false, error: 'invalid_claim' };
    if (!Number.isInteger(claim.source_id) || !byId.has(claim.source_id)) return { valid: false, error: 'unknown_source' };
    if (/\[\d+\]|【[^】]*】/u.test(claim.text)) return { valid: false, error: 'inline_citation' };
    if (!normalized(byId.get(claim.source_id).text).includes(normalized(claim.quote))) return { valid: false, error: 'quote_not_in_source' };
  }
  return { valid: true, answerable: true, claims: data.claims };
}
