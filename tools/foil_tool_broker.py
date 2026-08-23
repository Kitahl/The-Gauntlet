"""PreToolUse broker: the point where a frozen-run tool budget is actually enforced.

Why this file exists
--------------------
`foil_task_guard` is an accounting ledger. It is honest about that: it cannot
stop a caller that never invokes it, and counting `authorize()` calls is not the
same as counting tool calls. This hook is the missing half. Claude Code runs it
*before* the tool executes and refuses the call when the hook returns a deny
decision, so the accounting and the operation are no longer separable by simply
not calling the ledger.

Scope, stated honestly
----------------------
This is an enforcement boundary for tools that go through the host's PreToolUse
hook. It is not a sandbox: a process that bypasses the host, or a tool the host
does not route through hooks, is outside it. What it does buy is that the
budgeted operations a frozen evaluation cares about - search and follow-up
retrieval - cannot be spent silently.

Activation
----------
`FOIL_TASK_RUN` is the single switch:

    FOIL_TASK_RUN            path to an existing task-guard state file
    FOIL_TASK_ID             task id the run was opened with
    FOIL_TASK_CONDITION      condition the run was opened with
    FOIL_TASK_PROMPT         the prompt text, or
    FOIL_TASK_PROMPT_SHA256  its SHA-256 (the hook normally has only the digest)

* `FOIL_TASK_RUN` unset or empty -> no run was intended. The hook prints nothing
  and exits 0, so an ordinary session is unaffected. The alternative would be a
  hook that denies every tool call on every machine that has never started a
  FOIL evaluation.
* `FOIL_TASK_RUN` set -> a run *was* intended, so anything wrong with the rest of
  the configuration is misconfiguration, not absence. A missing state file, or a
  missing `FOIL_TASK_ID` / `FOIL_TASK_CONDITION` / prompt binding, denies the
  call. Allowing there would let a partially configured run proceed unguarded
  while looking exactly like a healthy one, which defeats the boundary.

Scope of that refusal: only tools this broker budgets. An unbudgeted tool is
never guarded by anything, so refusing it would break unrelated work without
protecting a single budget unit.

Charging point
--------------
A PreToolUse hook cannot observe the tool's result, so budget is charged at
reservation time, not on success. A tool call that the host then fails for its
own reasons still consumes its unit. That is the conservative direction for a
budget - it can never under-count - but it does mean the ledger records
*attempts admitted*, not *successful retrievals*, and a receipt must be read
that way.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import foil_capabilities  # noqa: E402
import foil_task_guard as tg  # noqa: E402

SCHEMA = "egrt.foil-tool-broker.v1"


class BrokerConfigError(RuntimeError):
    """A run was intended (FOIL_TASK_RUN is set) but the configuration is unusable."""

#: Exact tool name -> budgeted operation. "write" is not a budget line; it is a
#: category the registry has no write-capable capability for, so it is refused
#: unless the operator explicitly opts in.
TOOL_OPERATIONS: dict[str, str] = {
    "WebSearch": "search",
    "WebFetch": "followup",
    "Edit": "write",
    "Write": "write",
    "MultiEdit": "write",
    "NotebookEdit": "write",
    "Bash": "write",
    "PowerShell": "write",
}

#: Pattern -> budgeted operation, for MCP tools whose names are host-defined.
#: Ordered: the first match wins.
TOOL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"mcp__.*search.*", re.IGNORECASE), "search"),
    (re.compile(r"mcp__.*(fetch|read_url).*", re.IGNORECASE), "followup"),
)

WRITE_OPERATION = "write"


def classify_tool(tool_name: str) -> str | None:
    """Budgeted operation for a tool name, or None to leave the call alone."""
    if not tool_name:
        return None
    if tool_name in TOOL_OPERATIONS:
        return TOOL_OPERATIONS[tool_name]
    for pattern, operation in TOOL_PATTERNS:
        if pattern.fullmatch(tool_name):
            return operation
    return None


def deny(reason: str) -> int:
    """Emit the host's deny decision. Always exits 0: the *decision* is the output."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _binding() -> dict[str, str] | None:
    """Frozen-run binding from the environment.

    Returns None only when `FOIL_TASK_RUN` is unset or empty, which is the one
    case that means "no run was intended". Every other defect raises
    `BrokerConfigError`, because a set `FOIL_TASK_RUN` is an assertion that a
    frozen run is in progress and a broken one must fail closed.
    """
    run = (os.environ.get("FOIL_TASK_RUN") or "").strip()
    if not run:
        return None
    task_id = (os.environ.get("FOIL_TASK_ID") or "").strip()
    condition = (os.environ.get("FOIL_TASK_CONDITION") or "").strip()
    prompt = os.environ.get("FOIL_TASK_PROMPT") or ""
    prompt_sha256 = (os.environ.get("FOIL_TASK_PROMPT_SHA256") or "").strip()

    missing = []
    if not task_id:
        missing.append("FOIL_TASK_ID")
    if not condition:
        missing.append("FOIL_TASK_CONDITION")
    if not prompt and not prompt_sha256:
        missing.append("FOIL_TASK_PROMPT or FOIL_TASK_PROMPT_SHA256")
    if missing:
        raise BrokerConfigError(
            f"frozen FOIL run is only partially configured: FOIL_TASK_RUN is set but "
            f"{', '.join(missing)} is missing; failing closed"
        )
    if not Path(run).is_file():
        raise BrokerConfigError(
            f"frozen FOIL run state file missing: {run}; failing closed"
        )
    return {
        "run": run,
        "task_id": task_id,
        "condition": condition,
        "prompt": prompt,
        "prompt_sha256": prompt_sha256,
    }


