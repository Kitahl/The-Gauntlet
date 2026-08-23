# Runtime setup: Process Assurance hooks + FOIL profiles

The skill directories contain `SKILL.md` only. Runtime automation lives in `.claude/`, `tools/`, project config, and user-local profile storage.

## Install

```bash
python -m pip install -r requirements-runtime.txt
```

Claude Code project hooks are committed in `.claude/settings.json`. They use current hook events (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`) and `${CLAUDE_PROJECT_DIR}` rather than an absolute workstation path. Command hooks use exec-form `args` so paths with spaces remain portable.

## Process Assurance configuration

Edit `.gauntlet.json` to define the governing files for your repository.

Runtime state is written under `.egrt/state/` and is gitignored. No state is written into `.git/`.

The optional evidence-ledger commit gate is disabled by default. Enable it only after pointing it at a real evidence ledger:

```json
{
  "ledger": {
    "enabled": true,
    "path": "evidence/ledger.json"
  }
}
```

Expected minimal ledger shape:

```json
{
  "claims": [
    {"id": "C1", "status": "supported", "evidence": ["results/run-001.json"]}
  ]
}
```

### Hook behavior

- `SessionStart` snapshots governing state, resets the turn-boundary budget, and loads/creates the active FOIL profile.
- `PreToolUse(Bash)` checks stale governing state before git sync operations and runs the optional evidence-ledger gate before `git commit`.
- `PreToolUse(Edit|Write|NotebookEdit)` surfaces stale governing state before mutation.
- `PostToolUse(Bash)` snapshots after successful commits.
- `Stop` runs the Process Assurance `frame`/`costume` turn-boundary evaluator and respects `stop_hook_active` to avoid continuation loops.
- `UserPromptSubmit` updates compact task-domain and cross-cutting-facet relevance metadata and injects the active FOIL context. It does **not** store raw prompts.

The turn-boundary state stores only lossy similarity fingerprints of recent assistant messages; the assistant-message text itself is not persisted by this runtime.

## Optional OpenRouter judgment / multi-agent tools

No API key is required for deterministic monitoring or strong repeated-tool-loop detection.

For optional LLM-based boundary precision, independent red-team review, or SNAP:

```bash
export OPENROUTER_API_KEY="..."
export GAUNTLET_JUDGE_MODEL="provider/model"
```

Additional fall-over credentials may be supplied as `OPENROUTER_API_KEY_1` through `_16`.

Credentials are environment-only. The public runtime never reads a project-specific keystore.

### Privacy and external-data boundary

Deterministic Gauntlet monitoring and FOIL profile/relevance updates are local. They do not require OpenRouter and do not send prompt content to an external model provider.

When an optional OpenRouter-backed boundary judge, independent red-team review, or SNAP run is enabled, the content supplied to that optional tool — including a prompt, brief, target, and generated review context as applicable — is transmitted to OpenRouter and the configured model provider. Do not enable those optional paths for secrets or material that must remain local. Provider retention/privacy terms apply independently of this repository.

Local FOIL profile directories and Gauntlet state directories are owner-restricted to `0700` and their files to `0600` on POSIX systems. Windows uses the normal user-profile/filesystem ACL model. These controls are defense in depth; users should still protect their operating-system account and backups.

## FOIL saved profiles

Profiles are stored outside the repository by default:

- Linux/macOS: `${XDG_CONFIG_HOME:-~/.config}/egrt/foil/profiles/`
- Windows: `%APPDATA%/egrt/foil/profiles/`
- override: `EGR_FOIL_PROFILE_DIR`

On the first hooked session, a **blank `default` profile** is created automatically if no active profile exists. It contains no assumed strengths or weaknesses.

For multiple people, create named profiles:

```bash
python tools/foil_profile.py init alice --activate
python tools/foil_profile.py init bob
python tools/foil_profile.py activate alice
```

Add explicit goals/preferences/relevant domains:

```bash
python tools/foil_profile.py set alice \
  --goal "become stronger at formal research reasoning" \
  --domain software_engineering \
  --preference independent_first=5
```

## Layer 1 — broad onboarding

The first screen contains 20 generated objective items across quantitative reasoning, formal reasoning, probability/statistics, causal inference, software engineering, systems/reliability, research/evidence literacy, scientific method, security/privacy, and planning/decision-making.

It also includes context, work-style preferences, self-estimates, confidence calibration, and open design/UX, creativity, and explanation tasks.

```bash
python tools/foil_assessment.py start \
  --setup-text "I work on research software, causal inference, UI design, and papers" \
  --domain theorem_proving \
  --out foil_assessment.json --responses foil_responses.json
```

Fill the generated response JSON, then score and apply it:

```bash
python tools/foil_assessment.py score foil_assessment.json foil_responses.json \
  --profile alice --out foil_assessment_report.json
```

The result is a **provisional routing prior**, not a personality/IQ/clinical/employment diagnosis.

## Layer 2A — structured cross-cutting screen

After Layer 1, run:

```bash
python tools/foil_layer2.py start \
  --profile alice --mode standard \
  --out foil_layer2.json --responses foil_layer2_responses.json
```

Standard mode contains 24 objective scenarios across 12 cross-cutting facets plus open design, creative-search, and explanation tasks. It samples formalization, systems decomposition, error detection, evidence discipline, causal and quantitative reasoning, execution, prioritization, confidence calibration, transfer, tool selection, and uncertainty management.

Score and apply it:

```bash
python tools/foil_layer2.py score \
  foil_layer2.json foil_layer2_responses.json \
  --profile alice --out foil_layer2_report.json
```

The open responses remain `NEEDS_RUBRIC_REVIEW` and are not copied into the saved profile automatically.

## Layer 2B — adaptive real-work / transfer calibration

Generate the next profile-specific plan:

```bash
python tools/foil_calibration.py start --profile alice --out foil_deep_calibration.json
```

Record only checked outcomes:

```bash
python tools/foil_calibration.py record \
  --profile alice \
  --probe-id formal_reasoning:harder_transfer:1 \
  --domain formal_reasoning \
  --facet transfer_adaptation \
  --kind harder_transfer \
  --outcome pass \
  --assistance none \
  --verified \
  --confidence 85 \
  --representation "changed notation"
```

Inspect profile maturity:

```bash
python tools/foil_calibration.py status --profile alice
```

The structured screen improves cold-start depth, but real-work/transfer evidence remains required for a genuinely informative profile.

## Usage-time adaptation

Prompt-time hooks mark both domains and cross-cutting facets as relevant without treating relevance as competence. Performance evidence is recorded only after a real diagnostic observation:

```bash
python tools/foil_profile.py observe alice \
  --domain causal_inference --outcome incorrect --assistance none \
  --confidence 90 --source usage --representation "DAG identification"
```

If a task requires a domain not already present, `observe` accepts any domain name and creates it as a candidate. The expanded relevance registry covers more than forty common research/professional families, and arbitrary custom domains remain supported.

Classification is a decision on a Beta posterior over verified, independent, user-executed evidence (`tools/foil_evidence.py`), not a count rule. Two observations are no longer enough: the default policy requires at least `min_effective_n` (4.0) of real-work weight before any load-bearing verdict, unverified and assisted observations carry zero weight, and onboarding-screen evidence is admissible but can never on its own reach `PROMISING_STRENGTH` or `POSSIBLE_GAP`. Newer task-diagnostic evidence outranks stale onboarding evidence by exponential recency decay, which downweights old evidence without erasing it.


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

This repository's runtime contains Gauntlet and FOIL. Mastermind is not imported, installed, or required by the hooks/runtime. Historical validation prose may record that an external audit procedure was used, but its implementation and benchmark-control material must remain outside this repository; CI contains a regression test for that boundary.
