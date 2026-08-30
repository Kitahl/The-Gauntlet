"""Event-driven, fail-closed activation policy for the dormant FOIL hook.

This module is deliberately independent of Gauntlet and Mastermind runtime
code.  It performs no polling and has no model, tool, filesystem, or network
dependencies.  Call :meth:`FoilActivationMonitor.evaluate` once for an event.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from time import monotonic, perf_counter
from typing import Callable, Optional, Sequence, Tuple, Union

from foil_signal_boundary import SignalAuthority

MAX_ACTIVE_CONTEXT_CHARS = 1200
MAX_CONTINUATION_LEASE_SECONDS = 300.0


class FeatureMode(str, Enum):
    """Supported rollout modes.  ``legacy`` is intentionally caller-selected."""

    LEGACY = "legacy"
    OFF = "off"
    OBSERVE = "observe"
    SMART = "smart"


class ActivationOutcome(str, Enum):
    INACTIVE_NO_TRIGGER = "INACTIVE_NO_TRIGGER"
    ACTIVE_EXPLICIT = "ACTIVE_EXPLICIT"
    ACTIVE_TASK_RELEVANCE = "ACTIVE_TASK_RELEVANCE"
    ACTIVE_FROZEN_RUN = "ACTIVE_FROZEN_RUN"
    ACTIVE_CONTINUATION = "ACTIVE_CONTINUATION"
    STAND_DOWN_COST_CAP = "STAND_DOWN_COST_CAP"
    UNAVAILABLE = "UNAVAILABLE"


class ReasonCode(str, Enum):
    MODE_OFF = "MODE_OFF"
    LEGACY_DELEGATED = "LEGACY_DELEGATED"
    EXPLICIT_REQUEST = "EXPLICIT_REQUEST"
    FROZEN_RUN_BINDING = "FROZEN_RUN_BINDING"
    TASK_REQUIREMENT_CANDIDATE = "TASK_REQUIREMENT_CANDIDATE"
    TASK_REQUIREMENT_MATCH = "TASK_REQUIREMENT_MATCH"
    CONTINUATION_LEASE = "CONTINUATION_LEASE"
    CONTINUATION_EXPIRED = "CONTINUATION_EXPIRED"
    NO_TRIGGER = "NO_TRIGGER"
    UNKNOWN_OR_AMBIGUOUS = "UNKNOWN_OR_AMBIGUOUS"
    PROFILE_UNAVAILABLE = "PROFILE_UNAVAILABLE"
    COST_CAP_EXHAUSTED = "COST_CAP_EXHAUSTED"
    CONTEXT_TRUNCATED = "CONTEXT_TRUNCATED"


@dataclass(frozen=True)
class ContinuationLease:
    """A bounded, caller-owned continuation binding.

    ``expires_at_monotonic`` must be expressed in the same clock as the event's
    ``now_monotonic``.  Leases longer than five minutes never activate FOIL.
    """

    issued_at_monotonic: float
    expires_at_monotonic: float


@dataclass(frozen=True)
class ActivationEvent:
    """One input event.  The prompt is never retained in an output object."""

    prompt: str
    # The canonical task requirement remains opaque to this policy module.
    task_requirement: Optional[object] = None
    # L0 receives only this bounded declaration, never introspects the object.
    requirement_joinable: bool = False
    frozen_run_binding: Optional[str] = None
    continuation_lease: Optional[ContinuationLease] = None
    now_monotonic: Optional[float] = None
    available_context_chars: int = MAX_ACTIVE_CONTEXT_CHARS


@dataclass(frozen=True)
class FoilSignal:
    """A control-only signal, never user-facing context or prompt content."""

    code: ReasonCode
    boundary: SignalAuthority = SignalAuthority.CONTROL_ONLY


@dataclass(frozen=True)
class ActivationTrace:
    """Safe diagnostic record: a one-way prompt hash and controlled metadata."""

    prompt_hash: str
    reason_codes: Tuple[ReasonCode, ...]
    signal_counts: Tuple[Tuple[str, int], ...]
    signals: Tuple[FoilSignal, ...]
    duration_ms: float
    context_chars: int
    routing_decisions: int


@dataclass(frozen=True)
class ActivationDecision:
    outcome: ActivationOutcome
    trace: ActivationTrace
    active_context: str
    state_transition_required: bool
    profile_update_required: bool = False


# These callbacks deliberately use opaque, canonical objects owned by the caller.
ProfileLoader = Callable[[], Optional[object]]
RequirementRouter = Callable[[object, object], bool]
ContextRenderer = Callable[[object], str]


_EXPLICIT_FOIL = re.compile(r"(?:^|\s)/foil(?:\s|$)|\b(?:activate|use|run)\s+foil\b", re.IGNORECASE)


def parse_feature_mode(
    value: Optional[Union[str, FeatureMode]], *, legacy_default: FeatureMode = FeatureMode.LEGACY
) -> FeatureMode:
    """Parse an environment/caller value fail-closed, with caller-owned default."""

    if isinstance(value, FeatureMode):
        return value
    if value is None or str(value).strip() == "":
        return legacy_default
    try:
        return FeatureMode(str(value).strip().lower())
    except ValueError:
        return FeatureMode.OFF


def _valid_continuation(lease: Optional[ContinuationLease], now: float) -> bool:
    if lease is None:
        return False
    duration = lease.expires_at_monotonic - lease.issued_at_monotonic
    return 0.0 < duration <= MAX_CONTINUATION_LEASE_SECONDS and now < lease.expires_at_monotonic


class FoilActivationMonitor:
    """Pure policy object with injected, post-L0 profile/routing dependencies."""

    def __init__(
        self,
        profile_loader: Optional[ProfileLoader] = None,
        requirement_router: Optional[RequirementRouter] = None,
        context_renderer: Optional[ContextRenderer] = None,
        *,
        max_active_context_chars: int = MAX_ACTIVE_CONTEXT_CHARS,
    ) -> None:
        if not 0 <= max_active_context_chars <= MAX_ACTIVE_CONTEXT_CHARS:
            raise ValueError("max_active_context_chars must be between 0 and 1200")
        self._profile_loader = profile_loader
        self._requirement_router = requirement_router
        self._context_renderer = context_renderer
        self._max_active_context_chars = max_active_context_chars

    def evaluate(
        self,
        event: ActivationEvent,
        mode: Union[str, FeatureMode, None] = FeatureMode.LEGACY,
        *,
        legacy_default: FeatureMode = FeatureMode.LEGACY,
    ) -> ActivationDecision:
        """Evaluate a single event; no state is retained and no polling occurs."""

        started = perf_counter()
        selected_mode = parse_feature_mode(mode, legacy_default=legacy_default)
        codes: list[ReasonCode] = []
        signals: list[FoilSignal] = []
        routing_decisions = 0
        context = ""

        def mark(code: ReasonCode) -> None:
            codes.append(code)
            signals.append(FoilSignal(code=code))

        prompt_hash = sha256(event.prompt.encode("utf-8")).hexdigest()

        if selected_mode is FeatureMode.OFF:
            mark(ReasonCode.MODE_OFF)
            return self._decision(
                ActivationOutcome.INACTIVE_NO_TRIGGER,
                event,
                selected_mode,
                codes,
                signals,
                prompt_hash,
                started,
                context,
                routing_decisions,
            )
        if selected_mode is FeatureMode.LEGACY:
            # The caller retains legacy behavior; this monitor makes no wake or load.
            mark(ReasonCode.LEGACY_DELEGATED)
            return self._decision(
                ActivationOutcome.UNAVAILABLE,
                event,
                selected_mode,
                codes,
                signals,
                prompt_hash,
                started,
                context,
                routing_decisions,
            )
        if event.available_context_chars <= 0 or self._max_active_context_chars <= 0:
            mark(ReasonCode.COST_CAP_EXHAUSTED)
            return self._decision(
                ActivationOutcome.STAND_DOWN_COST_CAP,
                event,
                selected_mode,
                codes,
                signals,
                prompt_hash,
                started,
                context,
                routing_decisions,
            )

        now = monotonic() if event.now_monotonic is None else event.now_monotonic
        explicit = bool(_EXPLICIT_FOIL.search(event.prompt))
        frozen = bool(event.frozen_run_binding and event.frozen_run_binding.strip())
        continuation = _valid_continuation(event.continuation_lease, now)
        relevance_candidate = (
            event.task_requirement is not None and event.requirement_joinable is True
        )
        if explicit:
            mark(ReasonCode.EXPLICIT_REQUEST)
        if frozen:
            mark(ReasonCode.FROZEN_RUN_BINDING)
        if continuation:
            mark(ReasonCode.CONTINUATION_LEASE)
        elif event.continuation_lease is not None:
            mark(ReasonCode.CONTINUATION_EXPIRED)
        if relevance_candidate:
            mark(ReasonCode.TASK_REQUIREMENT_CANDIDATE)

        # L0 ends here.  No injected dependency is reachable above this line.
        if not (explicit or frozen or continuation or relevance_candidate):
            mark(ReasonCode.NO_TRIGGER)
            return self._decision(
                ActivationOutcome.INACTIVE_NO_TRIGGER,
                event,
                selected_mode,
                codes,
                signals,
                prompt_hash,
                started,
                context,
                routing_decisions,
            )

        profile: Optional[object] = None
        if self._profile_loader is not None:
            try:
                loaded = self._profile_loader()
                profile = loaded
            except Exception:
                profile = None
            if profile is None:
                mark(ReasonCode.PROFILE_UNAVAILABLE)

        outcome: Optional[ActivationOutcome] = None
        if explicit:
            outcome = ActivationOutcome.ACTIVE_EXPLICIT
        elif frozen:
            outcome = ActivationOutcome.ACTIVE_FROZEN_RUN
        elif continuation:
            outcome = ActivationOutcome.ACTIVE_CONTINUATION
        elif (
            relevance_candidate
            and profile is not None
            and event.task_requirement is not None
            and self._requirement_router is not None
        ):
            routing_decisions = 1
            try:
                matched = bool(self._requirement_router(event.task_requirement, profile))
            except Exception:
                matched = False
            if matched:
                mark(ReasonCode.TASK_REQUIREMENT_MATCH)
                outcome = ActivationOutcome.ACTIVE_TASK_RELEVANCE

        if outcome is None:
            mark(ReasonCode.UNKNOWN_OR_AMBIGUOUS)
            return self._decision(
                ActivationOutcome.UNAVAILABLE,
                event,
                selected_mode,
                codes,
                signals,
                prompt_hash,
                started,
                context,
                routing_decisions,
            )

        if (
            profile is not None
            and self._context_renderer is not None
            and selected_mode is FeatureMode.SMART
        ):
            limit = min(
                self._max_active_context_chars,
                event.available_context_chars,
                MAX_ACTIVE_CONTEXT_CHARS,
            )
            try:
                candidate_context = self._context_renderer(profile)
                rendered_context = candidate_context if isinstance(candidate_context, str) else ""
                if not isinstance(candidate_context, str):
                    mark(ReasonCode.PROFILE_UNAVAILABLE)
            except Exception:
                rendered_context = ""
                mark(ReasonCode.PROFILE_UNAVAILABLE)
            context = rendered_context[:limit]
            if len(rendered_context) > len(context):
                mark(ReasonCode.CONTEXT_TRUNCATED)
        # Observe deliberately runs the same decision path but exposes no context
        # and requests no profile mutation.
        return self._decision(
            outcome,
            event,
            selected_mode,
            codes,
            signals,
            prompt_hash,
            started,
            context,
            routing_decisions,
        )

    @staticmethod
    def _decision(
        outcome: ActivationOutcome,
        event: ActivationEvent,
        mode: FeatureMode,
        codes: Sequence[ReasonCode],
        signals: Sequence[FoilSignal],
        prompt_hash: str,
        started: float,
        context: str,
        routing_decisions: int,
    ) -> ActivationDecision:
        counts = tuple(
            (code.value, sum(1 for item in codes if item is code)) for code in dict.fromkeys(codes)
        )
        trace = ActivationTrace(
            prompt_hash=prompt_hash,
            reason_codes=tuple(codes),
            signal_counts=counts,
            signals=tuple(signals),
            duration_ms=(perf_counter() - started) * 1000.0,
            context_chars=len(context),
            routing_decisions=routing_decisions,
        )
        active = outcome.name.startswith("ACTIVE_")
        return ActivationDecision(
            outcome=outcome,
            trace=trace,
            active_context=context,
            state_transition_required=active and mode is FeatureMode.SMART,
            profile_update_required=False,
        )
