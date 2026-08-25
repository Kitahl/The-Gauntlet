# SESSION A — TEST #3R — BASE ONLY

Run only the BASE arm of the certified paired Space retest. This must be a fresh conversation. Do not run SPACE and do not score.

## Frozen authority

Repository: `Kitahl/The-Gauntlet`

Frozen package commit: `b7d949f711738cfd3485d45ae74c7df964c93245`

Experiment: `SESSION3R_TEST3R_SPACE`

Intended model: **GPT-5.6 Sol**

Expected work: exactly **100 predictions** in frozen order:

- 50 primary verified-release retrieval tasks
- 30 secondary multi-source comparison tasks
- 20 exploratory release-history navigation tasks

Per-task hard limits:

- 6 individual web search queries
- 8 source follow-up/read operations
- 450 visible output tokens maximum

## Absolute isolation boundary

Before and during BASE inference you may access from the frozen package only:

- `benchmarks/session3r_test3r_space/MANIFEST.json`
- `benchmarks/session3r_test3r_space/VALIDATION_REPORT.json`
- `benchmarks/session3r_test3r_space/CI_CERTIFICATION.json`
- `benchmarks/session3r_test3r_space/base/questions.jsonl`

Always fetch them at exact commit `b7d949f711738cfd3485d45ae74c7df964c93245`.

Do NOT list the package directory recursively.

Do NOT access:

- `space/questions.jsonl`
- the Space skill/blob
- any path under `gold/`
- `score.py`
- builder/validator source
- workflow files or workflow logs
- Git history/diffs for this package
- previous Test #3 conversations or question packs

If semantic answer-key material enters model-visible context before both arms are committed, stop with:

`INVALID — RAW GOLD EXPOSURE`

## Benchmark-artifact firewall

During ordinary web research, if a search result points to `Kitahl/The-Gauntlet` or contains `session3r_test3r_space` / `SESSION3R_TEST3R_SPACE`, do not open it or use it as evidence. Record `BENCHMARK_ARTIFACT_HIT` and continue with another search result.

The sealed gold is encoded, so a mere artifact-domain hit is not itself semantic gold exposure. If an actual expected answer/source mapping somehow appears from the benchmark package, stop as invalid.

## Tool policy

Package loading may use the connected GitHub tool.

Actual benchmark research must use ordinary public web search and webpage reading only. Do not use the connected GitHub API/connector to query target repositories, releases, tags, or metadata during inference. Do not use Python, a calculator, another LLM, or another Gauntlet skill to solve tasks.

Search accounting counts every individual query, including batched search records. Follow-up accounting counts opens, clicks, finds, direct webpage reads, and equivalent source-read operations.

Unused budget does not transfer between tasks.

## Verify package

Before inference, fetch only the three public certification files above and verify:

- experiment ID = `SESSION3R_TEST3R_SPACE`
- `SOURCE_VALIDATED = true`
- `GOLD_SEMANTICALLY_HIDDEN_FROM_SEARCH = true`
- 100 unique tasks
- BASE and SPACE each require 100 predictions
- 50/30/20 section counts
- resource limits = 6 searches, 8 follow-ups, 450 visible tokens
- frozen Space blob = `a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

Then state:

`PACKAGE VERIFIED — BASE ONLY — GOLD NOT ACCESSED — SPACE NOT LOADED`

## Load BASE questions without exposing SPACE

Fetch only:

`benchmarks/session3r_test3r_space/base/questions.jsonl`

at exact commit `b7d949f711738cfd3485d45ae74c7df964c93245`.

Read it in bounded line ranges, preferably 10 JSONL rows at a time. Do not fetch `space/questions.jsonl`.

## Inference

Run all 100 tasks in exact file order.

For every task, perform independent web research under the matched budget. Prefer first-party evidence when you naturally judge it appropriate, but do not reconstruct or emulate the Space checklist from prior context.

The benchmark prompt specifies the exact JSON answer schema. Return that exact JSON as the submitted answer.

In addition, preserve the fully qualified evidence URLs actually used.

Create one immutable receipt row per item:

```json
{"id":"...","condition":"BASE","answer":{},"evidence_urls":["https://..."],"search_queries_used":0,"followups_used":0,"visible_response":"..."}
```

Do not add information from later tasks to earlier predictions.

## Commit BASE

After exactly 100 predictions, write:

- `SESSION3R_BASE_RECEIPT.jsonl`
- `SESSION3R_BASE_RECEIPT.sha256.txt`

The SHA-256 file must contain the hash of the exact receipt bytes.

Verify 100 unique task IDs before commitment.

Then state exactly:

`BASE COMMITTED — 100 predictions frozen`

After commitment, do not revise any answer, evidence URL, or resource count.

Do not open gold. Do not load Space. Do not score. End the session.
