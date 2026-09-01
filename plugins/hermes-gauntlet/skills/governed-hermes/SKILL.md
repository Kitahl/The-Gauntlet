---
name: governed-hermes
description: Start, diagnose, or resume Bastion Hermes, BASTION-01's task-bound governed Hermes integration for Codex. Use when the user asks for Hermes, Bastion Hermes, governed Hermes, Hermes Gauntlet, a Gauntlet-backed Hermes session, or continuation by Gauntlet task ID. Governed turns include persistent privacy-bounded Counterform/FOIL adaptation automatically; use the sibling hermes-foil skill for an explicit adaptation task.
---

# Bastion Hermes

Use the bundled `scripts/hermes_gauntlet.py` helper. Resolve `<plugin-root>` as the parent of the `skills` directory containing this skill; do not assume the shell working directory is the plugin directory.

## Authority boundaries

- Launch tasks only through `gauntlet_host.cli` with the `governed` profile. Do not run the vendored Hermes agent directly for task work because that bypasses Gauntlet task binding and Soul finalization.
- Treat the printed Gauntlet task ID (`task-...`) as the public resume handle. Never invent, expose, or ask the user for Hermes's derived internal session ID.
- Never release a canonical task automatically. Run `release` only when the user explicitly requests release after reviewing a `CLEARED` finalization.
- Do not interpret model prose or raw tool output as a canonical receipt. Report the final Soul status produced by the host.
- Bastion Hermes applies persistent Counterform/FOIL adaptation on every prompt. Do not claim that this background adaptation clears an explicit adaptation obligation; explicit work must use the sibling `hermes-foil` skill and an `ADAPTATION` task.

## Workflow

1. Diagnose the local installation before the first run:

   ```powershell
   python "<plugin-root>\scripts\hermes_gauntlet.py" doctor --json
   ```

2. If no provider/model configuration hint is present, explain that the user must configure the pinned Hermes CLI or supply a provider, model, and matching credential environment variable. Do not request or print secret values. When the user asks to configure Hermes interactively, run `setup` in a user-visible terminal:

   ```powershell
   python "<plugin-root>\scripts\hermes_gauntlet.py" setup
   ```

3. For a new task, prefer one bounded turn so Codex receives a complete result and the task ID:

   ```powershell
   python "<plugin-root>\scripts\hermes_gauntlet.py" start --prompt "<task>"
   ```

   Preserve the `[GAUNTLET TASK] task-...` value in the response so the user can resume it.

4. Continue the same task only with its Gauntlet task ID:

   ```powershell
   python "<plugin-root>\scripts\hermes_gauntlet.py" continue --task-id "task-..." --prompt "<next turn>"
   ```

5. Use interactive chat only when the user specifically wants a terminal session:

   ```powershell
   python "<plugin-root>\scripts\hermes_gauntlet.py" chat
   ```

   In chat, `/task` prints the bound task ID and `/quit` exits. Resume later with `chat --task-id "task-..."`.

6. Release only on an explicit user request:

   ```powershell
   python "<plugin-root>\scripts\hermes_gauntlet.py" release --task-id "task-..." --confirm-release
   ```

Pass `--model` and `--provider` to `start`, `continue`, or `chat` only when the user specifies overrides or the diagnosed base configuration is absent. Use `--root` only to override discovery with a different valid Gauntlet checkout.
