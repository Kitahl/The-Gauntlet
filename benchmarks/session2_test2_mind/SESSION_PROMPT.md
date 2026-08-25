# SESSION #2 — TEST #2 — MIND VS BASE

Run the frozen package as a fresh-session comparison of GPT-5.6 Sol BASE versus the frozen Mind skill.

## Frozen package reference

Repository: `Kitahl/The-Gauntlet`

Package commit: `cc312f53cffffc0a2340b66cd5a59cbafa327c44`

Development branch: `benchmark/session2-test2-mind-package`

Every package file used for inference or scoring must be fetched at the exact package commit above. Do not use `main`, an unpinned branch head, or a later package revision.

## Absolute gold boundary

Before both condition receipts are committed, you may fetch only these four files at package commit `cc312f53cffffc0a2340b66cd5a59cbafa327c44`:

- `benchmarks/session2_test2_mind/MANIFEST.json`
- `benchmarks/session2_test2_mind/assignments.json`
- `benchmarks/session2_test2_mind/questions/omni_math_rule_questions.jsonl`
- `benchmarks/session2_test2_mind/questions/bbeh_questions.jsonl`

Do **not** list or recursively fetch the package directory. Do **not** open, search, click, inspect, render, summarize, or otherwise access any path containing:

`gold/SEALED_UNTIL_BOTH_ARMS_COMMIT`

Do not inspect `build_package.py`, `build_package_ci.py`, workflow logs, git history, commit diffs, scorer code, or prior benchmark traces before inference. Those routes may expose gold or selection details. If any gold/reference answer enters model-visible output before both arms commit, stop and report `INVALID — RAW GOLD EXPOSURE`.

## Model and exclusions

- Intended model: GPT-5.6 Sol. Record the active model if available.
- Mirror/FOIL: prohibited.
- Soul, Space, Reality, Power, Time, Gauntlet, Meditate, Council, Mastermind: prohibited.
- Web, Python, calculator, symbolic solver, theorem prover, and external retrieval: prohibited during inference.
- Local code may be used only after both arms commit for scoring.

## BASE phase

1. Read `assignments.json` and the two question files only.
2. Solve all records assigned `BASE` in the frozen order: Omni-MATH-Rule first, then BBEH.
3. For each Omni problem, provide concise supporting reasoning and end with `FINAL ANSWER: <answer>`.
4. For each BBEH task, obey its required output format exactly.
5. Preserve one prediction JSON object per task with `id`, `condition`, `answer`, and optional `response`.
6. After all 20 are complete, print a SHA-256 or content hash of the BASE prediction block if possible and state exactly:

`BASE COMMITTED — 20 predictions frozen`

Do not revise BASE afterward.

## Load Mind

Only after BASE commitment, fetch the exact Git blob from `Kitahl/The-Gauntlet`:

`8c27111809e390910a74b1380b9fbce12b016999`

Verify the SHA. Activate only that Mind specification. Do not load its runtime or any other Gauntlet component.

## MIND phase

Solve all 20 records assigned `MIND` in frozen order under the same closed-book, tool-free rules and output format. Do not use BASE answers as evidence. Then hash/freeze the prediction block and state exactly:

`MIND COMMITTED — 20 predictions frozen`

Do not revise either arm afterward.

## Scoring phase

Only now may you access these paths at package commit `cc312f53cffffc0a2340b66cd5a59cbafa327c44`:

- `benchmarks/session2_test2_mind/gold/SEALED_UNTIL_BOTH_ARMS_COMMIT/`
- `benchmarks/session2_test2_mind/score.py`
- `benchmarks/session2_test2_mind/grader.py`
- `benchmarks/session2_test2_mind/requirements-score.txt`

Combine all 40 committed predictions into JSONL and run `score.py`. Install `requirements-score.txt` only after both commitments. Preserve unresolved Omni mathematical-equivalence cases for reference-solution adjudication rather than silently marking them wrong.

## Required report

Report Omni-MATH-Rule and BBEH separately:

- BASE and MIND correct/n and accuracy;
- Wilson 95% intervals;
- difficulty breakdown for Omni;
- family breakdown for BBEH;
- first-5 and all-10 stability views for each benchmark;
- all failures and unresolved equivalence cases;
- visible response-length cost;
- validity audit.

Use exactly one verdict: `POSITIVE DIRECTION`, `MIXED`, `TIE / NO OBSERVED DIFFERENCE`, `NEGATIVE DIRECTION`, or `INVALID / INCONCLUSIVE`.

This is a disjoint matched-pair exploratory test, not an isolated same-item causal A/B. Do not claim general Mind efficacy from the sample.
