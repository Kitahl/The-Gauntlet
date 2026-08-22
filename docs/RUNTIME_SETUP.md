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
- `UserPromptSubmit` updates only task-domain relevance metadata and injects the active FOIL context. It does **not** store raw prompts.

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

## Questionnaire / onboarding

The onboarding screen covers 20 generated objective items across:

- quantitative reasoning;
- formal reasoning;
- probability/statistics;
- causal inference;
- software engineering;
- systems/reliability;
- research/evidence literacy;
- scientific method;
- security/privacy;
- planning/decision-making.

It also includes open design/UX, creativity, and explanation tasks, plus context, work-style preferences, self-estimates, and confidence calibration.

Setup text automatically adds relevant optional domains such as data/ML, physics, chemistry/materials, biology/life sciences, law/policy, economics/finance, hardware/embedded, product management, human factors, and operations/logistics. Arbitrary custom domains can also be added with repeated `--domain` flags.

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

The result is a **provisional routing prior**, not a personality/IQ/clinical/employment diagnosis. A single miss cannot create a stable weakness; a clean initial screen cannot certify ownership.

## Usage-time adaptation

Prompt-time hooks mark domains as relevant without treating relevance as competence. Performance evidence is recorded only after a real diagnostic observation:

```bash
python tools/foil_profile.py observe alice \
  --domain causal_inference --outcome incorrect --assistance none \
  --confidence 90 --source usage --representation "DAG identification"
```

If a task requires a domain not already present, `observe` accepts any domain name and creates it as a candidate. Two independent consistent observations may support `PROMISING_STRENGTH` or `POSSIBLE_GAP`; mixed evidence stays `UNCERTAIN`. Newer task-diagnostic evidence overrides stale onboarding evidence.
