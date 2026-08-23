# Runtime setup: typed EGR runtime + Process Assurance + FOIL

Skill directories remain `SKILL.md`-only. Executable runtime lives under `tools/`, hook wiring under `.claude/`, configuration in `.gauntlet.json`, and private state under `.egrt/state/` or the existing FOIL profile directory.

## Install

Use the repository's hash-locked environment for reproducible evaluation:

```bash
python -m pip install --require-hashes -r requirements-lock.txt
python -m playwright install chromium
```

The typed runtime itself uses the standard library plus dependencies already present in the runtime environment. Optional external verifiers such as Z3, Lean, Coq, Hypothesis, mutmut or Semgrep are feature-detected; absence is reported as `UNAVAILABLE` rather than installed or invented automatically.

## Hook order

`.claude/settings.json` wires the typed runtime around the existing Gauntlet/FOIL hooks.

### SessionStart

1. `egrt_hook.py session` initializes a privacy-safe runtime event.
2. `gauntlet_monitor.py snapshot` snapshots governing state.
3. `gauntlet_boundary.py reset` resets compatibility loop detection.
4. `foil_hook.py session` loads/creates the active FOIL profile.

### UserPromptSubmit

1. `egrt_hook.py prompt` stores only a one-way prompt hash, length bucket and explicit module aliases.
2. `foil_hook.py prompt` performs the existing domain/facet relevance adaptation and context injection.

Neither generic typed runtime nor FOIL profile persistence stores raw prompt text.

### PreToolUse

The typed hook stores only a canonical tool-input hash + tool name. Existing Gauntlet pre-tool/pre-write checks then enforce stale-state and evidence-ledger policies.

### PostToolUse

The typed hook records a hashed tool event, then the existing Gauntlet hook updates state after commits where applicable.

### Stop

1. existing `gauntlet_boundary.py` performs compatibility `frame`/`costume` turn-boundary checks;
2. `egrt_hook.py stop` emits a release-gate warning only when an explicit typed active task exists and load-bearing obligations are unresolved.

This avoids forcing typed task state onto simple conversations while making substantial registered work mechanically auditable.

## Typed task workflow

Start a task:

```bash
python tools/soul_runtime.py start --goal "verify the release candidate"
```

Add obligations:

```bash
python tools/soul_runtime.py add <task-id> ENGINEERING --claim "candidate passes release checks"
python tools/soul_runtime.py add <task-id> ASSURANCE --claim "release process has no unresolved typed assurance hazard"
```

Component tools write receipts under `.egrt/state/runtime/receipts/`. Check the gate:

```bash
python tools/soul_runtime.py gate <task-id>
```

A missing load-bearing receipt is `UNKNOWN`; a missing verifier is `UNAVAILABLE`; a failed obligation is `ISSUE`.

## Component runtime entry points

| Component | Runtime | Engineering spec |
|---|---|---|
| Soul | `tools/soul_runtime.py` | `docs/specs/SOUL_ENGINEERING_SPEC.md` |
| Gauntlet | `tools/gauntlet_runtime.py` | `docs/specs/GAUNTLET_ENGINEERING_SPEC.md` |
| Meditate | `tools/meditate_runtime.py` | `docs/specs/MEDITATE_ENGINEERING_SPEC.md` |
| Council | `tools/council_runtime.py` | `docs/specs/COUNCIL_ENGINEERING_SPEC.md` |
| Mind | `tools/mind_runtime.py` | `docs/specs/MIND_ENGINEERING_SPEC.md` |
| Space | `tools/space_runtime.py` | `docs/specs/SPACE_ENGINEERING_SPEC.md` |
| Reality | `tools/reality_runtime.py` | `docs/specs/REALITY_ENGINEERING_SPEC.md` |
| Power | `tools/power_runtime.py` | `docs/specs/POWER_ENGINEERING_SPEC.md` |
| Time | `tools/time_runtime.py` | `docs/specs/TIME_ENGINEERING_SPEC.md` |
| FOIL | existing tools + `tools/foil_runtime_bridge.py` | `docs/specs/FOIL_INTEGRATION_SPEC.md` |

## Gauntlet support registry

```bash
python tools/egrt_runtime.py coverage
```

This prints the declared support mode and monitorability requirements for all ten operations. An operation is not presented as automatically monitored unless the runtime has the typed state needed for its mechanical part.

## Meditate

Create a JSON `DecisionState` and run:

```bash
python tools/meditate_runtime.py decision.json --obligation <obligation-id>
```

Quantitative VOC is used only if probabilities/utilities/costs are supplied and valid. Otherwise the runtime uses ordinal dominance or returns `UNKNOWN`.

## Council

Council is a library/state machine in `tools/council_runtime.py`. It requires 3–6 distinct seat questions, a skeptic/adversarial seat, frozen first-pass commitment hashes, verified reveals, cross-critique participation from every seat, overlap diagnostics, and a DIRECT control matched to the same artifact hash and frozen total-budget hash. Without that control the REVIEW receipt remains `UNKNOWN`.

## Mind

The initial adapters provide restricted exact arithmetic and optional Z3 SMT2 execution. Z3 is never assumed to exist. Solver receipts explicitly state that the result applies to the supplied encoding.

## Space

`tools/space_runtime.py` registers a bounded search plan and currently supports OpenAlex + Crossref. Search failure/saturation produces explicit scope states. `NOT_FOUND_WITHIN_SCOPE` never means nonexistence.

## Reality

