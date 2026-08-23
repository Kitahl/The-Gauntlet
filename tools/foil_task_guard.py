"""Fail-closed task identity and tool-budget ledger for frozen FOIL evaluations.

Scope claim, stated honestly
----------------------------
This module is a **tamper-evident accounting ledger**, not a security boundary.
It cannot stop a caller that never invokes it.  The v1 documentation described
it as "mechanically enforced", which was false: it counted `authorize()` calls,
not tool calls.  Real enforcement requires mediating the operation itself - an
egress proxy, a sandbox syscall filter, or a tool wrapper the model cannot
reach around.  `guarded_operation()` below is the wrapper form and is the only
supported way to spend budget, because it makes the accounting inseparable from
the call.  `attest()` makes after-the-fact edits detectable.

Fixes over v1
-------------
* `fcntl.flock` on a held descriptor replaces the `O_EXCL` lockfile, so a
  crashed process releases its lock automatically.  v1 left a permanent lock
  behind: a dead PID bricked every later authorize for that item.
* The descriptor is closed exactly once.  v1 closed it inside the `try` and
  again in `finally`; under threads the number can be recycled between the two
  closes, so the second close can close an unrelated open file.
* Where `fcntl` is unavailable (Windows) the lock is a real kernel byte-range
  lock via `msvcrt.locking` on a persistent lock file, not an `O_EXCL` sentinel.
  The `O_EXCL` fallback was not a lock at all: it serialised nothing once the
  sentinel existed, and its PID/TTL liveness heuristic refused live contenders
  outright, so 12 concurrent workers against a budget of 5 produced 2 grants and
  10 `LockTimeout`s instead of 5 grants and 7 refusals. Byte-range locks are
  released by the kernel when the handle closes, including on a crash, so no
  liveness heuristic is needed and the lock file is never unlinked.
* Events form a SHA-256 hash chain, so a deleted or edited event is detectable
  by `attest()`.  The chain alone only covers *interior* edits: removing events
  from the end leaves a self-consistent chain, so the state also records
  `event_count` and `head`, and `attest()` re-derives `used` from the events.
  A tail truncation, or an edit to `used` that the events do not support, is a
  failed attestation rather than a valid receipt that under-reports the spend.
* Budget is spent only on success by default, so a transport failure does not
  silently consume a query; pass `spend_on_error=True` to charge attempts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:  # POSIX
    import fcntl

    _HAVE_FLOCK = True
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]
    _HAVE_FLOCK = False

try:  # Windows
    import msvcrt

    _HAVE_MSVCRT = True
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None  # type: ignore[assignment]
    _HAVE_MSVCRT = False

SCHEMA = "egrt.foil-task-run.v2"
GENESIS = "0" * 64
LOCK_TIMEOUT_SECONDS = 30.0


class BudgetExhausted(RuntimeError):
    """Raised instead of allowing a governed operation to exceed its budget."""


class LockTimeout(RuntimeError):
    """Raised when the evaluation state lock could not be acquired in time."""


class BindingMismatch(RuntimeError):
    """Raised when task id, condition, or prompt hash does not match the frozen run."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# hash-chained events                                                          #
# --------------------------------------------------------------------------- #

def _event_digest(previous: str, event: dict[str, Any]) -> str:
    payload = {k: v for k, v in event.items() if k != "digest"}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{previous}|{blob}".encode("utf-8")).hexdigest()


