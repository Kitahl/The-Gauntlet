# Audit of `FOIL_UPDATE_EVIDENCE_LEDGER_2026-08-22.md`

**Ledger SHA-256:** `4f6f712360bb05c9354e4ea0ed18a7251e8a639356fd41ae8f59bfcd57de5c8a` (matches the value stated with the file).
**Rule applied:** a claim enters the backlog only if it was re-checked against the repository, a primary source, or a re-run. Unverifiable claims are listed as UNVERIFIED and do not drive engineering.
**Date:** 2026-08-23. Tree audited: `main` at `ba03be5` plus all remote experiment refs.

## A. Claim verdicts

| # | Ledger claim | Verdict | Evidence |
|---|---|---|---|
| A1 | `tools/foil_profile.py` is schema v1; `observe()` has no `verified`/`verifier`; `independent = assistance in {"none","independent"}`; independent counters drive classification | **CONFIRMED** | `main:tools/foil_profile.py` (blob `280a19d`), lines 20, 207-258 |
| A2 | `skills/foil/SKILL.md` blob `81a9b13...`; `tools/foil_hook.py` blob `b2d3503...` | **CONFIRMED** | `git rev-parse main:<path>` |
| A3 | Hook prints profile + deep context + task metadata; no payload budget, no `as_of`, no supersession | **CONFIRMED** | `tools/foil_hook.py` has no budget/as_of handling; `foil_profile.compact_context()` |
| A4 | Frozen V2 at commit `8a44d68341d57f8157f3e13a22c6aca882446ead` | **REFUTED as a locator** - commit exists on none of 120 remote refs | `git cat-file -t` fails after a full fetch |
| A5 | `experiments/foil_vnext/SPEC_V2.md` blob `806d741...`, `EVALUATION_V2.md` blob `9c9d0bc...`, `tests/test_foil_vnext_v2.py`, `runtime_policy_v2.py` exist | **CONFIRMED at `origin/experiment/foil-vnext5-vnext@9540860`** (not in `main`) | `git log --find-object`, `git ls-tree` |
| A6 | ARC 9/12 -> 11/12, GPQA 18/24 -> 21/24, pooled 27/36 -> 32/36, 6 improvements / 1 regression, exact McNemar p = .125 | **PARTIAL: historical 27/36 CONFIRMED; vNext 32/36 REFUTED by re-score.** Mechanical re-score of the same 48-item vNext prediction file against the harness gold gives **ARC 12/12, GPQA 23/24, pooled 35/36; discordant 8 vNext-only / 0 historical-only; exact two-sided McNemar p = 0.0078**. The cited `FOIL_VNEXT_BENCHMARK_AUDIT_2026-08-22.md` and `foil_vnext_benchmark_results_2026-08-22.json` exist in no ref and nowhere on disk; the ledger's figures came from an unarchived LLM scoring session. | re-run of `gpqa_prepare_score.prepare()` + `hle_arc_prepare_score.prepare()` against `benchmark_predictions_FOIL_VNEXT.json` (its 48 ids match the repo's 2026-08-22 prediction ids exactly) |
| A6-caveat | - | Even the stronger number is **not superiority evidence**: historical predictions came from earlier disjoint-subset sessions (the repo prediction files say "disjoint deterministic subsets"); the vNext run was a later same-item re-run in a different GPT-5.6 Sol session with the questions already public; gold-blindness of the vNext session rests on a question-only pack, not on a verifiable receipt; GPQA/ARC are public. Directional only. | protocol fields in `benchmark_runs/2026-08-22/*.json` |
| A7 | HLE invalid as primary evidence (gold exposed) | **CONFIRMED** | `hle_arc_prepare_score.py:27` `HLE_EXCLUDED_IDS` |
| A8 | BrowseComp four-way: BASE 1/2, FOIL 2/2, FOIL_PROFILE 1/2, FOIL_MM 0/2 | **CONFIRMED** (disjoint subsets, n = 2 each, exact-normalized scoring, 20+ post-exposure exclusions) | `benchmark_runs/2026-08-22/browsecomp_four_way_results.json` `summary` |
| A9 | Layer 2A: 0/2 under p = .70 has probability .09 | **CONFIRMED** (0.3^2 = 0.09) | arithmetic |
| A10 | Claude Code hooks: output incl. `additionalContext` capped at 10,000 chars; `UserPromptSubmit` default timeout 30 s; hooks in skill frontmatter | **CONFIRMED** verbatim | code.claude.com/docs/en/hooks |
| A11 | "resume can replay stale injected values" | **UNVERIFIED** - not stated in the hooks doc; `SessionStart` does have a `resume` matcher | same doc |
| A12 | AgentPoison: >80% average attack success with <0.1% poison rate | **CONFIRMED** (abstract, arXiv 2407.12784) | arXiv abstract |
| A13 | Persona study: 162 personas, 4 LLM families, 2,410 factual questions; personas do not improve performance; automatic persona selection is about random | **CONFIRMED** (arXiv 2311.10054 / OpenReview CvrzffhXSg) | arXiv abstract |
| A14 | MINJA, Huang et al. 2023, RPKT, PSI-KT, TASA, TutorBench, Borchers & Shou, Harvard RCT, Tutor CoPilot, DeepTutor | **NOT RE-FETCHED** - identifiers copied from the ledger; none is load-bearing for an engineering change in this pass | - |
| A15 | "FOIL should not compete by becoming a larger tutor platform" | design opinion, not a claim | - |

