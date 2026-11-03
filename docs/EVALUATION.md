# Evaluation with Ragas

## What is ready

The evaluation tools are separate from the search server. They use Ragas 0.4.3's collections API, a Fireworks OpenAI-compatible judge, and the existing local Ollama embedding adapter. A separate virtual environment keeps the extra libraries out of the production runtime.

There are ten source-checked seed cases in `server/evaluation/cases.jsonl`: nine questions about facts explicitly reported in training documents and one synthetic unanswerable probe. These are a pilot set, not a statistically representative production benchmark. Review and expand them to 50–100 cases before drawing broader conclusions. The validation CSV's `Y` labels are question-quality categories, not reference answers; they are not used as RAG ground truth.

## Monitor indexing

A chat heartbeat checks every 30 minutes, stays quiet while work proceeds normally, and notifies on completion, failure, or a sustained stall. It does not run paid evaluations automatically. Codex must be available on this machine for local checks.

For a manual read-only check, run from `server`:

```powershell
npm run rag:progress
```

This counts embeddings only in the currently configured model/prefix/version space. It never treats vectors from another model as completion. A process-permission result of `workerAlive: null` means unknown, not stopped. The heartbeat can check host processes when needed. A stall requires three consecutive unchanged checks while the machine is available.

## Installation

The local environment is `server/.venv-eval`. For another PC, from `server`:

```powershell
python -m venv .venv-eval
.venv-eval\Scripts\python.exe -m pip install -r evaluation/requirements.txt
```

Keep `server/.env` private. Existing Fireworks credentials and `BASE_URL` are reused. Optional independent judge overrides:

```dotenv
EVAL_JUDGE_BASE_URL=https://api.fireworks.ai/inference/v1
EVAL_JUDGE_MODEL=your-enabled-judge-model
EVAL_JUDGE_API_KEY=your-judge-key
```

If these are absent, scoring uses `RAG_MODEL` and the existing Fireworks key. Reports explicitly flag when the judge and answer model are the same; prefer a different judge for stronger independent evidence. No hosted OpenAI default endpoint or automatic model choice is used.

## Preflight: no model calls

From `server`:

```powershell
npm run eval:check
npm run eval:capture -- --dry-run --limit 2
```

The first command checks installed packages and non-secret configuration. The second validates seed cases and current index coverage without generation or judge calls. `rag:progress` is the authoritative completion check.

## Capture actual pipeline responses

After indexing completes:

```powershell
npm run eval:capture -- --mode hybrid --limit 5 --output evaluation/reports/hybrid.jsonl
```

This makes answer-generation calls to Fireworks. It captures the actual question, all excerpts supplied to the generator (not just the ones it cited), response, source IDs, expected evidence IDs, timings, model identity, embedding space, coverage, and revision.

By default, semantic/hybrid captures refuse an incomplete index. For a deliberately partial diagnostic run, pass `--allow-partial`; the report remains labeled partial. Use `--resume` with the same output file to skip completed case IDs after interruption. Existing files are otherwise protected from overwrite; a different model or embedding space requires a new file.

For comparison, capture identical cases using:

```powershell
npm run eval:capture -- --mode bm25 --limit 5 --output evaluation/reports/bm25.jsonl
npm run eval:capture -- --mode semantic --limit 5 --output evaluation/reports/semantic.jsonl
```

BM25 does not call embeddings. Semantic-only refuses lexical fallback. Hybrid records actual fallback warnings if the embedding service is unavailable. Do not compare runs labeled as different actual modes or partial coverage as if they were complete-index equivalents.

## Score captured answers

```powershell
npm run eval:score -- --input evaluation/reports/hybrid.jsonl --limit 5
```

This sends captured questions, answers and relevant excerpts/reference answers to the configured Fireworks judge. Ragas may make multiple judge calls for each metric. Scoring is sequential, defaults to five cases, limits each judge output to 2,048 tokens, disables SDK retries, limits structured-output attempts, and times out each metric. It does not run inside normal user searches or the monitor.

Metrics:

- **Faithfulness:** whether answer claims are supported by supplied excerpts.
- **Answer relevancy:** whether the response addresses the question; generated comparison questions are embedded locally with Ollama.
- **Context precision / recall:** whether retrieved excerpts cover the supplied reference answer and place useful evidence first.
- **Known-source recall, MRR and nDCG:** deterministic document-level checks against the seed's known evidence IDs. These gold ID sets are not exhaustive lists of every potentially relevant document, so do not interpret them as complete corpus-wide recall labels.
- **Abstention counts:** expected-unanswerable cases are assessed separately. A refusal is not automatically assigned perfect faithfulness or zero answer relevance.

