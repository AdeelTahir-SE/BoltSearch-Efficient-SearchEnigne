# Bolt Search

A React search and RAG interface with an Express API, SQLite FTS5/BM25, semantic retrieval, and configurable OpenAI-compatible answer models.

Offline evaluation is prepared with Ragas: see [evaluation setup and commands](docs/EVALUATION.md). Use `npm run rag:progress` in `server` for a read-only indexing check.

## Run locally

Requires Node.js 22.13+ and Python 3.10+ with SQLite FTS5 support. The active search and RAG paths use Python's standard library: no NLTK downloads or external database are required. `server/requirements.txt` is only needed for the older CSV/NLP utilities.

1. Run `npm ci` in `server` and in `client/BoltSearch`.
2. Copy `server/.env.example` to `server/.env`. Set your answer provider, key, and chat model. Configure a separate embedding model and endpoint for semantic retrieval. See [RAG configuration](docs/RAG.md).
3. Run `npm start` in `server` and `npm run dev` in `client/BoltSearch`.
4. Open the URL printed by Vite. `/api` proxies to port 3000.
5. Add a JSON collection using **Add documents**. For an existing CSV corpus, run `npm run rag:import` in `server` once.
6. Choose **Ask your knowledge**, then **Build semantic index**. Each click embeds up to 32 unique passages. For a full corpus, run `npm run rag:embed` in `server`; it resumes until indexing is complete.

Keyword search works without model keys. Ask mode requires a chat model; if embeddings are unavailable, answers visibly use BM25-only retrieval. Model API calls can incur charges. Questions and selected excerpts go to the answer provider; passage text goes to the embedding provider when you build the semantic index.

Backend secrets belong only in `server/.env`. Never prefix keys with `VITE_`, commit them, or enter them in the frontend. For a deployed frontend, set `VITE_API_URL` to the backend's `/api` URL at build time, or use a same-origin proxy.

## Document format

```json
[
  { "id": 1, "Title": "How does binary search work?", "Body": "Search a sorted sequence.", "Answer": "Repeatedly halve the search interval.", "Tag": "<algorithms><search>", "Score": 10, "CreationDate": "2026-10-28" }
]
```

`id` and `Title` are required. IDs are nonnegative safe integers, unique within a batch. Title is at most 500 characters; Tag is at most 2,000. Other displayed fields are optional. Imports are transactional: unchanged documents are skipped, changed documents with the same ID are updated, and stale chunks are removed. Uploads accept one JSON file up to 10 MB and 10,000 documents. Embeddings are built separately and reused by content hash.

## Verification

- Frontend: `npm run build` and `npm run lint` in `client/BoltSearch`.
- Backend: `npm test` in `server`. The integration test starts local mock provider endpoints and needs local network access; it makes no paid or external AI calls.
- Retrieval, storage, and ingestion tests: `python -m unittest discover -s server/tests` from the repository root.
- Index inspection: `npm run rag:status` in `server`.

See [RAG configuration and architecture](docs/RAG.md). The [initial project review](docs/PROJECT_REVIEW.md) records the earlier CSV implementation and its limitations; its proposed RAG work is now implemented as described in the RAG guide.

## StackSample corpus and evaluation

The local demonstration uses 45,000 answered Stack Overflow questions, 65,114 answer bodies, and 143,398 passages from StackSample. A deterministic streaming importer selects answered questions and retains up to two highest-scored answers. See [the corpus setup](docs/RAG.md#active-stacksample-question-and-answer-corpus-2026-10-30) and `server/rag/import_stacksample.py --help` for migration details. Downloaded datasets, SQLite indexes, vectors, API keys, and installed dependencies are intentionally excluded from Git; a fresh checkout must import and embed its own corpus.

Hybrid Ask combines SQLite FTS5 BM25 with Nomic semantic retrieval through reciprocal-rank fusion. Normal paginated search uses direct SQLite queries and caching. Fireworks supplies OpenAI-compatible generation and embeddings; local Ollama embeddings are also supported. Generated claims undergo source-ID and copied-quotation validation, with bounded repair and abstention when evidence is insufficient. These checks do not prove semantic correctness.

A 50-case pilot used a separate DeepSeek judge with a 4,096-token evaluation budget: faithfulness **0.930** and answer relevance **0.809** across 38 accepted answers; context precision **0.874** and context recall **0.950** across 40 answerable cases. Known-source retrieval recall was **40/40**, MRR **0.930**, and correct absent-evidence abstention **10/10**. All eligible DeepSeek metric values were scored with zero final errors. These are agent-reviewed pilot results, not overall accuracy or expert-adjudicated benchmark results. See [evaluation methodology, judge comparisons, and reproduction commands](docs/EVALUATION.md).
