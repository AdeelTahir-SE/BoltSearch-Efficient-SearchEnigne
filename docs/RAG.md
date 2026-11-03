# Hybrid RAG: configuration and architecture

## Provider configuration

Copy `server/.env.example` to `server/.env`; the server and administration commands load it automatically. Shell environment variables take precedence. Restart the server after changes.

### Fireworks for answers and embeddings

```dotenv
RAG_PROVIDER=fireworks
BASE_URL=https://api.fireworks.ai/inference/v1
FIREWORKS_API_KEY=your-key
RAG_MODEL=your-enabled-chat-model-id
EMBEDDING_BASE_URL=https://api.fireworks.ai/inference/v1
EMBEDDING_MODEL=your-enabled-embedding-model-id
```

The embedding key defaults to `FIREWORKS_API_KEY`. Select actual model IDs available in your account; a chat model cannot substitute for an embedding model. For models requiring task prefixes, set `EMBEDDING_QUERY_PREFIX` and `EMBEDDING_DOCUMENT_PREFIX` exactly as their model documentation specifies. Quote prefix values containing trailing spaces, for example `"search_query: "` and `"search_document: "` for appropriate Nomic deployments. There is no implicit model or paid deployment selection.

### Grok answers with Fireworks embeddings

```dotenv
RAG_PROVIDER=xai
XAI_API_KEY=your-xai-key
RAG_MODEL=your-enabled-grok-model-id
FIREWORKS_API_KEY=your-fireworks-key
EMBEDDING_BASE_URL=https://api.fireworks.ai/inference/v1
EMBEDDING_MODEL=your-enabled-embedding-model-id
```

Chat uses `https://api.x.ai/v1/chat/completions`. Embeddings still go to the separately configured embedding service. This integration does not assume that xAI exposes an OpenAI-compatible public embeddings endpoint. Its hosted Collections retrieval is a different service and is not used here.

### Other compatible providers

