# Process Assurance runtime

The Process Assurance Framework skill is specification-only. Runtime automation is external:

- `.claude/settings.json` — Claude Code hook wiring;
- `.gauntlet.json` — governing files, budgets, optional ledger policy;
- `tools/gauntlet_monitor.py` — stale-state monitoring;
- `tools/gauntlet_boundary.py` — Stop-hook `frame`/`costume` evaluator;
- `tools/gauntlet_hook.py` — Pre/Post tool adapter;
- `tools/verify_ledger.py` — optional evidence-ledger commit gate;
- `tools/openrouter_bot.py`, `tools/fsa_bots.py`, `tools/snap.py` — optional model-backed review.

State is written under `.egrt/state/`, not `.git/`. Credentials are environment-only. See `docs/RUNTIME_SETUP.md`.
