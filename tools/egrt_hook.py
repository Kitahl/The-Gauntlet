"""Privacy-preserving Claude Code hook adapter for the typed EGR runtime."""
from __future__ import annotations

import json
import re
import sys

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import RuntimeEvent, Verdict, digest, text_digest
from gauntlet_config import load_config, project_root
from soul_runtime import release_task

ALIASES = {
    "/soul": "soul", "/gauntlet": "gauntlet", "/foil": "foil", "/council": "council",
    "/mind": "mind", "/space": "space", "/reality": "reality", "/power": "power", "/time": "time",
}


def _payload() -> dict:
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}


def _store() -> RuntimeStore:
    return RuntimeStore(project_root())


def _active_task(store: RuntimeStore) -> str | None:
    path = store.base / "active_task"
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def _event(store: RuntimeStore, event_type: str, component: str, payload_hash: str, metadata: dict | None = None, task_id: str | None = None) -> None:
    store.append_event(RuntimeEvent(
        event_id=new_id("evt"), event_type=event_type, component=component,
        task_id=task_id if task_id is not None else _active_task(store), payload_hash=payload_hash,
        timestamp=utcnow(), metadata=metadata or {},
    ))


def session() -> int:
    store = _store()
    _event(store, "session.started", "soul", digest({"schema": "egrt.runtime.v1"}), {
        "raw_prompt_persisted": False,
        "raw_tool_output_persisted": False,
    })
    return 0


def _explicit_aliases(raw: str) -> list[str]:
    low = raw.lower()
    found = []
    for token, name in ALIASES.items():
        if re.search(rf"(?<!\w){re.escape(token)}(?![\w-])", low):
            found.append(name)
    return sorted(found)


def prompt() -> int:
    data = _payload()
    raw = str(data.get("prompt") or "")
    # Persist a one-way digest plus explicit slash-command aliases only. No raw prompt.
    _event(_store(), "prompt.received", "soul", text_digest(raw), {
        "explicit_modules": _explicit_aliases(raw),
        "length_bucket": min(len(raw) // 256, 20),
    })
    return 0


def _tool_fields(data: dict) -> tuple[str, dict, str]:
    tool_name = str(data.get("tool_name") or data.get("matcher") or "unknown")
    tool_input = data.get("tool_input") or {}
    input_hash = digest(tool_input)
    return tool_name, tool_input, input_hash


def pre_tool() -> int:
    data = _payload()
    store = _store()
    tool_name, _, input_hash = _tool_fields(data)
    _event(store, "tool.pre", "soul", input_hash, {"tool_name": tool_name})
    _event(store, "action.attempted", "soul", input_hash, {
        "tool_name": tool_name,
        "action_signature": digest({"tool_name": tool_name, "input_hash": input_hash}),
        # blocker_hash/progress_hash are intentionally absent unless a component
        # explicitly supplies them; Redirect will then return UNKNOWN, not guess.
    })
    return 0


def post_tool() -> int:
    data = _payload()
    store = _store()
    tool_name, _, input_hash = _tool_fields(data)
    is_error = bool(data.get("is_error") or data.get("tool_error"))
    _event(store, "tool.post", "soul", input_hash, {"tool_name": tool_name, "is_error": is_error})
    if is_error:
        _event(store, "action.failed", "soul", input_hash, {
            "tool_name": tool_name,
            "failure_signature": digest({"tool_name": tool_name, "input_hash": input_hash}),
        })
    return 0


def pre_write() -> int:
    data = _payload()
    store = _store()
    tool_name, _, input_hash = _tool_fields(data)
    _event(store, "write.pre", "soul", input_hash, {"tool_name": tool_name})
    return 0


def stop() -> int:
    data = _payload()
    if data.get("stop_hook_active"):
        return 0
    root = project_root()
    cfg = load_config(root)
    runtime_cfg = cfg.get("runtime", {})
    if not runtime_cfg.get("enabled", True) or not runtime_cfg.get("release_gate", True):
        return 0
    store = RuntimeStore(root)
    task_id = _active_task(store)
    if not task_id:
        # Typed tasks are opt-in. Ordinary small interactions are not forced into
        # ceremony simply because hooks are installed.
        return 0
    _event(store, "release.attempted", "soul", digest({"task_id": task_id}), task_id=task_id)
    verdict, detail = release_task(root, task_id)
    if verdict == Verdict.CLEARED:
        return 0
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"EGR release gate: {verdict.value}. Load-bearing obligations remain unresolved; "
            f"inspect typed receipts before claiming completion. task={task_id}; detail_hash={digest(detail)[:16]}"
        ),
    }))
    return 0


def main(argv: list[str] | None = None) -> int:
    mode = (argv or sys.argv[1:] or [""])[0]
    if mode == "session":
        return session()
    if mode == "prompt":
        return prompt()
    if mode == "pre-tool":
        return pre_tool()
    if mode == "post-tool":
        return post_tool()
    if mode == "pre-write":
        return pre_write()
    if mode == "stop":
        return stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
