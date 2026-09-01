---
name: hermes-foil
description: Run Bastion Hermes with explicit, persistent, task-bound Counterform adaptation. Use when the user asks for Counterform, FOIL, Mirror, adapt to me, teach me this, check me against the evidence, identify what I am missing, or create an adaptation obligation.
---

# Bastion Hermes Counterform

Use the bundled `scripts/hermes_gauntlet.py` helper. Resolve `<plugin-root>` as the parent of the `skills` directory containing this skill; do not assume the shell working directory is the plugin directory.

## Required route

- Create explicit FOIL work only with the `foil` command. It forces the Gauntlet obligation kind to `ADAPTATION` and prefixes the prompt with `/foil` when needed.
- Preserve the printed Gauntlet task ID (`task-...`) as the public resume handle. Resume with `continue --task-id`; never expose or invent Hermes's derived internal session ID.
- Continue to include `/foil` or the specific adaptation obligation ID when asking Hermes to satisfy an explicit FOIL obligation. Only an explicitly requested adaptation receipt may clear that obligation.
- Treat background Counterform/FOIL profile adaptation on ordinary governed turns as useful context, not proof that an explicit adaptation obligation is complete.
- Never release a canonical task automatically. Run `release` only after an explicit user request and a `CLEARED` Soul finalization.

## Workflow

1. Diagnose the installation without printing secret values:

   ```powershell
   python "<plugin-root>\scripts\hermes_gauntlet.py" doctor --json
   ```

2. Start a new explicit Counterform adaptation task:

   ```powershell
   python "<plugin-root>\scripts\hermes_gauntlet.py" foil --prompt "<adaptation request>"
   ```

3. Continue the same task with its Gauntlet task ID:

   ```powershell
   python "<plugin-root>\scripts\hermes_gauntlet.py" continue --task-id "task-..." --prompt "/foil <next adaptation turn>"
   ```

4. Report the host-produced Soul status and evidence. If the status is not `CLEARED`, keep the task bound and explain the remaining obligation.

Pass `--model` and `--provider` only when the user specifies overrides or diagnosis shows that the base Hermes configuration is absent. Use `--root` only to select a different valid Gauntlet checkout.
