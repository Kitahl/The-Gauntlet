"""Turn-boundary Process Assurance evaluator with incident-keyed suppression.

This legacy natural-language boundary remains deliberately narrow. Deterministic
repeated-tool-loop evidence can fire without an LLM. Free-text frame/costume
candidates use an optional independent semantic precision judge; judge absence is
reported as UNAVAILABLE rather than silently interpreted as a negative judgment.
Persisted history contains lossy fingerprints only, never assistant-message text.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable

from gauntlet_config import load_config, project_root, state_dir
from openrouter_bot import OpenRouterError, ask, available
from private_io import write_private_text

MARKER = "[PROCESS ASSURANCE"
REPEAT = re.compile(r"\b(again|still|same|keeps?|kept|once more|repeated(?:ly)?|recurs?|attempt \d+|try \d+|as before|last time|every attempt|each attempt|no matter what)\b", re.I)
SURVIVOR = re.compile(r"\b(only remaining|only viable|last option|last resort|left standing|only approach|only way|remaining candidate|nothing else works)\b", re.I)
NOVELTY = re.compile(r"\b(our novel|my novel|new framework|new method|invented|devised|proprietary|bespoke|home-?grown|breakthrough|my own|our own)\b", re.I)
PRIOR_ART = re.compile(r"\b(existing|known as|prior art|already exists|similar to|standard technique|off-the-shelf|same as|equivalent to|reinvent)\b", re.I)
READONLY_TOOL = re.compile(r"^(Read|Glob|Grep|WebSearch|WebFetch|TaskGet|TaskList|.*status.*|.*get_.*)$", re.I)
FINGERPRINT = re.compile(r"^[0-9a-f]{16}$")
TOKEN = re.compile(r"[a-z0-9]+", re.I)


def message_fingerprint(message: str) -> str:
    """Return a lossy SimHash-like fingerprint without retaining recoverable text."""
    tokens = TOKEN.findall(message.lower())[:400]
    if not tokens:
        return "0000000000000000"
    features = tokens if len(tokens) == 1 else [f"{a}\x1f{b}" for a, b in zip(tokens, tokens[1:])]
    weights = [0] * 64
    for feature in set(features):
        hashed = int.from_bytes(hashlib.blake2b(feature.encode(), digest_size=8).digest(), "big")
        for bit in range(64):
            weights[bit] += 1 if hashed & (1 << bit) else -1
    value = 0
    for bit, weight in enumerate(weights):
        if weight >= 0:
            value |= 1 << bit
    return f"{value:016x}"


def _as_fingerprint(value: str) -> str:
    value = str(value)
    return value if FINGERPRINT.fullmatch(value) else message_fingerprint(value)


def fingerprint_similarity(a: str, b: str) -> float:
    left = int(_as_fingerprint(a), 16)
    right = int(_as_fingerprint(b), 16)
    return 1.0 - ((left ^ right).bit_count() / 64.0)


def near_duplicate(message: str, previous: list[str], threshold: float) -> bool:
    if not previous:
        return False
    current = message_fingerprint(message)
    return any(fingerprint_similarity(current, prior) >= threshold for prior in previous)


def stage1(message: str, previous: list[str], threshold: float) -> str | None:
    if REPEAT.search(message) or near_duplicate(message, previous, threshold):
        return "frame"
    if (SURVIVOR.search(message) or NOVELTY.search(message)) and not PRIOR_ART.search(message):
        return "costume"
    return None


def _tail_tool_calls(transcript: str, limit: int = 14) -> list[tuple[str, str, bool]]:
    """Return tool name + normalized input hash + error flag; never raw output."""
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
                input_hash = hashlib.sha256(canonical.encode()).hexdigest()[:16]
                calls.append((name, input_hash, False, str(block.get("id") or "")))
            elif block.get("type") == "tool_result":
                results[str(block.get("tool_use_id") or "")] = bool(block.get("is_error"))
    return [(name, input_hash, results.get(ident, False)) for name, input_hash, _, ident in calls[-limit:]]


def action_loop(transcript: str) -> str | None:
    calls = _tail_tool_calls(transcript)
    if len(calls) < 3:
        return None
    stats: dict[str, list] = {}
    for name, input_hash, err in calls:
        row = stats.setdefault(input_hash, [name, 0, 0, False])
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


def llm_judge(op: str, message: str, model: str | None) -> bool | None:
    if not model or not available():
        return None
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
        return None


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict) -> None:
    write_private_text(path, json.dumps(state, indent=2) + "\n")


def reset(root: Path | None = None) -> int:
    root = root or project_root()
    path = state_dir(root) / "gauntlet_boundary.json"
    save_state(path, {"turn": 0, "judge_calls": 0, "history": [], "incidents": {}, "last_unavailable": None})
    return 0


def _incident_key(op: str, message: str, action_ev: str | None) -> str:
    if action_ev:
        raw = f"{op}|tool-loop|{action_ev}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{op}:{message_fingerprint(message)}"


def _suppressed(state: dict, incident: str, turn: int, refractory_turns: int) -> bool:
    last = (state.get("incidents") or {}).get(incident)
    return isinstance(last, int) and turn - last <= refractory_turns


def evaluate(
    message: str,
    transcript: str,
    *,
    root: Path | None = None,
    judge: Callable[[str, str, str | None], bool | None] = llm_judge,
) -> tuple[str | None, str]:
    root = root or project_root()
    cfg = load_config(root)
    bc = cfg.get("boundary", {})
    if not bc.get("enabled", True):
        return None, ""
    path = state_dir(root, cfg) / "gauntlet_boundary.json"
    st = load_state(path)
    turn = int(st.get("turn", 0)) + 1
    st["turn"] = turn
    history = [_as_fingerprint(item) for item in list(st.get("history", []))[-2:]]
    threshold = float(bc.get("near_duplicate_threshold", 0.72))
    op = stage1(message, history, threshold)
    action_ev = action_loop(transcript)
    if op is None and action_ev:
        op = "frame"
    history.append(message_fingerprint(message))
    st["history"] = history[-3:]
    if not op:
        st["last_unavailable"] = None
        save_state(path, st)
        return None, ""

    incident = _incident_key(op, message, action_ev)
    refractory = max(0, int(bc.get("incident_refractory_turns", 3)))
    if _suppressed(st, incident, turn, refractory):
        save_state(path, st)
        return None, ""

    model = os.environ.get("GAUNTLET_JUDGE_MODEL") or bc.get("judge_model")
    confirmed: bool | None = True if (op == "frame" and action_ev) else judge(op, message, model)
    if confirmed is None:
        st["last_unavailable"] = {"operation": op, "incident": incident, "turn": turn}
        save_state(path, st)
        return None, (
            f"{MARKER} /{op}] Semantic precision judge UNAVAILABLE for a free-text audit candidate. "
            "No pass/fail inference was made; use typed runtime evidence or configure GAUNTLET_JUDGE_MODEL."
        )
    if not confirmed:
        st["last_unavailable"] = None
        save_state(path, st)
        return None, ""

    st.setdefault("incidents", {})[incident] = turn
    st["last_unavailable"] = None
    # Retain only a bounded incident ledger; keys are non-recoverable fingerprints.
    if len(st["incidents"]) > 64:
        oldest = sorted(st["incidents"], key=lambda key: st["incidents"][key])[:-64]
        for key in oldest:
            st["incidents"].pop(key, None)
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
    elif reason:
        print(json.dumps({"systemMessage": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
