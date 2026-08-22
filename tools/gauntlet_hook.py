"""Claude Code hook adapter for deterministic Process Assurance gates."""
from __future__ import annotations

import json
import re
import subprocess
import sys

from gauntlet_config import project_root
from gauntlet_monitor import check, snapshot

GIT_SYNC = re.compile(r"(?:^|[;&|]\s*)git\s+(pull|fetch|merge|rebase|push)\b", re.I)
GIT_COMMIT = re.compile(r"(?:^|[;&|]\s*)git\s+commit\b", re.I)


def payload() -> dict:
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}


def command(data: dict) -> str:
    return str((data.get("tool_input") or {}).get("command") or "")


def ledger_gate() -> tuple[bool, str]:
    try:
        root = project_root()
        p = subprocess.run([sys.executable, str(root / "tools" / "verify_ledger.py")], cwd=root, text=True, capture_output=True, timeout=15)
    except Exception as exc:
        return False, f"evidence-ledger gate could not run: {exc}"
    return p.returncode == 0, (p.stderr or p.stdout).strip()


def main(argv: list[str] | None = None) -> int:
    mode = (argv or sys.argv[1:] or [""])[0]
    data = payload()
    cmd = command(data)
    if mode == "pre-write":
        code, drift = check()
        if code:
            print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Governing research state changed: " + "; ".join(drift) + ". Re-read before editing."}}))
        return 0
    if mode == "pre-tool":
        if GIT_SYNC.search(cmd):
            code, drift = check()
            if code:
                print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Governing research state changed: " + "; ".join(drift)}}))
        if GIT_COMMIT.search(cmd):
            ok, detail = ledger_gate()
            if not ok:
                print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Evidence ledger gate failed: " + detail[:1500]}}))
        return 0
    if mode == "post-tool" and GIT_COMMIT.search(cmd):
        snapshot()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
