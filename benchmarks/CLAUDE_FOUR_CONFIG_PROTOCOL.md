# Four-config Claude contract test — preregistration

**Status: PREREGISTERED, NOT YET RUN.** This document is committed before any unit executes.
Nothing in it may be edited after the first prediction is committed; a change after that point
is an amendment and must be added as a dated section at the end, never a silent edit.

**Harness:** `benchmarks/harness/claude_four_config_runner.py`
**Statistics:** `benchmarks/harness/paired_stats.py`
**Run directory:** `benchmark_runs/2026-08-23/`

---

## 1. What this experiment tests, and what it does not

The question is narrow and deliberately so: **does the FOIL skill text change task outcomes when
it is the only thing that changes, at matched cost?**

The FOIL arm receives the skill file as an appended system prompt and the invocation line
`/foil solve` in front of the item. Everything else — the item text, the answer-format
instruction, the model, the effort level, the tool allowance, the tool budget, the working
directory, the settings file — is byte-identical between arms.

This is a **contract test of the skill text at matched cost.** It is **not** a personalization
test. No profile is loaded in either arm. The profile arms (`CORRECT_PROFILE`, `WRONG_PROFILE`,
`NOPROFILE`) are the **next** experiment and require a real profile that does not yet exist;
mixing them in here would confound the skill text with the profile content.

Prohibited readings of any result this design can produce:

- "FOIL improves reasoning" — the design cannot separate skill text from prompt-length effects
  beyond the matched-cost control it does implement.
- "FOIL is equivalent to BASE" — see §9. A null at these sample sizes is absence of evidence.
- Any pooled headline number across configurations or across benchmarks.

## 2. Configurations

Four Claude Code configurations, the full cross of two models and two effort levels.

| Config | `--model` | `--effort` |
|---|---|---|
| `C-SL` | `sonnet` | `low` |
| `C-SH` | `sonnet` | `high` |
| `C-OL` | `opus` | `low` |
| `C-OH` | `opus` | `high` |

Every item is run under **all four configurations, in both conditions**: units = items × 4 × 2.

## 3. Conditions and the sealed condition map

Two conditions on the **same items**:

- **BASE** — the prompt body alone.
- **FOIL** — `--append-system-prompt-file skills/foil/SKILL.md`, and the prompt body prefixed
  with the literal line `/foil solve` followed by a newline. No other difference.

Predictions and receipts record the **opaque condition id** (`A` / `B`), never the condition
name. The mapping is written before any run to:

```
benchmark_runs/2026-08-23/condition_map.sealed.json
sha256 = 60b1933777806b99661dc14bbb436a1051fa922128828fb4b6256c360d4536ab
```

That digest is over the file's bytes with **LF** line endings. Every artifact this harness
hashes is written LF-only, because a text-mode write would otherwise make the pinned hash
differ between the machine that sealed the file and the machine that checks it.

The map is a deterministic function of the order seed `20260823`, so it can be pinned by hash
here before a single item is selected, and any later regeneration that disagrees is a detectable
tamper rather than an ordinary rerun. For this seed the map came out `A = BASE`, `B = FOIL`.
That is stated plainly rather than re-rolled: re-drawing a seed because the drawn map looks
insufficiently opaque is exactly the post-hoc choice preregistration exists to prevent.

**What the seal buys, stated honestly.** The map is sealed against relabelling, not against
operator knowledge. It prevents arms from being renamed after the outcomes are known — the file
is committed and its hash is preregistered here, which is what makes a later edit detectable. It
does **not** blind the operator, who necessarily knows which arm carries the skill text, and it
does not blind the harness, which must know which flags to pass.

## 4. Ordering

For each `(item, config)` pair the execution order of the two conditions is randomised from a
per-pair seed derived from the order seed `20260823`, the benchmark name, the item id and the
config id. A systematic ordering effect — a warm cache, a tiring operator, a drifting service —
therefore cannot line up with one arm.

## 5. Execution mechanics (identical in both arms)

Every unit, without exception:

- runs with **cwd = a fresh empty temporary directory**, created for that unit and removed after
  its receipt is written;
- runs with `--settings <generated json>` whose **only** content is the broker `PreToolUse` hook.
  The hook command is resolved at runtime from the running interpreter and the repository
  location; no path is baked into the harness. No other setting, hook, permission or MCP server
  is present;
