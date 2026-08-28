"""Fail-closed provider-token reservations for paid FOIL benchmarks.

The ledger counts every provider token category in one caller-supplied total,
including cached input.  It authorizes a call only when the provider/harness
can enforce that call's reservation.  Post-hoc accounting alone is not a
spending control.
"""

from __future__ import annotations

from dataclasses import dataclass


class BenchmarkBudgetError(RuntimeError):
    """A benchmark call cannot be launched within the hard token envelope."""


@dataclass(frozen=True)
class TokenReservation:
    call_id: str
    maximum_total_tokens: int


class BenchmarkTokenLedger:
    def __init__(self, maximum_total_tokens: int):
        if (
            isinstance(maximum_total_tokens, bool)
            or not isinstance(maximum_total_tokens, int)
            or maximum_total_tokens < 0
        ):
            raise ValueError("maximum_total_tokens must be a non-negative integer")
        self._cap = maximum_total_tokens
        self._spent = 0
        self._reservations: dict[str, int] = {}

    @property
    def maximum_total_tokens(self) -> int:
        return self._cap

    @property
    def spent_total_tokens(self) -> int:
        return self._spent

    @property
    def reserved_total_tokens(self) -> int:
        return sum(self._reservations.values())

    @property
    def remaining_unreserved_tokens(self) -> int:
        return self._cap - self._spent - self.reserved_total_tokens

    def reserve(
        self,
        call_id: str,
        maximum_total_tokens: int,
        *,
        provider_cap_enforced: bool,
    ) -> TokenReservation:
        if not isinstance(call_id, str) or not call_id.strip():
            raise ValueError("call_id must be non-empty text")
        if call_id in self._reservations:
            raise BenchmarkBudgetError("call_id already reserved")
        if not isinstance(provider_cap_enforced, bool):
            raise TypeError("provider_cap_enforced must be bool")
        if not provider_cap_enforced:
            raise BenchmarkBudgetError(
                "provider cannot enforce the reservation before launch"
            )
        if (
            isinstance(maximum_total_tokens, bool)
            or not isinstance(maximum_total_tokens, int)
            or maximum_total_tokens < 0
        ):
            raise ValueError("maximum_total_tokens must be a non-negative integer")
        if maximum_total_tokens > self.remaining_unreserved_tokens:
            raise BenchmarkBudgetError("reservation would exceed benchmark token cap")
        self._reservations[call_id] = maximum_total_tokens
        return TokenReservation(call_id, maximum_total_tokens)

    def settle(self, call_id: str, actual_total_tokens: int) -> None:
        if call_id not in self._reservations:
            raise BenchmarkBudgetError("call_id has no active reservation")
        if (
            isinstance(actual_total_tokens, bool)
            or not isinstance(actual_total_tokens, int)
            or actual_total_tokens < 0
        ):
            raise ValueError("actual_total_tokens must be a non-negative integer")
        reservation = self._reservations.pop(call_id)
        if actual_total_tokens > reservation:
            raise BenchmarkBudgetError("provider exceeded its enforced reservation")
        self._spent += actual_total_tokens

    def cancel(self, call_id: str) -> None:
        if call_id not in self._reservations:
            raise BenchmarkBudgetError("call_id has no active reservation")
        del self._reservations[call_id]

    def trace(self) -> dict[str, object]:
        return {
            "schema": "foil.benchmark-token-ledger.v1",
            "maximum_total_tokens": self._cap,
            "spent_total_tokens": self._spent,
            "reserved_total_tokens": self.reserved_total_tokens,
            "remaining_unreserved_tokens": self.remaining_unreserved_tokens,
            "active_call_ids": sorted(self._reservations),
            "counts_cached_input": True,
            "requires_provider_enforced_reservations": True,
        }
