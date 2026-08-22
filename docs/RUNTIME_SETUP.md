# Runtime setup: Process Assurance hooks + FOIL profiles

The skill directories contain `SKILL.md` only. Runtime automation lives in `.claude/`, `tools/`, project config, and user-local profile storage.

## Install

```bash
python -m pip install -r requirements-runtime.txt
```

Claude Code project hooks are committed in `.claude/settings.json`. The configuration follows current Claude Code hook events (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`) and uses `${CLAUDE_PROJECT_DIR}` rather than an absolute workstation path.

## Process Assurance configuration

Edit `.gauntlet.json` to define which files are governing authority for your repository.

Runtime state is written under `.egrt/state/` and must remain gitignored. No state is written into `.git/`.

The optional evidence-ledger commit gate is disabled by default. To enable it:

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

## Optional OpenRouter judgment / multi-agent tools

No API key is required for deterministic monitoring or strong tool-loop detection.

For optional LLM-based boundary precision, red-team review, or SNAP:

```bash
export OPENROUTER_API_KEY="..."
export GAUNTLET_JUDGE_MODEL="provider/model"
```

Additional fall-over credentials may be supplied as `OPENROUTER_API_KEY_1` through `_16`.

Keys are never read from project files or a hidden project-specific keystore.

## FOIL saved profiles

Profiles are stored outside the repository by default:

- Linux/macOS: `${XDG_CONFIG_HOME:-~/.config}/egrt/foil/profiles/`
- Windows: `%APPDATA%/egrt/foil/profiles/`
- override: `EGR_FOIL_PROFILE_DIR`

Create and activate a profile:

```bash
python tools/foil_profile.py init alice --activate
python tools/foil_profile.py set alice --goal "become stronger at formal research reasoning" --domain software_engineering
```

Run onboarding:

```bash
python tools/foil_assessment.py start \
  --setup-text "I work on research software, causal inference, UI design, and papers" \
  --out foil_assessment.json --responses foil_responses.json
```

Fill the generated response JSON, then apply the result:

```bash
python tools/foil_assessment.py score foil_assessment.json foil_responses.json \
  --profile alice --out foil_assessment_report.json
```

The SessionStart/UserPromptSubmit hooks inject only a compact profile summary. Raw prompts are not stored by the profile tool.

## Usage-time adaptation

FOIL should record task evidence after diagnostic interactions:

```bash
python tools/foil_profile.py observe alice \
  --domain causal_inference --outcome incorrect --assistance none \
  --confidence 90 --source usage --representation "DAG identification"
```

If a new task requires a domain not already present, `observe` creates it as a `CANDIDATE`. Repeated observations or explicit setup relevance promote it to active profile context. One miss never creates a stable weakness.