- runs with a child environment **stripped** of `CLAUDECODE*`, `CLAUDE_CODE_*` and `CLAUDE_PID`,
  so a nested `claude -p` cannot attach to the launching session;
- receives its prompt on **stdin** (a benchmark prompt can exceed the Windows command-line cap);
- claims a **distinct `isolation_session_id`** in the task-guard sidecar index. Two units sharing
  a session id fails closed rather than being reported as isolated;
- opens a `foil_task_guard` run bound to `task_id`, `condition`, `prompt_sha256`, `model`,
  `effort`, `allowed_tools` and `isolation_session_id`, and is charged through
  `tools/foil_tool_broker.py` as a `PreToolUse` hook.

Output format is `--output-format json`; the envelope is parsed by the existing
`foil_models` `claude_json` parser, which fails loudly rather than scoring a usage banner as an
answer.

`--max-turns` does not exist in the CLI version this protocol targets (2.1.206) and is not used.

### Per-benchmark tool policy

| Benchmark | `--tools` | `--allowedTools` | Budget enforced by the broker | Subprocess timeout |
|---|---|---|---|---|
| GPQA-Diamond | `""` (none) | — | `search=0`, `followup=0` (any tool call is refused) | 900 s |
| BrowseComp | `WebSearch,WebFetch` | `WebSearch,WebFetch` | `search=12`, `followup=12` | 1200 s (20 min) |

The broker charges at **reservation** time, because a `PreToolUse` hook cannot observe a tool's
result. The ledger therefore records *attempts admitted*, not *successful retrievals*, and the
receipts must be read that way.

## 6. Items

**GPQA-Diamond — 24 items.** Selected by the existing `benchmarks/harness/gpqa_prepare_score.py`
selection at seed `20260825`. The harness calls that selection and **discards the gold mapping it
returns**; no gold field is ever written to the run directory.

**BrowseComp — 12 fresh items, seed `20260831`.** The candidate pool excludes every row any
earlier pilot already exposed: the complete 40-row four-way selection chain (scored items plus
all three exclusion lists in `benchmark_runs/2026-08-22/browsecomp_four_way_results.json`) and
the 20 rows the legacy BrowseComp pilot consumed at seed `20260824` — 60 rows in total. The
harness asserts that count and refuses to select against an incomplete exclusion set. The
decrypted private review material stays out of the repository (it is gitignored).

`contamination_status = known_public` for both benchmarks. GPQA-Diamond and BrowseComp are
public datasets; neither arm can be assumed uncontaminated, and the paired design is what makes
that survivable — contamination applies equally to both arms of the same item.

## 7. Replicates: one, and why that is a declared weakness

**Replicates = 1 per cell. This is an owner decision, and this run is declared EXPLORATORY
because of it.**

`tools/foil_models.py` classifies the `claude_cli` preset as **`NONDETERMINISTIC`**: the CLI
offers no seed, so `Determinism.requires_replicates` is `True` for it. The session bench's own
`design` output states that with a non-seeded model in the pool, "a single sample per cell
measures noise rather than effect" and sets `replicates_per_cell = 3`.

This run knowingly departs from that. A per-item outcome here therefore mixes the condition
effect with sampling noise, and the design cannot separate them. That is recorded as a limit of
this run, not resolved by it.

## 8. Answer extraction

Both conditions' prompts carry the **same** answer-format instruction:

- GPQA: end the reply with a final line `ANSWER: <letter>`.
- BrowseComp: end the reply with a final line `ANSWER: <exact answer>`.

The **last** matching line in the reply is the prediction. A reply with no such line is recorded
`INVALID` with reason `no ANSWER line` — never converted into a guess, and never re-rolled. A
GPQA answer line that is not one of `A`–`D` is `INVALID` for the same reason.

A unit is recorded `INVALID` when the envelope's **`is_error` flag is true** *or* its
**`subtype` is anything other than `success`**. Both signals are consulted: either alone can
miss a case — a failure flagged without a changed subtype, or a non-success subtype on an
unflagged envelope — and scoring a failed run is worse than recording an extra `INVALID`. The
`claude_json` parser in `tools/foil_models.py` surfaces `is_error` (bool, default `false`) and
`subtype` directly, so neither is inferred. A unit whose subprocess times out or whose envelope
fails to parse is recorded `INVALID` with the model error text.