Missing references skip reference-based metrics. Refused/unverified responses skip answer-quality metrics; retrieval metrics can still be scored against references. Failed or non-finite judge scores remain null with explicit errors and are excluded from averages. Means include scored-case counts so a high average cannot conceal extensive failures. Reports are saved after each case and contain data from your corpus; they are ignored by Git.

A passing model judgment is not proof of truth or citation entailment. Manually review some outputs, especially unsupported-answer probes and cases with high relevance but low faithfulness. Do not choose universal thresholds before calibrating against reviewed cases.

## References

- [Ragas faithfulness](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/faithfulness/)
- [Ragas answer relevancy](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/answer_relevance/)
- [Ragas context precision](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/context_precision/)

## Verification status

The isolated installation includes a compatibility pin for `langchain-community==0.4.1`; 0.4.2 removed modules that Ragas 0.4.3 still imports. The verified environment is recorded in `server/evaluation/requirements.lock.txt`.

Twenty-five Python unit/regression tests and the evaluation/provider validation tests passed. A real Ragas collections runtime test executed all four metrics with an in-process fake judge and fake embeddings; it passed without network/model calls. To reproduce that plumbing check from `server`, run `.venv-eval\Scripts\python.exe evaluation/test_ragas_runtime.py`. Model/API-backed quality scores have not been run automatically.

A synthetic provider-smoke input is available at `evaluation/fixtures/smoke.jsonl` if you explicitly want to test the live judge. Any resulting scores are labeled as synthetic fixture checks and must not be presented as corpus benchmark results.


Current workspace embedding provider: Fireworks Qwen3 Embedding 8B. Ragas relevancy uses the configured embedding provider, so it now makes paid Fireworks embedding requests instead of local Ollama calls. The judge still uses the separate configured judge settings. No paid Ragas evaluation is started by indexing or monitoring.


## Quality improvement priorities after the pilot

All three modes found the known source at rank one on the five pilot cases. The pilot cannot establish a retrieval winner. Hybrid verified three answers; lexical and semantic each verified two. Faithfulness/relevancy exclude citation failures: report verified coverage alongside those means.

- Run all ten prepared cases, including abstention, then expand to 50–100 reviewed cases: paraphrases, ambiguity, absent answers, multiple-source evidence, and adversarial instructions. Keep a held-out set when tuning.
- Add real source answer bodies. The current corpus contains questions only; reported facts are supported, but many technical solutions are absent.
- Diagnose invalid citations and improve format adherence without weakening validation or fabricating source references.
- Configure an independent EVAL_JUDGE_MODEL; the pilot answer and judge model were the same. Manually label a subset for citation support and correctness.
- Compare chunk sizes, evidence diversity, candidate counts, and optional reranking on development cases. Assess source recall/MRR, context quality, verified coverage, abstention correctness, latency and cost together.
- Repeat matched runs to estimate variability. Different verified subsets cannot establish a winner from their relevance means. Perfect conditional faithfulness is not overall system accuracy.

Normal Search uses native Node SQLite BM25 with a bounded 30-second revision-aware cache. It calls neither embeddings nor generation, and no longer starts Python. Node 22.13+ is required (Node 24 is installed). Ask retains hybrid RAG. These changes do not launch paid evaluation runs.


## StackSample staged migration (2026-10-30)

45,000 deterministically sampled answered questions were joined to their top two available answers by score (65,114 answer bodies), yielding 143,398 passages. Source answers are not labeled accepted: StackSample lacks that field. Common tags include JavaScript, Java, C#, PHP, Android, Python, and C++. The original question-only index remains active until staged embedding completion.

Matched development embedding probe: nine source-checked queries against 64 answer excerpts. Nomic v1.5 and Qwen3 Embedding 8B both obtained recall@1/5 and MRR of 1.0. Nomic median document-batch (16 passages) and query times were 2.975s and 1.418s; Qwen3 medians were 3.002s and 1.442s. Timing differences are small and not statistically established. Nomic was selected by the recorded tie-break policy and uses 768-dimensional vectors instead of 4096, reducing local exact-search work and storage. This is not proof of a universally best or fastest model. Full staged embedding uses verified batches of 64 for throughput.

