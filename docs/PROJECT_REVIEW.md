# Project review and next steps

This records the initial CSV-based improvement pass. The subsequent [hybrid RAG implementation](RAG.md) supersedes the runtime/indexing architecture and the proposed RAG work described below.

## What this project does

The frontend is a React 18/Vite app. Express accepts queries and JSON uploads, then invokes Python. Title and tag terms are lemmatized, mapped to numeric token IDs, and stored in CSV inverted-index barrels. Forward barrels hold questions and answers in document-ID ranges of 4,000. Older offline scripts build and merge indexes; they remain legacy utilities and are not the updated API ingestion path.

## Changes in this revision

- Rebuilt the interface with a charcoal/green palette, editorial typography, subtle dot texture, responsive layouts, clearer search and result hierarchy, an upload dialog, keyboard navigation, and reduced-motion support.
- Retained the lightning hover interaction and added a secret alternate palette. Spoilers: click the logo five times, type `bolt` outside an input, search `42`, or double-click the footer star.
- Fixed the empty-query loading lock, obsolete dropzone accept configuration, hardcoded frontend service URL, and misleading upload success handling.
- Isolated document HTML in sandboxed frames with a restrictive content policy. Scripts, forms, popups, and parent-page access are disabled. Rich content remains readable; external links cannot navigate out of the sandbox.
- Replaced one Python process per word with one per query. Deduplicated query terms, fixed integer/string token lookup, shared barrel reads within a request, and ranked the complete candidate set before limiting results. Removed pandas from the online search implementation.
- Added deterministic ranking by matched query terms, title matches, document score, and ID. This is a transparent baseline, not BM25 or semantic relevance.
- Added a bounded 30-second result cache (100 entries), identical-query coalescing, upload cache invalidation, subprocess timeouts/error handling, and stable script paths independent of the launching directory.
- Added query and batch validation, random temporary upload names, 10 MB limits, cleanup, serialized writes, and consistent API errors.
- Replaced the broken batch ingestion path: documents are grouped into the correct forward barrels, every document contributes postings, existing IDs are skipped, UTF-8 is preserved, and new token barrels can be created without a preexisting dataset.
- Fixed the server start command and replaced Vite branding.
- Removed eight unused backend dependencies, including the unmaintained `loadsh` typo package, and refreshed the lockfile.

## Remaining limitations and priorities

1. The repository does not include the real dataset or linguistic resources. Production relevance and latency require measurement against that corpus. Record p50/p95 latency and use labeled queries to measure recall@10 and nDCG@10.
2. CSV is useful for demonstrating indexing but does not support transactions across barrels. Individual file replacements are atomic; an interrupted import can still leave forward and inverted files inconsistent. Back up existing data before migration. Do not deploy multiple writing server instances against these files.
3. The custom numeric token hash can collide. A durable index should store normalized terms directly or verify terms after hash lookup. The old index covers titles/tags rather than full question and answer text.
4. For a single-machine next version, SQLite FTS5 is a reasonable migration candidate: full-text retrieval across title/body/answer, a durable transaction for imports, weighted ranking, and no separate database service. Benchmark it before choosing the production backend.
5. Unique concurrent searches still start separate Python processes; NLTK startup and CSV parsing remain costs on cache misses. A persistent Python search service with an in-memory index and a bounded worker queue is the next runtime improvement if retaining the custom index.
6. Public deployments need authentication/authorization for uploads, request throttling, and deployment-specific origin/proxy configuration. CORS does not authenticate callers. Restrict access before exposing corpus modification publicly.
7. Legacy offline builders and upload components still exist for reference. Do not mix their writes with the updated API ingestion path without checking schema compatibility.
   They use inconsistent working-directory assumptions and schemas; consolidation into a single documented import command remains a follow-up.
8. The typeface downloads from Google Fonts with local sans-serif fallbacks. Self-host for fully offline usage.

## Should we add RAG?

Yes, if users need synthesized answers across documents or natural-language questions with evidence. If the product goal is finding existing questions and answers quickly, first improve retrieval and measure it. RAG does not repair missing documents, broken indexing, or poor retrieval.

Recommended staged architecture:

1. Normalize and index complete document content, preserving document IDs and source locations. Split long bodies and answers into meaningful chunks with limited overlap.
2. Keep keyword search and add embedding retrieval. Fuse their ranked lists, then optionally rerank a small candidate set. Hybrid retrieval helps preserve exact technical names while finding semantically related text.
3. Add a separate optional **Ask** mode. Retrieve supporting chunks, pass only those chunks to an answer model, and return an answer with clickable source references. Clearly report insufficient evidence and treat retrieved document instructions as untrusted content.
4. Measure retrieval quality, citation correctness, answer faithfulness, latency, and cost with a curated question set before enabling the feature broadly. Cache embeddings by content hash and rebuild only changed chunks.

No model provider, paid API, embedding store, or document upload to an external AI service has been introduced in this revision. Those choices require the corpus size, privacy needs, deployment target, and budget. The new search endpoint and stable IDs provide an integration point for a later retrieval layer.

Primary references: [Elastic hybrid search](https://www.elastic.co/docs/solutions/search/hybrid-search), [Microsoft RAG information retrieval guidance](https://learn.microsoft.com/azure/architecture/ai-ml/guide/rag/rag-information-retrieval).

## Verification performed

Production build and frontend lint passed. Two API-validation tests and five retrieval/ingestion tests passed. Headless Edge checks passed for desktop/mobile layout, search shortcuts, mocked search results and expansion, upload dialog, keyboard Easter egg, and isolation of document scripts. Preview images use fixture search results. The final dark document-frame background was also checked in the browser. End-to-end indexing with real NLTK resources and real-corpus performance remain unverified because those resources and the dataset are absent.
