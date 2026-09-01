# Aegis process-assurance runtime

Aegis is BASTION-01's Process Assurance Layer. Its stable technical route remains
`/gauntlet`. The skill carries the semantic specification; deterministic runtime
automation is provided by:

- `.claude/settings.json` — Claude Code hook wiring;
- `.gauntlet.json` — governing files, budgets, optional ledger policy;
- `tools/gauntlet_monitor.py` — stale-state monitoring;
- `tools/gauntlet_boundary.py` — Stop-hook `frame`/`costume` evaluator;
- `tools/gauntlet_hook.py` — Pre/Post tool adapter;
- `tools/verify_ledger.py` — optional evidence-ledger commit gate;
- `tools/openrouter_bot.py`, `tools/blackgem_runtime.py`, `tools/snap.py` — optional model-backed review, including the Obsidian adversarial cell.

State is written under `.egrt/state/`, not `.git/`. Credentials are environment-only. See `docs/RUNTIME_SETUP.md`.