## B. Valid updates to add before the benchmark run

All are measured defects or cheap validity gates; none depends on an efficacy claim.

| ID | Update | Ledger items | Lands in |
|---|---|---|---|
| B1 | Migration receipt (`old_sha256`, `new_sha256`, `migrated_at`, `derivation_version`) emitted on v1 -> v2 load; derivation algorithm versioned in the profile | #2, #4 | `tools/foil_profile.py` |
| B2 | Test: marking relevance or running a solve-only path leaves competence state byte-identical; only `observe()` with verified + independent evidence can move it | #3 | `tests/test_foil_profile_v2.py` |
| B3 | Injection hardening of `compact_context()` / hook output: closed vocabulary for competence-bearing fields; `goals` / `preferences` free text sanitized (control chars stripped, length capped, never raw notes); total payload <= 4,000 chars (host hard cap is 10,000); `as_of`, `profile_sha256`, `derivation_version` attributes; negative tests for oversized or malformed profiles | #9, #10, A3, A10, A12 | `tools/foil_profile.py`, `tools/foil_hook.py` |
| B4 | `GAP_KINDS` enum <-> `SKILL.md` section 5 drift test (same mechanism as the assistance-ladder drift test) | #8 | `tools/foil_interventions.py`, `tests/` |
| B5 | Port `runtime_policy_v2.py` + `test_foil_vnext_v2.py` from `origin/experiment/foil-vnext5-vnext@9540860` as `tools/foil_policy.py` rather than writing a new kernel; V2 mechanisms stay labelled experimental hypotheses | #16-#21, A5 | Phase 3 |
| B6 | Guard binding records `model`, `effort`, `allowed_tools`, `isolation_session_id`; a duplicate isolation id fails closed | #13 | `tools/foil_task_guard.py` |
| B7 | Write-capable tools denied by default under the broker unless the registry permits | #11, #12 | `tools/foil_tool_broker.py` |
| B8 | Protocol wording: the 4-config Claude run is a **contract test of the skill text at matched cost**, not a personalization test; profile arms (`CORRECT_PROFILE` / `WRONG_PROFILE` / `NOPROFILE`) are the next experiment and need a real profile. `docs/BENCHMARKS.md` records the re-scored vNext evidence with the A6 caveat, never the ledger's 32/36. | #15, #23, #24, A6 | Phase 4/5 docs |

## C. Already covered by the 0.5.1 plan (no new work)

#1 verified/verifier fields; #5 per-item assessment replay; #6 screening-only Layer 2A (SCREEN tier weight 0.4, never load-bearing alone); #7 task-first order (SKILL.md); #11 capability registry; #13 task guard; #14 gold separation (existing harness); #27 tool success is not competence (`ExecutionOwner.TOOL` -> weight 0).

## D. Deferred (trigger named) or rejected

| Item | Decision | Trigger |
|---|---|---|
| #25 routing oracle gap, #26 intervention analytics, #28 hidden/given localisation, #30 `MODEL_RISK` | DEFER | after the 4-config run produces route traces |
| #33 bounded prerequisite tracing, #34 ladder/fading trial, #35 delayed transfer endpoint | DEFER | human study with at least one real profile |
| #36-#40 IRT / KT / RL / graph / crypto | DEFER (agrees with the research report) | calibrated item bank or longitudinal data |
| #41-#45 rejects | AGREE | - |
| #22 Mastermind selective | policy only; the n = 2 result is descriptive | - |

## E. Open items this audit could not close

- The vNext prediction session is not archived in the repo. The 35/36 re-score may be committed with gold hashes as *descriptive* evidence, or dropped from prose entirely; it must never appear as "validated".
- Ledger commit `8a44d68...` should read `9540860` wherever cited.
