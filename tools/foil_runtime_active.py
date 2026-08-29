"""Canonical public entry point for active FOIL v2 execution.

The boundary validates host adapters and records their observed resource use
before orchestration crosses the persistence and comparison boundaries.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from foil_active_runtime_v2 import (
    FoilRuntimePolicyV2,
    FoilRuntimeReceiptV2,
    RuntimeOutcomeV2,
    run_foil_v2 as _run_core,
)
from foil_bounded_answer_constructor_v2 import ConstructorRunnerV2
from foil_evidence_archive import RawEvidenceArchive
from foil_evidence_contract import QuestionObligation
from foil_retrieval_claim_comparator import SemanticComparator
from foil_route_opportunity_v2 import RuntimeToolFamily
from foil_runtime_token_ledger import RuntimeTokenLedger
from foil_runtime_tools_v2 import RuntimeToolAdapterV2, ToolBoundaryFailure, ToolProbeV2
from foil_tool_contract_v2 import BoundaryFailureCode, ToolContractV2, ToolReceiptV2


class _ValidatedAdapter:
    def __init__(self, inner: RuntimeToolAdapterV2, ledger: RuntimeTokenLedger):
        self.inner = inner
        self.ledger = ledger
        self.family = inner.family
        self.tool_id = inner.tool_id
        self.tool_version = inner.tool_version

    def probe(self, task):  # type: ignore[no-untyped-def]
        probe = self.inner.probe(task)
        if not isinstance(probe, ToolProbeV2):
            raise TypeError("adapter probe must return ToolProbeV2")
        return probe

    def execute(
        self, contract: ToolContractV2, task, probe: ToolProbeV2  # type: ignore[no-untyped-def]
    ) -> ToolReceiptV2:
        receipt: ToolReceiptV2 | None = None
        try:
            candidate = self.inner.execute(contract, task, probe)
            if not isinstance(candidate, ToolReceiptV2):
                raise TypeError("adapter execute must return ToolReceiptV2")
            receipt = candidate
            self.ledger.note_observed(
                f"call-{contract.contract_digest[:16]}",
                usage=receipt.usage,
                tool_calls=receipt.tool_calls,
                latency_ms=receipt.latency_ms,
                monetary_microunits=receipt.monetary_microunits,
            )
            receipt.validate_against(contract)
            return receipt
        except ToolBoundaryFailure:
            raise
        except (TypeError, ValueError) as exc:
            detail = str(exc)
            code = (
                BoundaryFailureCode.RESOURCE_OVERRUN
                if "exceed" in detail or "envelope" in detail
                else BoundaryFailureCode.MALFORMED_RESULT
            )
            raise ToolBoundaryFailure(
                code,
                detail,
                usage=None if receipt is None else receipt.usage,
                tool_calls=0 if receipt is None else receipt.tool_calls,
                latency_ms=0 if receipt is None else receipt.latency_ms,
                monetary_microunits=0 if receipt is None else receipt.monetary_microunits,
            ) from exc


def run_foil(
    raw_task: Mapping[str, object],
    a0: str,
    obligation: QuestionObligation,
    *,
    adapters: Mapping[RuntimeToolFamily, RuntimeToolAdapterV2],
    ledger: RuntimeTokenLedger,
    policy: FoilRuntimePolicyV2,
    archive: RawEvidenceArchive | None,
    constructor_runner: ConstructorRunnerV2 | None = None,
    semantic_comparator: SemanticComparator | None = None,
) -> tuple[str, FoilRuntimeReceiptV2]:
    if (
        policy.answer_change_enabled
        and policy.comparator.semantic_enabled
        and not policy.comparator.semantic_route_admitted
    ):
        raise ValueError("active answer change cannot use an unadmitted semantic comparator")
    wrapped = {
        family: _ValidatedAdapter(adapter, ledger)
        for family, adapter in adapters.items()
    }
    final, receipt = _run_core(
        raw_task,
        a0,
        obligation,
        adapters=wrapped,
        ledger=ledger,
        policy=policy,
        archive=archive,
        constructor_runner=constructor_runner,
        semantic_comparator=semantic_comparator,
    )
    if (
        final == a0
        and receipt.outcome in {RuntimeOutcomeV2.VERIFY_RESOLVED, RuntimeOutcomeV2.FULL_RESOLVED}
        and (receipt.selection is None or receipt.selection.get("answer_changed") is not True)
    ):
        receipt = replace(receipt, outcome=RuntimeOutcomeV2.PRESERVED_A0)
    return final, receipt


__all__ = [
    "FoilRuntimePolicyV2",
    "FoilRuntimeReceiptV2",
    "RuntimeOutcomeV2",
    "run_foil",
]
