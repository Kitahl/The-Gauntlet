# SESSION B — TEST #3R — SPACE ONLY

Run only the SPACE arm of the certified paired Space retest. This must be a fresh conversation independent of BASE. Do not access BASE material and do not score.

## Frozen authority

Repository: `Kitahl/The-Gauntlet`

Frozen package commit: `__PACKAGE_COMMIT__`

Experiment: `SESSION3R_TEST3R_SPACE`

Intended model: **GPT-5.6 Sol**

Frozen Space blob SHA:

`a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

Expected work: exactly **100 predictions** in frozen order:

- 50 primary verified-release retrieval tasks
- 30 secondary multi-source comparison tasks
- 20 exploratory release-history navigation tasks

Per-task hard limits, identical to BASE:

- 6 individual web search queries
- 8 source follow-up/read operations
- 450 visible output tokens maximum

## Absolute isolation boundary

Before and during SPACE inference you may access from the frozen package only:

- `benchmarks/session3r_test3r_space/MANIFEST.json`
- `benchmarks/session3r_test3r_space/VALIDATION_REPORT.json`
- `benchmarks/session3r_test3r_space/CI_CERTIFICATION.json`
- `benchmarks/session3r_test3r_space/space/questions.jsonl`

Always fetch package files at exact commit `__PACKAGE_COMMIT__`.

You may additionally fetch the exact Space blob by SHA before opening any benchmark question.

Do NOT access:

- `base/questions.jsonl`
- BASE predictions or BASE receipt
- any path under `gold/`
- `score.py`
- builder/validator source
- workflow files or workflow logs
- Git history/diffs for the package
- another Gauntlet skill
- previous Test #3 traces

If semantic answer-key material enters model-visible context before both arms are committed, stop with:

`INVALID — RAW GOLD EXPOSURE`

## Benchmark-artifact firewall

During ordinary web research, if a search result points to `Kitahl/The-Gauntlet` or contains `session3r_test3r_space` / `SESSION3R_TEST3R_SPACE`, do not open it or use it as evidence. Record `BENCHMARK_ARTIFACT_HIT` and continue.

A package-domain hit alone is not semantic gold exposure because gold is stored as gzip+base64. If an actual expected answer/source mapping somehow appears, stop as invalid.

## Load Space before questions

Before opening `space/questions.jsonl`, fetch exact blob:

`a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

Verify it is the `scoutbot` / Research Discovery skill and record the exact blob SHA.

Activate **only** this Space procedure.

Do not activate or use:

- Soul
- Mind
- Reality
- Power
- Time
- Gauntlet
- Meditate
- Council
- Mirror / FOIL
- Mastermind

Do not use Space runtime helpers. This tests the frozen procedural skill itself.

## Tool policy

Package/skill loading may use the connected GitHub tool.

Actual benchmark research must use ordinary public web search and webpage reading only. Do not use the connected GitHub API/connector to query target repositories, releases, tags, or metadata during inference. Do not use Python, calculator, another LLM, or another Gauntlet skill to solve tasks.

Space may alter research strategy only: mechanism translation, query reformulation, synonym expansion, source prioritization, source inspection, provenance checking, and scoped uncertainty.

It receives no extra searches, reads, or output budget.

## Verify package

Before inference, verify from the public certification files:

- experiment ID = `SESSION3R_TEST3R_SPACE`
- `SOURCE_VALIDATED = true`
- `GOLD_SEMANTICALLY_HIDDEN_FROM_SEARCH = true`
- 100 unique tasks
- 50/30/20 section counts
- limits = 6 searches, 8 follow-ups, 450 visible tokens
- Space blob matches exactly

Then state:

`PACKAGE VERIFIED — SPACE LOADED — GOLD NOT ACCESSED — BASE NOT ACCESSED`

## Load SPACE questions

Fetch only:

`benchmarks/session3r_test3r_space/space/questions.jsonl`

at exact commit `__PACKAGE_COMMIT__`.

Read it in bounded line ranges, preferably 10 rows at a time. Do not fetch BASE questions.

## Inference

Run all 100 tasks in exact file order using the frozen Space procedure under the matched resource limits.

Return the exact JSON answer schema specified by each benchmark prompt and preserve fully qualified evidence URLs actually used.

Create one immutable receipt row per item:

```json
{"id":"...","condition":"SPACE","answer":{},"evidence_urls":["https://..."],"search_queries_used":0,"followups_used":0,"visible_response":"..."}
```

## Commit SPACE

After exactly 100 predictions, write:

- `SESSION3R_SPACE_RECEIPT.jsonl`
- `SESSION3R_SPACE_RECEIPT.sha256.txt`

Verify 100 unique IDs and hash the exact receipt bytes.

Then state exactly:

`SPACE COMMITTED — 100 predictions frozen`

Do not revise predictions afterward. Do not open gold. Do not score. End the session.