`tools/reality_runtime.py` stores falsifiable candidate objects and refuses complete admission without cleared prior-art discovery evidence and negative-control/transfer/ablation/verifier plans.

## Power

`tools/power_runtime.py` executes explicit argv plans with `shell=False`, timeouts, output hashes, mandatory/optional checks and named defect-class coverage. Raw generic output is not persisted in receipts.

## Time

`tools/time_runtime.py` provides a dependency-light paired binary baseline: discordance table, exact conditional McNemar p-value, Wilson intervals and Holm step-down correction. Repeated/adaptive monitoring requires a separately validated anytime-valid method; the stdlib implementation explicitly records that as unresolved.

## Evidence ledger compatibility

The legacy optional evidence ledger remains supported. vNext additionally recognizes content-addressed runtime receipts. A content hash verifies object integrity, **not semantic truth**; claim–evidence entailment remains a separate obligation where needed.

## Privacy

Generic typed runtime state stores only hashes and small structured metadata. Component-specific evidence artifacts may contain substantive content when the user deliberately saves them as evidence. OpenRouter-backed optional tools still transmit supplied content to the configured provider; the typed local runtime does not change that boundary.

## FOIL

Classification is a decision on a Beta posterior over verified, independent, user-executed evidence (`tools/foil_evidence.py`), not a count rule. Two observations are no longer enough: the default policy requires at least `min_effective_n` (4.0) of real-work weight before any load-bearing verdict, unverified and assisted observations carry zero weight, and onboarding-screen evidence is admissible but can never on its own reach `PROMISING_STRENGTH` or `POSSIBLE_GAP`. Newer task-diagnostic evidence outranks stale onboarding evidence by exponential recency decay, which downweights old evidence without erasing it.

The existing Layer 1/2A/2B profile/calibration system remains intact. FOIL can affect routing/representation but cannot self-certify another module's factual obligation.


## Frozen-run tool broker (PreToolUse)

`tools/foil_task_guard.py` is an accounting ledger and says so: it cannot stop a caller that never invokes it. `tools/foil_tool_broker.py` is the enforcement half. It is registered as the first `PreToolUse` hook in `.claude/settings.json` and runs before the tool executes, so a budgeted operation cannot be spent without being charged.

`FOIL_TASK_RUN` is the single activation switch.

| Variable | Meaning |
| --- | --- |
| `FOIL_TASK_RUN` | Path to an existing task-guard state file. **Unset or empty: the hook is inert.** Set: a frozen run is asserted to be in progress. |
| `FOIL_TASK_ID` | Task id the run was opened with. |
| `FOIL_TASK_CONDITION` | Condition the run was opened with. |
| `FOIL_TASK_PROMPT` **or** `FOIL_TASK_PROMPT_SHA256` | Prompt text, or its SHA-256. A hook process normally holds only the digest, so `verify_binding` accepts either. |
| `FOIL_TASK_ALLOW_WRITES` | Optional. `1` admits write-capable tools for this run. No other value opts in. |

With `FOIL_TASK_RUN` unset or empty the hook prints nothing and exits 0, so ordinary sessions are unaffected.

Once `FOIL_TASK_RUN` is set, a broken configuration **denies** rather than falling back to inert. A missing state file gives `frozen FOIL run state file missing: <path>; failing closed`; a missing `FOIL_TASK_ID`, `FOIL_TASK_CONDITION`, or prompt binding gives `frozen FOIL run is only partially configured: ...; failing closed`. Setting the variable is an assertion that a run is in progress, so anything wrong with the rest of it is misconfiguration, not absence — and allowing there would let a partially configured run proceed completely unguarded while looking exactly like a healthy one. The refusal is scoped to the tools the broker budgets: an unbudgeted tool is guarded by nothing in any case, so refusing it would break unrelated work without protecting a single budget unit.

Tool mapping:

| Tool | Budgeted operation |
| --- | --- |
| `WebSearch`, `mcp__*search*` | `search` |
| `WebFetch`, `mcp__*fetch*`, `mcp__*read_url*` | `followup` |
| `Edit`, `Write`, `MultiEdit`, `NotebookEdit`, `Bash`, `PowerShell` | `write` |
| anything else | not brokered; the call is allowed untouched |

Deny contract. On a refusal the hook writes exactly one JSON object to stdout and exits 0:

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}
```

A call is denied when the budget for its operation is exhausted, when `FOIL_TASK_ID`/`FOIL_TASK_CONDITION`/prompt digest do not match the frozen run, when the run is configured but incomplete or its state file is absent, when the ledger cannot be locked, when the state file is unreadable or corrupt, and for write-capable tools unless `FOIL_TASK_ALLOW_WRITES=1` (no capability in `tools/foil_capabilities.py` declares `writes=True`, so the registry has nothing to route a write through). Every unexpected failure denies rather than allowing: the hook fails closed. On allow it prints nothing and exits 0.

Charging point, stated plainly: a `PreToolUse` hook cannot observe the tool result, so the budget unit is charged at reservation. A call the host subsequently fails still consumes its unit. The ledger therefore records attempts admitted, not successful retrievals, and a receipt must be read that way. Both allows and denies are appended to the run's hash-chained event ledger, so `foil_task_guard.py attest` covers the broker's decisions too.

Ledgers written under `.foil/` are gitignored; nothing here transmits data anywhere. Model egress remains only what the OpenRouter section above describes.

## Repository boundary

Mastermind remains external. The repository runtime does not import, install, call or persist Mastermind implementation/state. Historical external-audit evidence may reference it as provenance only.