Probe details/configuration/corpus counts are in ignored `server/dataset/stacksample/staged/`. Ten new source-checked/abstention pilot cases are in `server/evaluation/stacksample-cases.jsonl`; those pilot cases overlap the development probe, so they are not held-out quality validation. No new Ragas quality scores are claimed until the staged index finishes and evaluation actually runs.


### Citation reliability follow-up

See ignored `server/evaluation/reports/citations-v2-summary.md`. The matched ten-case hybrid run improved accepted coverage from 3/9 to 9/9 supported questions with one correct absent-evidence refusal. New faithfulness was 1.0 and relevance 0.859 across all nine supported answers, zero metric errors. Different previous scored subsets and self-judge bias preclude claiming general accuracy or an isolated causal relevance gain. A separate five-case GPT/DeepSeek comparison retained GPT for coverage/faithfulness; Llama was unavailable (404). All failures/refusals and timing/selection limitations are retained in the summary. Captures now include final-output diagnostics (not model reasoning), finish reasons, attempt counts and generation token usage; outputs may contain corpus text and remain ignored by Git.


## Expanded 50-case evaluation set (2026-10-31)

`server/evaluation/sets/stacksample-50.jsonl` contains 30 direct source-grounded questions, 10 intended harder constraint/contrast/multi-detail questions, and 10 unanswerable probes. It spans 16 topic buckets using 45 different stored source documents, with no source overlap with the earlier labeled pilots. Difficulty is intended, not empirically measured; no multi-document reasoning coverage is claimed.

References were reviewed by the coding agent against the actual stored historical answers. They are not human-adjudicated labels or independent verification of current technical correctness. Each answerable case includes an evidence quote and source content hash. Five negatives use fictional identifiers confirmed absent across the corpus. Five ask for unstated details in a named stored post; their negative scope is that post, not a claim of corpus-wide absence.

The 30-case development split has 18 direct, 6 harder, and 6 unanswerable cases. The reserved 20-case holdout has 12 direct, 4 harder, and 4 unanswerable cases. Their source documents are disjoint. Keep prompts and retrieval frozen while assessing the holdout. Once holdout outcomes inform tuning, it is no longer untouched validation and a new holdout is needed. Prior pilot files remain unchanged. Both splits were subsequently evaluated in the frozen query-parsing comparison below; holdout outcomes have now been observed.

From `server`, audit labels, hashes, source quotes and splits with no API calls:

```powershell
python evaluation/validate_dataset.py --database dataset/stacksample/staged/rag.sqlite3
```

Use the development split while tuning (these commands make paid model calls):

```powershell
npm run eval:capture -- --cases evaluation/sets/stacksample-50-dev.jsonl --mode hybrid --limit 30 --output evaluation/reports/expanded50-dev-hybrid.jsonl
npm run eval:score -- --input evaluation/reports/expanded50-dev-hybrid.jsonl --limit 30
```

After freezing the implementation, assess the reserved holdout:

```powershell
npm run eval:capture -- --cases evaluation/sets/stacksample-50-holdout.jsonl --mode hybrid --limit 20 --output evaluation/reports/expanded50-holdout-hybrid.jsonl
npm run eval:score -- --input evaluation/reports/expanded50-holdout-hybrid.jsonl --limit 20
```

To deliberately evaluate all 50, supply `--cases evaluation/sets/stacksample-50.jsonl --limit 50` to capture and `--limit 50` to score. Do not mistake the default five-case limit for a full run. Existing default smoke cases are retained for quick regression checks. Choose unique output paths for each retrieval mode/run. Preserve unverified answers and answerable refusals in coverage, distinguish synthetic vs named-post negatives, and report scored-case counts and judge bias alongside quality means. A 50-case set remains a limited evaluation, not a general accuracy guarantee.


## Frozen query-parsing comparison

`eval:capture` accepts `--query-parsing off|on` (default off). Off retains the original query tokenization. On uses the deterministic `lexical-keywords-v1` parser for BM25 only: remove question scaffolding, preserve quoted phrases and technical identifiers, and preserve negation/conditions. Semantic embeddings and answer generation still receive the original question. This is not an LLM query rewrite, typo correction, entity linker or expansion system. Production search/Ask defaults remain unchanged.

The expanded-set comparison uses the same 50 cases per arm (100 captures), frozen prompt/parser/dataset/model/index identity and six-source hybrid retrieval. Both the development and reserved holdout splits are evaluated without mid-run tuning. The parser source hash is captured, and resume rejects changed parser or case settings. `score.py --concurrency 2` bounds concurrent cases, uses separate metric instances per case, and writes ordered checkpoint reports after each completed case. Default concurrency remains one and the maximum is four.

