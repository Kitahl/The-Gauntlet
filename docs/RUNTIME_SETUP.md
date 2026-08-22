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

## Optional OpenRouter judgment / multi-agent tools

No API key is required for deterministic monitoring or strong repeated-tool-loop detection.

For optional LLM-based boundary precision, independent red-team review, or SNAP:

```bash
export OPENROUTER_API_KEY="..."
export GAUNTLET_JUDGE_MODEL="provider/model"
```

Additional fall-over credentials may be supplied as `OPENROUTER_API_KEY_1` through `_16`.

Credentials are environment-only. The public runtime never reads a project-specific keystore.

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

Two independent consistent observations may support `PROMISING_STRENGTH` or `POSSIBLE_GAP`; mixed evidence stays `UNCERTAIN`. Newer task-diagnostic evidence overrides stale onboarding evidence.