Set `RAG_PROVIDER=custom`, `RAG_BASE_URL`, `RAG_API_KEY`, and `RAG_MODEL`. Independently set `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, and `EMBEDDING_MODEL`. Base URLs include `/v1` (or the provider-specific equivalent) but exclude `/chat/completions` and `/embeddings`. HTTPS is required except on localhost. Redirects are refused to avoid forwarding credentials elsewhere.

The implementation uses ordinary Chat Completions and float embeddings via HTTP, with explicit model names. Model-specific request extensions are not assumed. Live access, availability, context limits, and billing must be verified with your own account.

## Index lifecycle

- SQLite database: `server/dataset/rag.sqlite3` by default. `RAG_DB_PATH` can specify another path; use an absolute path for predictable CLI/server behavior.
- Upload a JSON array. Title, question body, and each answer are normalized to plain text. Scripts/styles are excluded. Questions and answers are chunked separately with 1,200-character windows, up to 180 characters of overlap, and source offsets into normalized text.
- Documents, chunks, and FTS updates commit in one transaction. The SQLite index is now the source of truth for the active API; old CSV files remain untouched.
- Existing CSV data can be copied into SQLite using `npm run rag:import` in `server`. This imports in transactional batches of 100; rerunning unchanged data is idempotent. Do not reimport outdated CSVs over newer edited documents.
- Build vectors from the UI, or run `npm run rag:embed` for the whole corpus. Each operation has at most two batches of 16 unique passages. Partial progress survives failure; rerun to resume. Building vectors is explicit and can incur provider charges.
- Status reports document count, chunk count, embedded/pending chunk counts, and a revision. It never returns keys or provider URLs.
- Embeddings are cached by content hash and an embedding-space fingerprint containing endpoint, model, task prefixes, and version. Changing any of these creates a separate space; no incompatible vectors are mixed. If model weights change under the same ID, increment `EMBEDDING_VERSION`, then rebuild.
- Unchanged imports and unchanged chunk text reuse vectors. Superseded vectors remain cached for possible reuse; the current implementation does not garbage-collect them automatically.
- Query vectors have a bounded five-minute cache (500 entries) in the same database. The cache stores a hash of the question and its vector, not its plaintext.

## Retrieval and answers

1. SQLite FTS5 ranks title, tags, and passage text using BM25 with weights 4, 2, and 1. User input is tokenized and quoted; it is not executed as FTS query syntax.
2. The embedding service maps the question to a vector. Exact cosine search compares it with all current chunk vectors in the same embedding space. Candidates below `RAG_MIN_SIMILARITY` (default 0.25) are excluded; tune this per model and corpus.
3. Reciprocal-rank fusion (`k=60`) combines independently ranked lexical and semantic candidates. Source selection limits each document to two passages so one long document cannot occupy all citations. Ask mode uses six sources by default (API maximum ten).
4. Only the question and selected plain-text excerpts go to the answer model. The prompt treats documents as untrusted data, requests citations for factual statements, and asks for an explicit insufficient-evidence response when needed. There are no tools, executable model actions, or access to backend secrets in the prompt.
5. Answers are displayed as text, with numeric citations mapped to source cards. The server rejects a model response with missing or nonexistent numeric citations as `unverified`. This validates citation IDs, not whether every claim is true or actually entailed; users should inspect excerpts. No retrieved passages means no generation call.
6. Embedding failures, missing keys, unfinished indexing, and dimension mismatches produce visible BM25 fallback warnings. The interface does not label that path as hybrid. Chat provider errors remain errors, not invented fallback answers.

Provider requests are bounded by timeouts and response sizes. Express caps retrieval workers at four, answer requests at two, and semantic index operations at one per server process. This is resource control, not authentication or account-level rate limiting. Protect uploads, indexing, and model-backed endpoints with authentication and gateway limits before exposing the app publicly. For a multi-user deployment, add collection ownership and retrieval filters before using private documents.

## Do we need a vector database?

This version stores vectors persistently in SQLite and performs exact cosine retrieval. It has **no ANN/HNSW index**. This keeps the initial deployment to one database file and provides real hybrid retrieval without another service. It is appropriate as a measurable local baseline, not a promise of large-corpus throughput: vector retrieval is O(number of embedded chunks × dimensions) per uncached request.

Move the vector retrieval layer to Qdrant when measured p95 latency, concurrent load, memory, or corpus size justify indexed nearest-neighbor retrieval, filtering, or a separate service. Qdrant is the suggested next step, not an implemented backend in this revision. Keep stable document IDs, content hashes, embedding-space isolation, and RRF; SQLite BM25 can remain the lexical side initially. Benchmark recall, latency, and filtering against the same labeled query set before changing storage. No hard chunk-count cutoff is universal.

## API

- `GET /api/rag/status`: non-secret configuration and indexing progress.
- `POST /api/rag/index`: embed up to 32 missing unique passages, resumably.
- `POST /api/ask`: `{ "question": "...", "limit": 6 }`; returns answer, status, sources, model, and retrieval mode/warnings. Question maximum: 2,000 characters.
- `GET /api/documents?args=...&limit=10`: hybrid search when prepared, otherwise BM25; returns the existing document array shape. `X-Retrieval-Mode` indicates the actual path.
- `GET /api/documents/:id`: full original question and answers for a source.
- `POST /api/documents`: validated transactional import/upsert. This no longer writes legacy CSV barrels.

## Primary references

- [Fireworks OpenAI compatibility](https://docs.fireworks.ai/tools-sdks/openai-compatibility)
- [Fireworks embeddings guide](https://fireworks.gitbook.io/fireworks/inference/querying-embedding-models)
- [xAI Chat Completions](https://docs.x.ai/developers/rest-api-reference/inference/chat-completions)
- [SQLite FTS5 / BM25](https://www.sqlite.org/fts5.html)
- [Qdrant indexing](https://qdrant.tech/documentation/manage-data/indexing/)

## Verification in this revision

- Frontend production build and lint passed.
- Seventeen Python tests passed for retrieval, chunking, transactions, caching, vector-space isolation, provider response validation, and legacy regressions.
- Ten Node tests passed, including a full HTTP import/embedding/retrieval/cited-answer flow and a simulated embedding outage. Provider endpoints were local mocks; no real credentials, paid calls, or external document transfers were used.
- Browser checks passed for semantic-index progress, Ask mode, citation navigation, source expansion, full-document viewing, and mobile overflow. [Desktop preview](bolt-rag-desktop.png) and [mobile preview](bolt-rag-mobile.png) use fixture documents and answers.
- Live Fireworks/xAI model access and real-corpus relevance/latency require your selected model IDs, keys, and data; those remain unverified.

## Local Ollama setup and the included archive

This workspace has been configured in the ignored `server/.env` to use the installed `nomic-embed-text:latest` through `http://127.0.0.1:11434/api/embed`. Set `EMBEDDING_PROVIDER=ollama` for this native local endpoint; no embedding API key is required, and cloud keys are never forwarded to it. The Nomic query/document prefixes are configured separately. `EMBEDDING_VERSION` records the installed model digest so this vector space is identifiable.

