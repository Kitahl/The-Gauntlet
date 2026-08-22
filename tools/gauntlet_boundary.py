"""Turn-boundary Process Assurance evaluator.

A sanitized, portable descendant of the original two-stage Gauntlet evaluator.
It detects repeated/stuck work and unsupported novelty/survivor framing, then
optionally asks an independently configured OpenRouter model for a precision
judgment. Strong deterministic tool-loop evidence can fire without an API key.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Callable

try:
    from rapidfuzz import fuzz
except Exception:
    fuzz = None

from gauntlet_config import load_config, project_root, state_dir
from openrouter_bot import OpenRouterError, ask, available

MARKER = "[PROCESS ASSURANCE"
REPEAT = re.compile(r"\b(again|still|same|keeps?|kept|once more|repeated(?:ly)?|recurs?|attempt \d+|try \d+|as before|last time|every attempt|each attempt|no matter what)\b", re.I)
SURVIVOR = re.compile(r"\b(only remaining|only viable|last option|last resort|left standing|only approach|only way|remaining candidate|nothing else works)\b", re.I)
NOVELTY = re.compile(r"\b(our novel|my novel|new framework|new method|invented|devised|proprietary|bespoke|home-?grown|breakthrough|my own|our own)\b", re.I)
PRIOR_ART = re.compile(r"\b(existing|known as|prior art|already exists|similar to|standard technique|off-the-shelf|same as|equivalent to|reinvent)\b", re.I)
READONLY_TOOL = re.compile(r"^(Read|Glob|Grep|WebSearch|WebFetch|TaskGet|TaskList|.*status.*|.*get_.*)$", re.I)


def near_duplicate(message: str, previous: list[str], threshold: float) -> bool:
    if fuzz is None or not previous:
        return False
    text = message[:1000]
    return any(fuzz.token_set_ratio(text, p[:1000]) / 100.0 >= threshold for p in previous)


def stage1(message: str, previous: list[str], threshold: float) -> str | None:
    if REPEAT.search(message) or near_duplicate(message, previous, threshold):
        return "frame"
    if (SURVIVOR.search(message) or NOVELTY.search(message)) and not PRIOR_ART.search(message):
        return "costume"
    return None


def _tail_tool_calls(transcript: str, limit: int = 14) -> list[tuple[str, str, bool]]:
    """Return only tool name + normalized input hash + error flag; never raw output."""
    import hashlib

    calls: list[tuple[str, str, bool, str]] = []
    results: dict[str, bool] = {}
    try:
        lines = Path(transcript).read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
    except OSError:
        return []
    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = obj.get("message", obj)
        content = msg.get("content", []) if isinstance(msg, dict) else []
        if isinstance(content, dict):
            content = [content]
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                name = str(block.get("name") or "unknown")
                canonical = json.dumps(block.get("input", {}), sort_keys=True, separators=(",", ":"))
                digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
                calls.append((name, digest, False, block.get("id", "")))
            elif block.get("type") == "tool_result":
                results[str(block.get("tool_use_id") or "")] = bool(block.get("is_error"))
    out: list[tuple[str, str, bool]] = []
    for name, digest, _, ident in calls[-limit:]:
        out.append((name, digest, results.get(ident, False)))
    return out


def action_loop(transcript: str) -> str | None:
    calls = _tail_tool_calls(transcript)
    if len(calls) < 3:
        return None
    stats: dict[str, list] = {}
    for name, digest, err in calls:
        row = stats.setdefault(digest, [name, 0, 0, False])
        row[1] += 1
        row[2] += int(err)
        row[3] = bool(err)
    for name, count, errors, last_error in stats.values():
        if count >= 3 and errors >= 2 and last_error:
            return f"tool {name!r} repeated {count}x and is still erroring"
    if len(calls) >= 6 and len(stats) == 2:
        rows = list(stats.values())
        if all(row[1] >= 3 for row in rows) and any(not READONLY_TOOL.match(str(row[0])) for row in rows):
            return f"alternating tool loop: {rows[0][0]} x{rows[0][1]} / {rows[1][0]} x{rows[1][1]}"
    for name, count, errors, _ in stats.values():
        if count >= 4 and (errors or not READONLY_TOOL.match(str(name))):
            return f"tool {name!r} repeated with identical input {count}x"
    return None


def llm_judge(op: str, message: str, model: str | None) -> bool:
    if not model or not available():
        return False
    system = (
        "You are a precision filter for a research-process audit. Return JSON only: "
        '{"fires":true|false,"reason":"..."}. For frame: fire only when the work is '
        "recurring without meaningful progress, not when repeated wording describes genuine progress. "
        "For costume: fire only when a last-survivor or novelty framing needs prior-art classification."
    )
    try:
        text = ask(system, f"operation={op}\nturn:\n{message}", model=model, json_mode=True, max_tokens=220)["text"]
        data = json.loads(text)
        return bool(data.get("fires"))
    except (OpenRouterError, json.JSONDecodeError, TypeError, KeyError):
        return False


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def reset(root: Path | None = None) -> int:
    root = root or project_root()
    path = state_dir(root) / "gauntlet_boundary.json"
    save_state(path, {"turn": 0, "judge_calls": 0, "fired": {}, "history": []})
    return 0


def evaluate(message: str, transcript: str, *, root: Path | None = None, judge: Callable[[str, str, str | None], bool] = llm_judge) -> tuple[str | None, str]:
    root = root or project_root()
    cfg = load_config(root)
    bc = cfg.get("boundary", {})
    if not bc.get("enabled", True):
        return None, ""
    path = state_dir(root, cfg) / "gauntlet_boundary.json"
    st = load_state(path)
    st["turn"] = int(st.get("turn", 0)) + 1
    history = list(st.get("history", []))[-2:]
    threshold = float(bc.get("near_duplicate_threshold", 0.72))
    op = stage1(message, history, threshold)
    action_ev = action_loop(transcript)
    if op is None and action_ev:
        op = "frame"
    history.append(message)
    st["history"] = history[-3:]
    if not op:
        save_state(path, st)
        return None, ""

    budgets = {"frame": int(bc.get("frame_budget", 3)), "costume": int(bc.get("costume_budget", 2))}
    fired = st.setdefault("fired", {})
    count = int(fired.get(op, 0))
    if count >= budgets[op]:
        save_state(path, st)
        return None, ""

    model = os.environ.get("GAUNTLET_JUDGE_MODEL") or bc.get("judge_model")
    confirmed = bool(action_ev) if op == "frame" else False
    if not confirmed:
        confirmed = judge(op, message, model)
    if not confirmed:
        save_state(path, st)
        return None, ""

    fired[op] = count + 1
    save_state(path, st)
    if op == "frame":
        detail = f" Tool evidence: {action_ev}." if action_ev else ""
        reason = (
            f"{MARKER} /frame] Repeated work appears stuck.{detail} Name the shared assumption or representation, "
            "then switch to a structurally different method, drop an assumption, search prior art, or surface the blocker."
        )
    else:
        reason = (
            f"{MARKER} /costume] A surviving/novelty-framed approach needs prior-art classification before adoption. "
            "Name the nearest established technique and the actual delta."
        )
    return op, reason


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "reset":
        return reset()
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("stop_hook_active"):
        return 0
    message = str(payload.get("last_assistant_message") or "")
    if not message or message.lstrip().startswith(MARKER):
        return 0
    op, reason = evaluate(message, str(payload.get("transcript_path") or ""))
    if op:
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