def _append_event(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Append to the chain and re-anchor the state-level tip.

    `event_count` and `head` are written here, on every append, because a chain
    that only knows its own links cannot detect that links were removed from its
    *end*: truncating the tail leaves a perfectly self-consistent chain. The tip
    has to be recorded outside the list it summarises for that to be checkable.
    """
    events = state.setdefault("events", [])
    previous = events[-1]["digest"] if events else GENESIS
    event["previous"] = previous
    event["digest"] = _event_digest(previous, event)
    events.append(event)
    state["event_count"] = len(events)
    state["head"] = event["digest"]
    return event


#: Event kinds that move the reservation counter, and by how much. `SPENT`
#: (and the `COMMITTED` spelling a closed run uses for its result) keep the hold
#: placed at reservation time, so they move nothing - see `_commit`.
_USED_DELTAS: dict[str, int] = {"RESERVED": 1, "RELEASED": -1, "SPENT": 0, "COMMITTED": 0}


def replay_used(events: list[dict[str, Any]]) -> dict[str, int]:
    """Recompute `used` per operation from the event chain alone.

    Mirrors `authorize`/`_commit` exactly, including the `max(0, ...)` floor a
    release applies, so a healthy run replays to the recorded counters. Any
    event kind that is not a reservation movement - `OPEN`, `CLOSE`,
    `BLOCKED_BUDGET`, and the broker's `BROKER` journal rows - is ignored even
    though several of them carry an `operation` field.
    """
    used: dict[str, int] = {}
    for event in events:
        delta = _USED_DELTAS.get(str(event.get("kind") or ""))
        operation = event.get("operation")
        if not delta or operation is None:
            continue
        used[str(operation)] = max(0, int(used.get(str(operation), 0)) + delta)
    return used


def attest(state: dict[str, Any]) -> dict[str, Any]:
    """Verify the event chain and return a signable summary.

    Three independent checks, because the chain alone is not enough:

    1. **Link integrity** - an edited or removed *interior* event breaks a digest.
    2. **Tip integrity** - `event_count` and `head` are compared against the
       events actually present. Deleting the last N events leaves an intact
       chain, so without this a tail truncation attested as valid while `used`
       still reported the spend.
    3. **Accounting integrity** - `used` is recomputed from the events and must
       match what the state records. This is what catches the two halves being
       edited apart: trimming events without touching `used`, or editing `used`
       without touching events.
    """
    events = list(state.get("events", []))
    previous = GENESIS
    for index, event in enumerate(events):
        if event.get("previous") != previous:
            return {"valid": False, "broken_at": index, "reason": "previous digest mismatch"}
        expected = _event_digest(previous, event)
        if event.get("digest") != expected:
            return {"valid": False, "broken_at": index, "reason": "event digest mismatch"}
        previous = expected

    recorded_count = state.get("event_count")
    if recorded_count is None:
        return {
            "valid": False,
            "reason": "state records no event_count, so a tail truncation would be undetectable",
        }
    if int(recorded_count) != len(events):
        return {
            "valid": False,
            "broken_at": len(events),
            "reason": (
                f"event count mismatch (truncation): state records {int(recorded_count)} "
                f"events, {len(events)} are present"
            ),
        }
    recorded_head = state.get("head")
    if recorded_head is None:
        return {
            "valid": False,
            "reason": "state records no head digest, so a tail truncation would be undetectable",
        }
    if str(recorded_head) != previous:
        return {
            "valid": False,
            "broken_at": len(events),
            "reason": (
                "head digest mismatch (truncation or replacement): the recomputed chain head "
                "is not the head the state records"
            ),
        }

    replayed = replay_used(events)
    recorded_used = {str(k): int(v) for k, v in dict(state.get("used", {})).items()}
    for key in set(replayed) | set(recorded_used):
        if recorded_used.get(key, 0) != replayed.get(key, 0):
            return {
                "valid": False,
                "reason": "used does not match replay",
                "recorded_used": recorded_used,
                "replayed_used": replayed,
            }

    return {
        "valid": True,
        "events": len(events),
        "event_count": len(events),
        "head": previous,
        "task_id": state.get("task_id"),
        "condition": state.get("condition"),
        "used": dict(state.get("used", {})),
        "budgets": dict(state.get("budgets", {})),
        "status": state.get("status"),
    }


# --------------------------------------------------------------------------- #
# state                                                                        #
# --------------------------------------------------------------------------- #

SESSION_INDEX_SUFFIX = ".sessions.json"


def session_index_path(state: Path) -> Path:
    """Sidecar index that records which isolation sessions a state file claimed."""
    return state.with_name(state.name + SESSION_INDEX_SUFFIX)


def claimed_isolation_sessions(state_dir: Path) -> dict[str, str]:
    """Every isolation session id already claimed anywhere in `state_dir`.

    The index is written per state file (`<state>.sessions.json`) but read across
    the whole directory. A run directory is the unit an evaluation actually shares,
    so two different state files reusing one isolation session id is exactly the
    collision worth catching - and a per-file-only check would miss it.
    """
    claimed: dict[str, str] = {}
    if not state_dir.is_dir():
        return claimed
    for sidecar in sorted(state_dir.glob("*" + SESSION_INDEX_SUFFIX)):
        try:
            rows = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A damaged sidecar must not hand out a session id as if it were
            # free. Fail closed by naming it, so the caller sees a mismatch
            # rather than a silent reuse.
            claimed.setdefault("<unreadable:" + sidecar.name + ">", sidecar.name)
            continue
        if not isinstance(rows, dict):
            continue
        for session_id, owner in rows.items():
            claimed.setdefault(str(session_id), str(owner))
    return claimed


def _claim_isolation_session(state: Path, isolation_session_id: str, task_id: str) -> None:
    """Record the claim, or refuse it. Fails closed on a duplicate."""
    state_dir = state.parent
    claimed = claimed_isolation_sessions(state_dir)
    if isolation_session_id in claimed:
        raise BindingMismatch(
            f"isolation_session_id {isolation_session_id!r} was already claimed by "
            f"{claimed[isolation_session_id]!r} in {state_dir}; a reused session is not "
            "an isolated run"
        )
    sidecar = session_index_path(state)
    try:
        rows = json.loads(sidecar.read_text(encoding="utf-8"))
        if not isinstance(rows, dict):
            rows = {}
    except (OSError, json.JSONDecodeError):
        rows = {}
    rows[isolation_session_id] = f"{state.name}:{task_id}"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    temp = sidecar.with_suffix(sidecar.suffix + ".tmp")
    temp.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(sidecar)


def start_state(
    *,
    task_id: str,
    prompt: str,
    condition: str,
    budgets: dict[str, int],
    profile_freeze: str | None = None,
    profile_payload_sha256: str | None = None,
    dataset_revision: str | None = None,
    as_of: str | None = None,
    decoding: dict[str, Any] | None = None,
    model: str | None = None,
    effort: str | None = None,
    allowed_tools: list[str] | None = None,
    isolation_session_id: str | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """Open a frozen run.

    `model`, `effort`, `allowed_tools` and `isolation_session_id` are part of the
    binding, not decoration: a result is only attributable to a configuration if
    the configuration is recorded with it, and an "isolated" run that silently
    shared a session with another run is not isolated. Pass `state_path` (the
    file the state will be saved to) together with `isolation_session_id` and the
    claim is registered in a sidecar index; a second run claiming the same id
    anywhere in that directory raises `BindingMismatch`.
    """
    clean_budgets = {str(k): int(v) for k, v in budgets.items()}
    if any(value < 0 for value in clean_budgets.values()):
        raise ValueError("budgets must be non-negative")
    tools = [str(item) for item in (allowed_tools or [])]
    if isolation_session_id is not None and state_path is not None:
        _claim_isolation_session(Path(state_path), str(isolation_session_id), task_id)
    state = {
        "schema": SCHEMA,
        "task_id": task_id,
        "prompt_sha256": prompt_hash(prompt),
        "condition": condition,
        "profile_freeze": profile_freeze,
        "profile_payload_sha256": profile_payload_sha256,
        "dataset_revision": dataset_revision,
        "as_of": as_of,
        "decoding": dict(decoding or {}),
        "model": model,
        "effort": effort,
        "allowed_tools": tools,
        "isolation_session_id": isolation_session_id,
        "budgets": clean_budgets,
        "used": {key: 0 for key in clean_budgets},
        "events": [],
        "status": "OPEN",
        "created_at": now(),
        "updated_at": now(),
    }
    _append_event(state, {"time": now(), "kind": "OPEN", "task_id": task_id, "condition": condition})
    return state


def _atomic_save(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now()
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# locking                                                                      #
# --------------------------------------------------------------------------- #

@contextmanager
def _exclusive_lockfile(lock: Path, timeout: float = LOCK_TIMEOUT_SECONDS) -> Iterator[None]:
    """Windows byte-range lock on a persistent lock file.

    `msvcrt.locking(fd, LK_NBLCK, 1)` takes a kernel lock on byte 0. The lock is
    held by the *handle*, so distinct `os.open` calls in the same process are
    mutually exclusive, and the kernel drops the lock if the process dies. The
    file itself is never unlinked: its content carries no meaning, so a leftover
    or garbage-filled lock file cannot brick a later run.

    The acquire loop mirrors the POSIX branch exactly: a *non-blocking* attempt
    retried every 10 ms until `timeout`. `LK_LOCK` would also work, but it
    retries internally on a one-second granularity, which turns ordinary
    contention into second-scale waits - measured at ~9-10 s for twelve threads
    contending over a budget of five, against well under a second here.
    """
    if not _HAVE_MSVCRT:  # pragma: no cover - no locking primitive available
        raise LockTimeout(f"no file-locking primitive is available on this platform: {lock}")
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not acquire evaluation state lock within {timeout}s: {lock}"
                    ) from exc
                time.sleep(0.01)
        try:
            yield
        finally:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)  # exactly one close, on every path


@contextmanager
def exclusive_state_lock(path: Path, *, timeout: float = LOCK_TIMEOUT_SECONDS) -> Iterator[None]:
    """Hold an exclusive lock for the duration of a state mutation.

    On POSIX this is `flock`; on Windows it is an `msvcrt` byte-range lock.
    Both are released by the kernel if the process dies, so a crash cannot leave
    the run permanently unusable.  Acquisition *waits* up to `timeout`:
    contending workers must queue, not fail.  A non-blocking lock would turn
    ordinary concurrency into spurious budget-refusal errors.
    """
    lock = path.with_suffix(path.suffix + ".lock")
    if not _HAVE_FLOCK:
        # `timeout` must be forwarded. Dropping it made the Windows branch
        # silently ignore the caller's deadline and always wait the module
        # default, so `timeout=0.0` blocked for 30 s.
        with _exclusive_lockfile(lock, timeout):
            yield
        return
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not acquire evaluation state lock within {timeout}s: {lock}"
                    ) from exc
                time.sleep(0.01)
        os.write(fd, f"pid={os.getpid()} time={time.time()}\n".encode("utf-8"))
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)  # exactly one close, on every path


# --------------------------------------------------------------------------- #
# authorization                                                                #
# --------------------------------------------------------------------------- #

def verify_binding(
    state: dict[str, Any],
    *,
    task_id: str,
    condition: str,
    prompt: str | None = None,
    prompt_sha256: str | None = None,
) -> None:
    """Check that the caller is bound to this frozen run.

    Either the prompt text or its SHA-256 must be supplied. A hook process that
    mediates tool calls never sees the prompt text, only the digest the run was
    opened with, so accepting the digest is what lets enforcement live outside
    the process that holds the prompt. Supplying neither is a binding failure,
    not a pass.
    """
    if state.get("status") != "OPEN":
        raise BindingMismatch(f"run is not open: {state.get('status')}")
    if task_id != state.get("task_id"):
        raise BindingMismatch("task_id mismatch")
    if condition != state.get("condition"):
        raise BindingMismatch("condition mismatch")
    if prompt is None and prompt_sha256 is None:
        raise BindingMismatch("either prompt or prompt_sha256 is required")
    digest = prompt_hash(prompt) if prompt is not None else str(prompt_sha256).strip().lower()
    if digest != state.get("prompt_sha256"):
        raise BindingMismatch("prompt hash mismatch")


def authorize(
    state: dict[str, Any],
    *,
    task_id: str,
    condition: str,
    operation: str,
    prompt: str | None = None,
    prompt_sha256: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    verify_binding(state, task_id=task_id, prompt=prompt, condition=condition,
                   prompt_sha256=prompt_sha256)
    budgets = state.get("budgets", {})
    if operation not in budgets:
        raise BindingMismatch(f"operation is not budgeted/allowed: {operation}")
    used = int(state.setdefault("used", {}).get(operation, 0))
    limit = int(budgets[operation])
    if used >= limit:
        _append_event(state, {"time": now(), "kind": "BLOCKED_BUDGET", "operation": operation,
                              "used": used, "limit": limit, "note": note})
        raise BudgetExhausted(f"budget exhausted for {operation}: {used}/{limit}")
    # A reservation *holds* the budget immediately. Deferring the increment to
    # commit time would let N concurrent workers all reserve the last slot.
    state["used"][operation] = used + 1
    return _append_event(state, {"time": now(), "kind": "RESERVED", "operation": operation,
                                 "ordinal": used + 1, "limit": limit, "note": note})


def _commit(state: dict[str, Any], operation: str, reservation: dict[str, Any], outcome: str) -> None:
    """SPENT keeps the hold placed at reservation time; RELEASED refunds it."""
    if outcome == "RELEASED":
        state["used"][operation] = max(0, int(state["used"].get(operation, 0)) - 1)
    _append_event(state, {"time": now(), "kind": outcome, "operation": operation,
                          "reservation": reservation["digest"]})


@contextmanager
def guarded_operation(
    path: Path,
    *,
    task_id: str,
    condition: str,
    operation: str,
    prompt: str | None = None,
    prompt_sha256: str | None = None,
    note: str | None = None,
    spend_on_error: bool = False,
) -> Iterator[dict[str, Any]]:
    """The only supported way to spend budget.

    Reserve, run the caller's block, then commit or release.  Because the
    reservation and the commit bracket the call, an operation cannot execute
    inside this context without being accounted for, and an operation that
    raises does not silently consume a query unless `spend_on_error` is set.
    """
    with exclusive_state_lock(path):
        state = load(path)
        reservation = authorize(state, task_id=task_id, prompt=prompt,
                                prompt_sha256=prompt_sha256, condition=condition,
                                operation=operation, note=note)
        _atomic_save(path, state)
    try:
        yield reservation
    except BaseException:
        with exclusive_state_lock(path):
            state = load(path)
            _commit(state, operation, reservation, "SPENT" if spend_on_error else "RELEASED")
            _atomic_save(path, state)
        raise
    with exclusive_state_lock(path):
        state = load(path)
        _commit(state, operation, reservation, "SPENT")
        _atomic_save(path, state)


def close(state: dict[str, Any], *, result: str = "COMMITTED") -> None:
    if state.get("status") != "OPEN":
        raise BindingMismatch("run already closed")
    state["status"] = result
    _append_event(state, {"time": now(), "kind": "CLOSE", "result": result})


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def _read_prompt(args: argparse.Namespace) -> str:
    if getattr(args, "prompt_file", None):
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if getattr(args, "prompt", None) is None:
        raise ValueError("provide --prompt or --prompt-file")
    return str(args.prompt)


def _parse_budget(values: list[str]) -> dict[str, int]:
    budgets: dict[str, int] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("budget must be operation=count")
        key, raw = value.split("=", 1)
        budgets[key.strip()] = int(raw)
    return budgets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOIL frozen-evaluation task/budget ledger")
    sub = parser.add_subparsers(dest="cmd", required=True)

    start = sub.add_parser("start")
    start.add_argument("state", type=Path)
    start.add_argument("--task-id", required=True)
    start.add_argument("--condition", required=True)
    start.add_argument("--prompt")
    start.add_argument("--prompt-file")
    start.add_argument("--budget", action="append", default=[], required=True)
    start.add_argument("--profile-freeze")
    start.add_argument("--profile-payload-sha256")
    start.add_argument("--dataset-revision")
    start.add_argument("--as-of")
    start.add_argument("--model")
    start.add_argument("--effort")
    start.add_argument("--allowed-tool", action="append", default=[],
                       help="repeatable; the tools this run is permitted to use")
    start.add_argument("--isolation-session-id",
                       help="claimed in a sidecar index; reuse in the same state directory fails closed")

    spend = sub.add_parser("spend", help="reserve and immediately commit one operation")
    spend.add_argument("state", type=Path)
    spend.add_argument("--task-id", required=True)
    spend.add_argument("--condition", required=True)
    spend.add_argument("--prompt")
    spend.add_argument("--prompt-file")
    spend.add_argument("--operation", required=True)
    spend.add_argument("--note")

    for name in ("status", "attest"):
        cmd = sub.add_parser(name)
        cmd.add_argument("state", type=Path)

    finish = sub.add_parser("close")
    finish.add_argument("state", type=Path)
    finish.add_argument("--result", default="COMMITTED")

    args = parser.parse_args(argv)
    if args.cmd == "start":
        state = start_state(task_id=args.task_id, prompt=_read_prompt(args),
                            condition=args.condition, budgets=_parse_budget(args.budget),
                            profile_freeze=args.profile_freeze,
                            profile_payload_sha256=args.profile_payload_sha256,
                            dataset_revision=args.dataset_revision, as_of=args.as_of,
                            model=args.model, effort=args.effort,
                            allowed_tools=args.allowed_tool,
                            isolation_session_id=args.isolation_session_id,
                            state_path=args.state)
        _atomic_save(args.state, state)
        print(args.state)
        return 0
    if args.cmd == "spend":
        with guarded_operation(args.state, task_id=args.task_id, prompt=_read_prompt(args),
                               condition=args.condition, operation=args.operation,
                               note=args.note) as reservation:
            pass
        print(json.dumps(reservation, ensure_ascii=False))
        return 0
    if args.cmd == "close":
        with exclusive_state_lock(args.state):
            state = load(args.state)
            close(state, result=args.result)
            _atomic_save(args.state, state)
        return 0
    state = load(args.state)
    print(json.dumps(attest(state) if args.cmd == "attest" else state, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
