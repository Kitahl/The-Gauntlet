"""Aggregate-unbounded, per-call-bounded accounting for FOIL v2.

The ledger is not a benchmark kill switch. It launches only calls whose
prelaunch value is positive and whose individual resource envelope is finite.
Observed resource use is conserved even when a call overruns its envelope or a
later persistence boundary fails.
"""

from __future__ import annotations

from dataclasses import dataclass

from egrt_types import digest
from foil_tool_contract_v2 import ResourceEnvelopeV2, RouteValueEstimate, TokenUsageV2


class RuntimeLedgerError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeReservation:
    call_id: str
    contract_digest: str
    envelope: ResourceEnvelopeV2
    value: RouteValueEstimate
    provider_cap_enforced: bool

    def __post_init__(self) -> None:
        if not isinstance(self.call_id, str) or not self.call_id.strip():
            raise ValueError("call_id must be non-empty text")
        if not isinstance(self.contract_digest, str) or len(self.contract_digest) != 64:
            raise ValueError("contract_digest must be SHA-256 hex")
        if not isinstance(self.envelope, ResourceEnvelopeV2):
            raise TypeError("envelope must be ResourceEnvelopeV2")
        if not isinstance(self.value, RouteValueEstimate):
            raise TypeError("value must be RouteValueEstimate")
        if not isinstance(self.provider_cap_enforced, bool):
            raise TypeError("provider_cap_enforced must be bool")


