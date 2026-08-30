"""Opt-in, event-driven post-solve trigger for FOIL's shadow scanner.

The monitor is a pure routing function.  It does not poll, schedule itself,
load a profile, run a verifier, call a model/tool/network, or mutate an answer.
The host may use a ``SCAN`` decision to invoke the separately budgeted scanner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PostSolveAction(str, Enum):
    STAND_DOWN = "STAND_DOWN"
    OBSERVE = "OBSERVE"
    SCAN = "SCAN"
    UNKNOWN = "UNKNOWN"


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_count(name: str, value: object, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int")
    minimum = 1 if positive else 0
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True)
class PostSolveEvent:
    event_id: str
    event_type: str
    sequence: int
    task_digest: str
    answer_digest: str
    payload_digest: str

    def __post_init__(self) -> None:
        _require_text("event_id", self.event_id)
        _require_text("event_type", self.event_type)
        _require_count("sequence", self.sequence, positive=True)
        for name in ("task_digest", "answer_digest", "payload_digest"):
            _require_digest(name, getattr(self, name))


@dataclass(frozen=True)
class PostSolveMonitorPolicy:
    """Budget for one explicitly invoked event stream.

    ``token_budget`` is fixed at zero: this trigger has no model-facing path.
    Diagnostic work has its own sealed run ledger and is not hidden here.
    """

    enabled: bool = False
    observe_only: bool = True
    subscribed_events: tuple[str, ...] = ("answer.sealed",)
    max_scan_triggers: int = 0
    cooldown_events: int = 0
    max_seen_payloads: int = 256
    token_budget: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(self.observe_only, bool):
            raise TypeError("enabled and observe_only must be bool")
        if not isinstance(self.subscribed_events, tuple) or not self.subscribed_events:
            raise ValueError("subscribed_events must be a non-empty tuple")
        for event_type in self.subscribed_events:
            _require_text("subscribed_event", event_type)
        if len(set(self.subscribed_events)) != len(self.subscribed_events):
            raise ValueError("subscribed_events must be unique")
        _require_count("max_scan_triggers", self.max_scan_triggers)
        _require_count("cooldown_events", self.cooldown_events)
        _require_count("max_seen_payloads", self.max_seen_payloads, positive=True)
        if self.token_budget != 0:
            raise ValueError("post-solve trigger token budget is fixed at zero")


@dataclass(frozen=True)
class PostSolveCursor:
    last_sequence: int = 0
    scan_triggers: int = 0
    next_scan_sequence: int = 0
    seen_payload_digests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("last_sequence", "scan_triggers", "next_scan_sequence"):
            _require_count(name, getattr(self, name))
        if not isinstance(self.seen_payload_digests, tuple):
            raise TypeError("seen_payload_digests must be a tuple")
        for item in self.seen_payload_digests:
            _require_digest("seen_payload_digest", item)
        if len(set(self.seen_payload_digests)) != len(self.seen_payload_digests):
            raise ValueError("seen payload digests must be unique")


@dataclass(frozen=True)
class PostSolveDecision:
    action: PostSolveAction
    reason: str
    event_id: str | None
    cursor: PostSolveCursor
    model_calls: int = 0
    tool_calls: int = 0
    network_calls: int = 0
    tokens: int = 0
    answer_mutated: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.action, PostSolveAction):
            raise TypeError("action must be PostSolveAction")
        _require_text("reason", self.reason)
        if self.event_id is not None:
            _require_text("event_id", self.event_id)
        if not isinstance(self.cursor, PostSolveCursor):
            raise TypeError("cursor must be PostSolveCursor")
        if any((self.model_calls, self.tool_calls, self.network_calls, self.tokens)):
            raise ValueError("post-solve trigger cannot record hidden external work")
        if self.answer_mutated:
            raise ValueError("post-solve trigger cannot mutate the answer")


def evaluate_postsolve_event(
    event: PostSolveEvent,
    policy: PostSolveMonitorPolicy,
    cursor: PostSolveCursor = PostSolveCursor(),
) -> PostSolveDecision:
    """Evaluate one host-supplied event with bounded, deduplicated work."""

    if not isinstance(event, PostSolveEvent):
        raise TypeError("event must be PostSolveEvent")
    if not isinstance(policy, PostSolveMonitorPolicy):
        raise TypeError("policy must be PostSolveMonitorPolicy")
    if not isinstance(cursor, PostSolveCursor):
        raise TypeError("cursor must be PostSolveCursor")
    if not policy.enabled:
        return PostSolveDecision(PostSolveAction.STAND_DOWN, "monitor_disabled", None, cursor)
    if event.sequence <= cursor.last_sequence:
        return PostSolveDecision(
            PostSolveAction.UNKNOWN, "stale_or_reordered_event", event.event_id, cursor
        )

    was_seen = event.payload_digest in cursor.seen_payload_digests
    seen = tuple(dict.fromkeys((*cursor.seen_payload_digests, event.payload_digest)))
    if len(seen) > policy.max_seen_payloads:
        seen = seen[-policy.max_seen_payloads :]
    next_cursor = PostSolveCursor(
        last_sequence=event.sequence,
        scan_triggers=cursor.scan_triggers,
        next_scan_sequence=cursor.next_scan_sequence,
        seen_payload_digests=seen,
    )
    if was_seen:
        return PostSolveDecision(
            PostSolveAction.STAND_DOWN, "duplicate_payload", event.event_id, next_cursor
        )
    if event.event_type not in policy.subscribed_events:
        return PostSolveDecision(
            PostSolveAction.STAND_DOWN, "event_not_subscribed", event.event_id, next_cursor
        )
    if policy.observe_only:
        return PostSolveDecision(
            PostSolveAction.OBSERVE, "observe_only", event.event_id, next_cursor
        )
    if cursor.scan_triggers >= policy.max_scan_triggers:
        return PostSolveDecision(
            PostSolveAction.STAND_DOWN, "scan_budget_exhausted", event.event_id, next_cursor
        )
    if event.sequence < cursor.next_scan_sequence:
        return PostSolveDecision(
            PostSolveAction.STAND_DOWN, "cooldown_active", event.event_id, next_cursor
        )

    next_cursor = PostSolveCursor(
        last_sequence=event.sequence,
        scan_triggers=cursor.scan_triggers + 1,
        next_scan_sequence=event.sequence + policy.cooldown_events + 1,
        seen_payload_digests=seen,
    )
    return PostSolveDecision(
        PostSolveAction.SCAN, "eligible_sealed_answer", event.event_id, next_cursor
    )
