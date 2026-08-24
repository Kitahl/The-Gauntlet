"""Pure, host-owned final selection over an immutable FOIL base answer.

This boundary performs no candidate generation, verification, tool execution,
I/O, or persistence.  It accepts only the non-executable request emitted by
``egrt_host_bridge`` and an explicit approval bound to that request.  Every
missing or mismatched prerequisite returns the original A0 object unchanged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from egrt_host_bridge import HostActionRequest
from egrt_types import digest

AnswerPayload = str | bytes


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _require_digest(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _timestamp(name: str, value: object) -> str:
    text = _require_text(name, value)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be ISO-8601 text") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    parsed.astimezone(timezone.utc)
    return text


def answer_digest(answer: AnswerPayload) -> str:
    """Hash exact UTF-8 text or exact bytes without JSON re-encoding."""

    if isinstance(answer, str):
        raw = answer.encode("utf-8")
    elif isinstance(answer, bytes):
        raw = answer
    else:
        raise TypeError("answer must be str or bytes")
    return hashlib.sha256(raw).hexdigest()


def host_request_digest(request: HostActionRequest) -> str:
    if not isinstance(request, HostActionRequest):
        raise TypeError("request must be HostActionRequest")
    return digest(request)


@dataclass(frozen=True)
class HostCommitApproval:
    """Explicit host decision bound to exactly one request and candidate."""

    request_digest: str
    candidate_digest: str
    approver_id: str
    approved_at: str
    reason: str
    approved: bool = True

    def __post_init__(self) -> None:
        _require_digest("request_digest", self.request_digest)
        _require_digest("candidate_digest", self.candidate_digest)
        _require_text("approver_id", self.approver_id)
        _timestamp("approved_at", self.approved_at)
        _require_text("reason", self.reason)
        if self.approved is not True:
            raise ValueError("HostCommitApproval represents an explicit approval only")

    @property
    def approval_digest(self) -> str:
        return digest(self)


class FinalizationState(str, Enum):
    BASE_PRESERVED = "BASE_PRESERVED"
    CANDIDATE_SELECTED = "CANDIDATE_SELECTED"


@dataclass(frozen=True)
class HostFinalizationResult:
    """Transient selected answer plus a raw-answer-free audit trace."""

    state: FinalizationState
    reason: str
    answer: AnswerPayload = field(repr=False)
    base_digest: str
    candidate_digest: str
    selected_digest: str
    request_digest: str
    approval_digest: str | None = None
    base_answer_preserved: bool = True
    host_action_applied: bool = False
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.state, FinalizationState):
            raise TypeError("state must be FinalizationState")
        _require_text("reason", self.reason)
        for name in ("base_digest", "candidate_digest", "selected_digest", "request_digest"):
            _require_digest(name, getattr(self, name))
        if self.approval_digest is not None:
            _require_digest("approval_digest", self.approval_digest)
        if answer_digest(self.answer) != self.selected_digest:
            raise ValueError("selected answer must match selected_digest")
        if self.state is FinalizationState.BASE_PRESERVED:
            if self.selected_digest != self.base_digest:
                raise ValueError("BASE_PRESERVED must select A0")
            if self.base_answer_preserved is not True or self.host_action_applied is not False:
                raise ValueError("preserved finalization invariants are fixed")
        else:
            if self.selected_digest != self.candidate_digest:
                raise ValueError("CANDIDATE_SELECTED must select the candidate")
            if self.base_answer_preserved is not False or self.host_action_applied is not True:
                raise ValueError("candidate finalization invariants are fixed")

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "state": self.state.value,
            "reason": self.reason,
            "base_digest": self.base_digest,
            "candidate_digest": self.candidate_digest,
            "selected_digest": self.selected_digest,
            "request_digest": self.request_digest,
            "approval_digest": self.approval_digest,
            "base_answer_preserved": self.base_answer_preserved,
            "host_action_applied": self.host_action_applied,
            "execution_authorized": self.execution_authorized,
            "raw_answer_stored": False,
        }
        body["finalization_digest"] = digest(body)
        return body


def _preserve(
    request: HostActionRequest,
    base_answer: AnswerPayload,
    reason: str,
    approval: HostCommitApproval | None,
) -> HostFinalizationResult:
    return HostFinalizationResult(
        state=FinalizationState.BASE_PRESERVED,
        reason=reason,
        answer=base_answer,
        base_digest=answer_digest(base_answer),
        candidate_digest=request.candidate_digest,
        selected_digest=answer_digest(base_answer),
        request_digest=host_request_digest(request),
        approval_digest=approval.approval_digest if approval is not None else None,
    )


def finalize_host_answer(
    request: HostActionRequest,
    *,
    base_answer: AnswerPayload,
    candidate_answer: AnswerPayload,
    approval: HostCommitApproval | None = None,
) -> HostFinalizationResult:
    """Select A1 only after exact content binding and explicit host approval.

    All ordinary denial or mismatch cases are fail-closed results, not partial
    mutations. Invalid Python types remain programming errors.
    """

    if not isinstance(request, HostActionRequest):
        raise TypeError("request must be HostActionRequest")
    base = answer_digest(base_answer)
    candidate = answer_digest(candidate_answer)
    if type(base_answer) is not type(candidate_answer):
        return _preserve(request, base_answer, "answer_type_mismatch", approval)
    if base != request.base_digest:
        return _preserve(request, base_answer, "base_digest_mismatch", approval)
    if request.artifact_sha256 != request.candidate_digest:
        return _preserve(request, base_answer, "artifact_binding_mismatch", approval)
    if candidate != request.candidate_digest:
        return _preserve(request, base_answer, "candidate_digest_mismatch", approval)
    if approval is None:
        return _preserve(request, base_answer, "host_approval_missing", None)
    if approval.request_digest != host_request_digest(request):
        return _preserve(request, base_answer, "approval_request_mismatch", approval)
    if approval.candidate_digest != request.candidate_digest:
        return _preserve(request, base_answer, "approval_candidate_mismatch", approval)
    return HostFinalizationResult(
        state=FinalizationState.CANDIDATE_SELECTED,
        reason="explicit_host_approval_and_content_bindings_matched",
        answer=candidate_answer,
        base_digest=base,
        candidate_digest=candidate,
        selected_digest=candidate,
        request_digest=host_request_digest(request),
        approval_digest=approval.approval_digest,
        base_answer_preserved=False,
        host_action_applied=True,
    )