Reproduction (paid API calls):

```powershell
npm run eval:capture -- --cases evaluation/sets/stacksample-50.jsonl --mode hybrid --query-parsing off --limit 50 --output evaluation/reports/expanded50-parsing-off-20261031.jsonl
npm run eval:capture -- --cases evaluation/sets/stacksample-50.jsonl --mode hybrid --query-parsing on --limit 50 --output evaluation/reports/expanded50-parsing-on-20261031.jsonl
npm run eval:score -- --input evaluation/reports/expanded50-parsing-off-20261031.jsonl --limit 50 --concurrency 2
npm run eval:score -- --input evaluation/reports/expanded50-parsing-on-20261031.jsonl --limit 50 --concurrency 2
python evaluation/compare_parsing.py --off evaluation/reports/expanded50-parsing-off-20261031.scores.json --on evaluation/reports/expanded50-parsing-on-20261031.scores.json --output evaluation/reports/expanded50-query-parsing-comparison.json
```

Use unique output names for repetitions; `--resume` is for an interrupted capture with the same configuration, not a fresh run. The comparison includes accepted-answer coverage, answerable refusals, unsupported answers on negatives, unverified outputs, metric errors, matched-case score changes, split/difficulty breakdowns and descriptive end-to-end timings. Concurrent capture and shared short-lived semantic query caching prevent interpreting latency as an isolated parser performance benchmark. The same-model judge and agent-authored reference limitations remain. No production parser toggle is changed automatically from this experiment.


### Completed 50-case parser comparison — 2026-10-31

All 100 captures and both 50-case Ragas scoring passes completed. Known-source recall was 1.000 off versus 0.975 on; source MRR 0.930 versus 0.902. Accepted supported answers were 38/40 versus 37/40, faithfulness 0.985 (38 scored) versus 0.959 (37), and answer relevance 0.789 (38) versus 0.815 (37). Both abstained on 10/10 negatives. End-to-end means were 11.88s versus 11.86s under concurrent activity and shared cache, not a meaningful isolated speed comparison. Three context-recall judge-format errors remained null in the on arm; the off arm had zero metric errors. Matched-score and development/holdout/category details are preserved in the ignored report `server/evaluation/reports/expanded50-query-parsing-comparison.md` and adjacent JSON.

Production remains parsing-off. The on variant is an opt-in evaluation experiment, not a shipped default. A lost lexical signal was identified in the compound phrase `duplicate-deletion`; it was not retuned after seeing holdout outcomes. The 20-case holdout has now been observed. Use a new untouched validation set if these outcomes guide further tuning.


## Comparing self-judging with different-model judges

The independent-judge experiment reuses the exact 50 saved baseline outputs in `server/evaluation/reports/expanded50-parsing-off-20261031.jsonl`. The earlier GPT-OSS 120B score report is the self-judge baseline. Two other account-available Fireworks models, `accounts/fireworks/models/deepseek-v4p1-flash` and `accounts/fireworks/models/qwen3p8-max`, score those same answers, references and retrieved excerpts. No generation, retrieval, embedding index or production model is changed by rescoring. Judge overrides are process-local; server `.env` is not edited.

The manifest in ignored `server/evaluation/reports/judge-comparison-20261031/` records input/report hashes, scorer identity and fixed settings. Both judges passed a one-case compatibility check. Full scoring retains the prior 2048-token judge budget, temperature zero, Ragas 0.4.3 metric definitions, strictness three, bounded retries, per-metric timeout and two-case concurrency. Failed metrics remain null with errors; no silent retry or low-score replacement is applied. These bounds may affect judge models differently and should not be mistaken for inherent model-quality rankings.

Example full-rescore command from `server` (paid calls):

```powershell
$env:EVAL_JUDGE_MODEL='accounts/fireworks/models/deepseek-v4p1-flash'
npm run eval:score -- --input evaluation/reports/expanded50-parsing-off-20261031.jsonl --output evaluation/reports/judge-comparison-20261031/deepseek-scores.json --limit 50 --concurrency 2
```

Repeat with the Qwen model and a unique output filename. Preserve the previous environment value if using these commands in a persistent shell. No change to `RAG_MODEL` is needed. Once every report is complete, compare offline:

```powershell
python evaluation/compare_judges.py --self-report evaluation/reports/expanded50-parsing-off-20261031.scores.json --other deepseek=evaluation/reports/judge-comparison-20261031/deepseek-scores.json --other qwen=evaluation/reports/judge-comparison-20261031/qwen-scores.json --output-directory evaluation/reports/judge-comparison-20261031
```