`npm run rag:import:archive` imports only `train.csv` directly from the repository's `archive.zip`, mapping `Tags` to `Tag`. It does not extract the ZIP or include `valid.csv`. The real import contains 45,000 training documents and 57,499 passages; a direct ID check confirmed that none of the 15,000 validation IDs is in the search index. `Y` is excluded from answer evidence, and no answers are invented for these question-only rows. A local import report is saved at `server/dataset/import-report.json`.

Local Ollama uses smaller batches of four passages per provider request to reduce CPU request duration. CPU indexing of the full corpus can take many hours; progress commits after every batch and a repeated `npm run rag:embed` resumes missing vectors. Keep Ollama running. The hidden background job launched for this import records its state in `server/dataset/embedding-job.json`, progress in `embedding-progress.log`, and the final summary in `embedding-result.log`. The Ask interface polls progress while that job runs and prevents a second indexing action through the UI.

The standard CLI can also run directly in a terminal: `npm run rag:embed`. Avoid starting another embedding job while the existing background job is running. Keyword search covers all imported questions immediately; semantic coverage grows as embeddings are generated. The Fireworks/Grok answer model still requires your chosen model ID and API key. A local embedding model alone cannot generate answers.

[Ollama native embedding API](https://docs.ollama.com/api/embed)

Local verification: 19 Python tests and 10 backend tests passed, including the archive split/mapping and native Ollama transport. Frontend build and lint passed. A real local hybrid query against the imported corpus returned the exact matching question, with partial-coverage warnings as expected. The background job uses `OLLAMA_EMBEDDING_THREADS=2` to leave more CPU capacity for the app. Its full semantic index is still being generated; only the database counts indicate completion.

## Indexing recovery

Full-corpus indexing now retries temporary connection failures and HTTP 408/429/500/502/503/504 responses, with at most six consecutive attempts and backoff capped at 30 seconds. Local retry batches shrink from four to two to one passage after failures. Background document requests allow 180 seconds; query timeout settings are unchanged. Authentication, model/configuration, malformed-response, and vector-validation errors fail immediately rather than retrying indefinitely.

Every successful batch commits before the next request. An operating-system file lock prevents simultaneous embedding writers and releases automatically if a worker exits; its lock file does not need deletion. Both foreground `npm run rag:embed` resumes and hidden jobs now use the same supervisor and progress metadata. Job state is written atomically and includes the current phase, retry count/delay, batch size, and committed counts. A completed state requires a successful worker exit and a final zero-pending event. Existing vectors and the embedding-space identity are preserved.


### Fireworks embedding migration

The workspace is configured for `https://api.fireworks.ai/inference/v1` with `nomic-ai/nomic-embed-text-v1.5`, 768 dimensions, and Nomic query/document prefixes. The key falls back to `FIREWORKS_API_KEY`. A short live connectivity check returned HTTP 200. Full corpus indexing is pending explicit approval for external data transfer and provider usage charges. Existing Ollama vectors remain saved in their separate space. The new Fireworks space needs all passages embedded; semantic coverage is incomplete until indexing finishes. Restart the API server after migration to load its new environment. Ragas uses the same configured embedding provider.


### Active Qwen3 Fireworks index

The approved full-corpus index uses `accounts/fireworks/models/qwen3-embedding-8b` through Fireworks, with 4096-dimensional vectors. Queries use `Instruct: Given a programming question, retrieve relevant Stack Overflow passages` followed by a newline and `Query: `; documents have no prefix, following the Qwen model card. The Fireworks key is reused via the OpenAI-compatible adapter. Full indexing is authorized, uses batches of 16, and retains retry, writer-lock, and resume protection. Old Ollama vectors remain isolated and saved. Ragas now accepts either configured provider. Restart an existing API server to load the new environment.


### Full-index cosine acceleration

The 4096-dimensional Fireworks index requires NumPy (`pip install -r server/requirements.txt`) for practical exhaustive-search latency. Cosine scores are computed in batches of 256 vectors with float64 arithmetic, retaining deterministic top-k ranking and bounded memory. Environments without NumPy retain the scalar fallback. This is exact search, not ANN; it does not change embedding-space identity or require re-embedding. A 300-document regression compares accelerated and scalar rankings across batch boundaries.


### Browsing search and source answers

The Search tab uses document-deduplicated SQLite FTS5 BM25 with stable ranking, page-size selection, and Previous/Next controls. GET `/api/documents?args=python&limit=10&page=2` preserves the array response and reports `X-Page`, `X-Has-More`, and `X-Retrieval-Mode: bm25`. Ask continues to use hybrid semantic/BM25 retrieval. Search does not call the embedding provider. Pagination uses a limit-plus-one probe instead of computing an expensive exact total.

All 45,000 records from the supplied archive contain questions only: its columns are Id, Title, Body, Tags, CreationDate, and Y. None has an answer body. The UI labels this source limitation explicitly; generated answers must not be presented as original Stack Overflow answers. Add a question-and-answer source dataset to populate source answers.


### Fast keyword search runtime

Normal search now reads SQLite directly in Node 22.13+ through `node:sqlite` (no Python startup or provider calls). A covering `chunks_search_mapping(id,document_id)` index avoids reading large passage rows during document ranking. A 100-entry, 30-second cache keys results by database path, index revision, query terms, page size and page; successful corpus changes invalidate results through revision changes. SQLite reads use a consistent transaction and close after each request. Existing database installations can run `npm run rag:status` to initialize schema/index additions before serving traffic.

Local HTTP smoke measurements for `python`, 10 results: first page 263 ms, cached first page 17 ms, second page 144 ms, zero duplicate documents across pages. These are single local checks, not load-test percentiles.


### Active StackSample question-and-answer corpus (2026-10-30)

The running app now uses `server/dataset/stacksample/staged/rag.sqlite3`: 45,000 answered questions, 65,114 actual answer bodies (up to two highest-scored answers per question), and 143,398 fully embedded passages. All documents have a source answer body. Nomic v1.5 on Fireworks supplies 768-dimensional query/document vectors; the old question-only index and its Qwen3 vectors are retained at `server/dataset/rag.sqlite3`. The folder is named staged for traceability but is now the configured active database. Selection is deterministic uniform sampling among answered questions; it covers common language/platform tags but is not tag-stratified. Score order is not accepted-answer status, which this archive does not supply.

The new app was checked for complete active fingerprint coverage, actual answer text, keyword pagination without duplicate documents, and a hybrid Ask HTTP request. Answer citation validation can still return unverified; full pilot reports retain those failures rather than treating conditional faithfulness as overall accuracy. Keyword-page smoke times were 437 ms for the first page and 66 ms for the second under concurrent evaluation activity; these are single observations, not latency percentiles.


### Structured claim citations

The custom RAG pipeline uses Fireworks JSON-schema output for answerable plus claims (text, numeric source_id, supporting quote). The server checks schema, source IDs and quote provenance, then renders citations itself. Evidence provenance is not a proof of semantic entailment. One repair is allowed under a shared 60-second deadline; invalid/truncated responses cannot pass. Raw final-output diagnostics are opt-in for offline evaluation only, never included in normal API responses, and never include hidden reasoning. Source panels display evidence quotes. No LangChain runtime is used; Ragas has a separate evaluation environment. Implementation follows https://docs.fireworks.ai/structured-responses/structured-response-formatting .