def _record(binding: dict[str, str], event: dict[str, Any]) -> None:
    """Append a broker event to the run ledger.

    Best effort by design: this runs on the deny path too, where the state file
    may be exactly what is broken. A failure to journal must not turn a deny
    into an allow, so it is swallowed here and the decision stands.
    """
    path = Path(binding["run"])
    try:
        with tg.exclusive_state_lock(path):
            state = tg.load(path)
            tg._append_event(state, {"time": tg.now(), **event})
            tg._atomic_save(path, state)
    except Exception:  # noqa: BLE001 - journalling must never change the decision
        pass


def handle(payload: dict[str, Any]) -> int:
    tool_name = str(payload.get("tool_name") or "")
    operation = classify_tool(tool_name)
    if operation is None:
        return 0  # unbudgeted tool: not this hook's business, healthy run or not

    try:
        binding = _binding()
    except BrokerConfigError as exc:
        # No run identity was established, so there is nothing to journal
        # against; the decision is the whole output.
        return deny(str(exc))
    if binding is None:
        return 0  # no frozen run in progress: this hook has nothing to enforce

    common = {
        "kind": "BROKER",
        "tool": tool_name,
        "operation": operation,
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
    }

    if operation == WRITE_OPERATION:
        if os.environ.get("FOIL_TASK_ALLOW_WRITES") == "1":
            _record(binding, {**common, "decision": "allow",
                              "reason": "FOIL_TASK_ALLOW_WRITES=1"})
            return 0
        writable = [
            name for name in foil_capabilities.CAPABILITIES
            if foil_capabilities.capability_writes(name)
        ]
        reason = (
            f"frozen FOIL run {binding['task_id']!r}: {tool_name} is a write-capable tool and "
            f"no capability in the registry declares writes=True "
            f"(foil_capabilities.capability_writes is False for all {len(foil_capabilities.CAPABILITIES)} "
            f"capabilities; write-capable: {writable or 'none'}). "
            "Set FOIL_TASK_ALLOW_WRITES=1 to admit writes for this run."
        )
        _record(binding, {**common, "decision": "deny", "reason": reason})
        return deny(reason)

    try:
        with tg.guarded_operation(
            Path(binding["run"]),
            task_id=binding["task_id"],
            condition=binding["condition"],
            prompt=binding["prompt"] or None,
            prompt_sha256=binding["prompt_sha256"] or None,
            operation=operation,
            note=f"pretooluse:{tool_name}",
            spend_on_error=True,
        ):
            pass
    except tg.BudgetExhausted as exc:
        reason = f"frozen FOIL run {binding['task_id']!r}: {exc}"
        _record(binding, {**common, "decision": "deny", "reason": reason})
        return deny(reason)
    except tg.BindingMismatch as exc:
        reason = f"frozen FOIL run binding rejected this call: {exc}"
        _record(binding, {**common, "decision": "deny", "reason": reason})
        return deny(reason)
    except tg.LockTimeout as exc:
        reason = f"frozen FOIL run ledger is locked: {exc}"
        _record(binding, {**common, "decision": "deny", "reason": reason})
        return deny(reason)
    except Exception as exc:  # noqa: BLE001 - unknown failure must fail closed
        reason = (
            f"frozen FOIL run ledger could not be charged, failing closed: "
            f"{type(exc).__name__}: {exc}"
        )
        _record(binding, {**common, "decision": "deny", "reason": reason})
        return deny(reason)

    _record(binding, {**common, "decision": "allow",
                      "reason": "budget unit charged at reservation"})
    return 0


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        raw = sys.stdin.read()
    except OSError:
        return 0
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    try:
        return handle(payload)
    except Exception as exc:  # noqa: BLE001 - a hook crash must not silently allow
        return deny(f"FOIL tool broker failed, failing closed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