The reporter rejects mismatched answers, references, contexts, model/prompt/corpus identities or incomplete reports. It provides per-judge means with scored counts, common-case means, paired score differences and agreement, metric failure lists, split/category breakdowns and evidence-backed review packets for large disagreements. A 0.25 case-level score range is a review triage threshold, not a validated definition of judge error. Different judges are not human ground truth; score differences alone cannot prove self-judge bias. Saved capture latency refers to original answer generation, not judge inference speed.


### Completed independent-judge comparison — 2026-10-31

All 50 frozen baseline outputs were rescored by DeepSeek v4.1 Flash and Qwen 3.8 Max, reusing GPT-OSS 120B self-judging as baseline. No answers, retrieval data, production model or .env values changed. On the 28 faithfulness cases all judges scored, means were GPT 1.000, DeepSeek 0.972, Qwen 0.979. Common-case relevance (37 cases) was 0.784, 0.805 and 0.811; context precision (38) was 0.874, 0.872 and 0.859; context recall (31) was 0.968 for all three. These are conditional model judgments, not overall accuracy or proof of self-judging bias.

The different judges had 10 and 19 failed metric values respectively out of 156 attempted; all failures remain explicit/null. Fixed-token output capacity and structured-output reliability require calibration before adopting either model as the official evaluator. Eight cases with large judge disagreements have review packets with final answers, references and full excerpts. Details and full available-case versus common-case tables are in ignored `server/evaluation/reports/judge-comparison-20261031/comparison.md`, `comparison.json`, and `review-cases.md`. Manifest hashes confirm identical saved inputs and scorer settings. No highest-score cherry-picking or silent failure replacement was performed.


## Larger judge-output budget experiment

`eval:score` supports `--judge-max-tokens` from 512 to 8192; its backward-compatible default is 2048. The budget applies only to the evaluation judge, not to generation in the app. The effective budget, metric timeout, temperature, requested metrics and answer-relevance strictness are recorded in each new report. Cross-judge reporting rejects mixed budgets.

The 4096-token experiment is a complete fresh scoring pass for GPT-OSS, DeepSeek and Qwen on the same 50 saved production-baseline outputs. The generation, references, contexts, decoder temperature, timeout/retry settings and metrics are held fixed. Old reports remain preserved. One pass per setting cannot fully separate token-budget effects from judge variability, and a higher score alone does not mean the system improved.

Example (paid calls; run from `server`):

```powershell
$env:EVAL_JUDGE_MODEL='accounts/fireworks/models/deepseek-v4p1-flash'
npm run eval:score -- --input evaluation/reports/expanded50-parsing-off-20261031.jsonl --output evaluation/reports/judge-comparison-4096-20261031/deepseek-scores.json --limit 50 --concurrency 2 --judge-max-tokens 4096
```

Restore the previous judge environment value if using a persistent shell. Use GPT-OSS/Qwen and unique filenames for the other judges. The experiment manifest records frozen input hashes and settings in the ignored reports folder. For publication, distinguish known-source recall, accepted citation/quote coverage, abstention correctness and judge-assessed faithfulness; do not label them overall factual accuracy. State the 50-case pilot size and the metric's actual scored-answer count, and retain independent-judge failures and variation.

### Completed 4,096-token pilot — 2026-10-31

All three judges completed the same 50 saved cases. Final failed metric values decreased from 0 to 0 for GPT-OSS, 10 to 0 for DeepSeek, and 19 to 10 for Qwen. DeepSeek independently scored faithfulness 0.930 (38 accepted answers), answer relevance 0.809 (38), context precision 0.874 (40 answerable cases), and context recall 0.950 (40). GPT self-judge faithfulness was 0.993 (38); Qwen was 0.955 (34), with its remaining failures retained. Larger output capacity improved evaluation coverage; it did not change generated answers or establish an improvement in RAG quality.

Known-source recall remained 40/40, MRR 0.930, nDCG 0.948, accepted citation/quote coverage 38/40, and absent-evidence abstention 10/10. DeepSeek is the headline independent judge because of complete coverage, not highest scores. These are development-pilot results with agent-reviewed references, not overall accuracy or expert-adjudicated benchmark results. Reports: `server/evaluation/reports/judge-comparison-4096-20261031/comparison.md`, `budget-comparison.md`, `budget-comparison.json`, and `review-cases.md`. The manifest confirms unchanged capture and scorer hashes.