@dataclass(frozen=True)
class RuntimeSettlement:
    call_id: str
    contract_digest: str
    usage: TokenUsageV2
    tool_calls: int
    latency_ms: int
    monetary_microunits: int
    cancelled: bool = False
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.usage, TokenUsageV2):
            raise TypeError("usage must be TokenUsageV2")
        for name in ("tool_calls", "latency_ms", "monetary_microunits"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not isinstance(self.cancelled, bool):
            raise TypeError("cancelled must be bool")
        if self.cancelled and (not isinstance(self.reason, str) or not self.reason):
            raise ValueError("cancelled settlement requires a reason")
        if not self.cancelled and self.reason is not None:
            raise ValueError("completed settlement cannot carry cancellation reason")

    def trace(self) -> dict[str, object]:
        return {
            "call_id": self.call_id,
            "contract_sha256": self.contract_digest,
            "usage": self.usage.trace(),
            "tool_calls": self.tool_calls,
            "latency_ms": self.latency_ms,
            "monetary_microunits": self.monetary_microunits,
            "cancelled": self.cancelled,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ObservedSpend:
    usage: TokenUsageV2
    tool_calls: int
    latency_ms: int
    monetary_microunits: int

    def __post_init__(self) -> None:
        if not isinstance(self.usage, TokenUsageV2):
            raise TypeError("usage must be TokenUsageV2")
        for name in ("tool_calls", "latency_ms", "monetary_microunits"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")


class RuntimeTokenLedger:
    """Track complete spend without imposing an aggregate total-token ceiling."""

    def __init__(self) -> None:
        self._active: dict[str, RuntimeReservation] = {}
        self._observed: dict[str, ObservedSpend] = {}
        self._settled: list[RuntimeSettlement] = []

    @property
    def spent_usage(self) -> TokenUsageV2:
        return TokenUsageV2(
            sum(item.usage.input_tokens for item in self._settled),
            sum(item.usage.cached_input_tokens for item in self._settled),
            sum(item.usage.output_tokens for item in self._settled),
        )

    @property
    def active_call_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._active))

    def reserve(
        self,
        *,
        call_id: str,
        contract_digest: str,
        envelope: ResourceEnvelopeV2,
        value: RouteValueEstimate,
        provider_cap_enforced: bool,
    ) -> RuntimeReservation:
        if (
            call_id in self._active
            or call_id in self._observed
            or any(item.call_id == call_id for item in self._settled)
        ):
            raise RuntimeLedgerError("call_id has already been used")
        reservation = RuntimeReservation(
            call_id, contract_digest, envelope, value, provider_cap_enforced
        )
        if not value.executes:
            raise RuntimeLedgerError("prelaunch expected value is not positive")
        if envelope.maximum_total_tokens and not provider_cap_enforced:
            raise RuntimeLedgerError("token-consuming call lacks an enforced per-call envelope")
        self._active[call_id] = reservation
        return reservation

    def note_observed(
        self,
        call_id: str,
        *,
        usage: TokenUsageV2,
        tool_calls: int,
        latency_ms: int,
        monetary_microunits: int,
    ) -> None:
        if call_id not in self._active:
            raise RuntimeLedgerError("cannot observe an inactive call")
        observed = ObservedSpend(usage, tool_calls, latency_ms, monetary_microunits)
        previous = self._observed.get(call_id)
        if previous is not None and previous != observed:
            raise RuntimeLedgerError("observed spend changed after execution")
        self._observed[call_id] = observed

    @staticmethod
    def _violations(
        envelope: ResourceEnvelopeV2,
        usage: TokenUsageV2,
        tool_calls: int,
        latency_ms: int,
        monetary_microunits: int,
    ) -> tuple[str, ...]:
        violations: list[str] = []
        if usage.input_tokens > envelope.maximum_input_tokens:
            violations.append("input-token envelope exceeded")
        if usage.cached_input_tokens > envelope.maximum_cached_input_tokens:
            violations.append("cached-input envelope exceeded")
        if usage.output_tokens > envelope.maximum_output_tokens:
            violations.append("output-token envelope exceeded")
        if tool_calls > envelope.maximum_tool_calls:
            violations.append("tool-call envelope exceeded")
        if latency_ms > envelope.maximum_latency_ms:
            violations.append("latency envelope exceeded")
        if monetary_microunits > envelope.maximum_monetary_microunits:
            violations.append("monetary envelope exceeded")
        return tuple(violations)

    @staticmethod
    def _contains_observation(settlement: ObservedSpend, prior: ObservedSpend) -> bool:
        return (
            settlement.usage.input_tokens >= prior.usage.input_tokens
            and settlement.usage.cached_input_tokens >= prior.usage.cached_input_tokens
            and settlement.usage.output_tokens >= prior.usage.output_tokens
            and settlement.tool_calls >= prior.tool_calls
            and settlement.latency_ms >= prior.latency_ms
            and settlement.monetary_microunits >= prior.monetary_microunits
        )

    def settle(
        self,
        call_id: str,
        *,
        usage: TokenUsageV2,
        tool_calls: int,
        latency_ms: int,
        monetary_microunits: int,
    ) -> RuntimeSettlement:
        reservation = self._active.get(call_id)
        if reservation is None:
            raise RuntimeLedgerError("call_id has no active reservation")
        settlement = ObservedSpend(usage, tool_calls, latency_ms, monetary_microunits)
        prior = self._observed.get(call_id)
        if prior is not None and not self._contains_observation(settlement, prior):
            raise RuntimeLedgerError("settlement omits previously observed spend")
        self._observed.pop(call_id, None)
        self._active.pop(call_id)
        violations = self._violations(
            reservation.envelope,
            usage,
            tool_calls,
            latency_ms,
            monetary_microunits,
        )
        if violations:
            reason = "resource_envelope_exceeded:" + ";".join(violations)
            item = RuntimeSettlement(
                call_id,
                reservation.contract_digest,
                usage,
                tool_calls,
                latency_ms,
                monetary_microunits,
                True,
                reason,
            )
            self._settled.append(item)
            raise RuntimeLedgerError(reason)
        item = RuntimeSettlement(
            call_id,
            reservation.contract_digest,
            usage,
            tool_calls,
            latency_ms,
            monetary_microunits,
        )
        self._settled.append(item)
        return item

    def cancel(self, call_id: str, reason: str) -> RuntimeSettlement:
        reservation = self._active.pop(call_id, None)
        if reservation is None:
            raise RuntimeLedgerError("call_id has no active reservation")
        observed = self._observed.pop(call_id, None)
        item = RuntimeSettlement(
            call_id,
            reservation.contract_digest,
            TokenUsageV2() if observed is None else observed.usage,
            0 if observed is None else observed.tool_calls,
            0 if observed is None else observed.latency_ms,
            0 if observed is None else observed.monetary_microunits,
            True,
            reason,
        )
        self._settled.append(item)
        return item

    def trace(self) -> dict[str, object]:
        settled_ids = [item.call_id for item in self._settled]
        active_ids = set(self._active)
        body: dict[str, object] = {
            "schema": "foil.runtime-token-ledger.v2",
            "aggregate_token_ceiling": None,
            "aggregate_cancellation_enabled": False,
            "per_call_envelopes_required": True,
            "positive_prelaunch_value_required": True,
            "observed_spend_conserved_on_failure": True,
            "spent_usage": self.spent_usage.trace(),
            "active_call_ids": list(self.active_call_ids),
            "observed_call_ids": sorted(self._observed),
            "settlements": [item.trace() for item in self._settled],
            "conserved": (
                len(set(settled_ids)) == len(settled_ids)
                and not (active_ids & set(settled_ids))
                and set(self._observed).issubset(active_ids)
            ),
        }
        body["ledger_sha256"] = digest(body)
        return body