**An `INVALID` unit is never re-run after gold has been opened.** Before gold is opened, a
re-run is permitted only if it is recorded as such in the receipt. An item with an `INVALID`
unit on either arm is dropped from that configuration's paired analysis and listed by id in
`excluded_invalid_items` — dropped items are named, never silently absent.

## 9. Analysis plan (fixed before any data exists)

Per configuration, on the items where both arms produced a valid prediction:

1. **Discordance table** — `both_correct`, `BASE_only`, `FOIL_only`, `both_wrong`, `n`.
2. **Primary test** — **mid-p McNemar, two-sided**, α = 0.05.
3. **Sensitivity** — **exact conditional McNemar, two-sided**. Reported always, not only when it
   agrees.
4. **Per-arm Wilson 95% intervals** on accuracy (Wilson, not Wald: Wald has zero width at 0/n and
   n/n, exactly the cells a benchmark this small hits).
5. **Multiplicity** — **Holm** across the four configurations, on the primary p-values.

Scorers are the existing normalisers: `gpqa_prepare_score.norm` for GPQA, and
`browsecomp_four_way_prepare_score.normalize` (exact-normalized string match) for BrowseComp.
The BrowseComp scorer is **not** the official BrowseComp LLM judge and results are not
comparable to published BrowseComp numbers.

### Gold discipline

`score` **refuses to run** unless the predictions file is committed: `git status --porcelain` on
that path must be empty **and** `git log -1` on it must be non-empty. Both are necessary — the
first alone passes for a file git has never seen. Every receipt asserts `gold_opened = false`;
only the results file carries `gold_opened = true`.

### Cost and time

Every receipt records `total_cost_usd`, `num_turns`, `duration_ms` and `session_id` from the
envelope. Matched cost is a design claim, so it is reported as measured per-arm cost, not
assumed from the flags.

## 10. Power — what these sample sizes can and cannot detect

Computed with `benchmarks/harness/bench_foil_session.py`'s own `mcnemar_power` /
`exact_two_sided` (two-sided exact McNemar, α = 0.05, 20 000 simulations, seed 20260822).

`python benchmarks/harness/bench_foil_session.py power` reports the resolvability floor and the
sizes needed for 80 % power:

```
n=5    best attainable p=0.0625  alpha reachable: False
n=6    best attainable p=0.0312  alpha reachable: True
n=10   best attainable p=0.0019  alpha reachable: True
n=25   best attainable p=0.0000  alpha reachable: True

items for 80% power:
  p_disc=0.2,p_fav=0.7,reps=1            -> 300
  p_disc=0.2,p_fav=0.7,reps=3            -> 150
  p_disc=0.3,p_fav=0.75,reps=1           -> 150
  p_disc=0.3,p_fav=0.75,reps=3           -> 75
  p_disc=0.3,p_fav=0.85,reps=1           -> 75
  p_disc=0.3,p_fav=0.85,reps=3           -> 50
```

At the sizes this run actually uses, with one replicate:

| Assumed effect | power at **n = 24** (GPQA) | power at **n = 12** (BrowseComp) |
|---|---:|---:|
| 20 % discordant, 70 % favouring FOIL | **0.035** | **0.002** |
| 30 % discordant, 75 % favouring FOIL | **0.148** | **0.019** |
| 30 % discordant, 85 % favouring FOIL | **0.326** | **0.043** |

**Stated plainly: this run is not powered to detect any plausible effect.** Even a large effect
(30 % of items discordant, 85 % of those favouring FOIL) is detected roughly one time in three at
n = 24 and one time in twenty-three at n = 12. At 30 % discordance the expected number of
discordant pairs is 7.2 for GPQA and 3.6 for BrowseComp — and **six** discordant pairs is the
minimum at which a two-sided exact test can reach α = 0.05 at all, so BrowseComp will usually
have too few discordant pairs for the sensitivity test to be able to reject under any split.

Consequences that are binding, not advisory:

- A **non-significant result is uninformative**. It must be reported as "not powered to detect",
  never as a null, an equivalence, or a "no harm" finding.
- A **significant result is directional evidence at best** and is a candidate for replication at
  a preregistered size, not a conclusion.
- The honest use of this run is **operational**: does the harness execute cleanly end to end, do
  the budgets hold, do both arms produce parsable answers, and what do a run's real cost and
  duration look like — the inputs a properly sized run needs.

## 11. Amendments

None. Any amendment after the first committed prediction is appended below with its date and
reason.
