"""Benchmark-owned adapter for the canonical active FOIL runtime.

This module deliberately contains no benchmark selection, scoring, or global
budget policy.  It gives future benchmark harnesses one narrow call boundary
and a fail-closed accounting projection for each independently executed row.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from foil_active_runtime_v2 import FoilRuntimeReceiptV2  # noqa: E402
from foil_bounded_answer_constructor_v2 import ConstructorRunnerV2  # noqa: E402
from foil_evidence_archive import RawEvidenceArchive  # noqa: E402
from foil_evidence_contract import QuestionObligation  # noqa: E402
from foil_retrieval_claim_comparator import SemanticComparator  # noqa: E402
from foil_route_opportunity_v2 import RuntimeToolFamily  # noqa: E402
from foil_runtime_active import FoilRuntimePolicyV2, run_foil  # noqa: E402
from foil_runtime_token_ledger import RuntimeTokenLedger  # noqa: E402
from foil_runtime_tools_v2 import RuntimeToolAdapterV2  # noqa: E402


ACCOUNTING_VALID = "VALID"
ACCOUNTING_INVALID = "ACCOUNTING_INVALID"
_USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "total_tokens",
)


def _usage_validation(raw: object) -> tuple[dict[str, object] | None, tuple[str, ...]]:
    """Preserve observed usage while validating it without zero-filling."""

    if not isinstance(raw, Mapping):
        return None, ("spent_usage_missing",)

    usage = {str(key): value for key, value in raw.items()}
    reasons: list[str] = []
    missing = [field for field in _USAGE_FIELDS if field not in usage]
    if missing:
        reasons.append("spent_usage_missing_fields:" + ",".join(missing))

    for field in _USAGE_FIELDS:
        value = usage.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            reasons.append(f"spent_usage_invalid_{field}")

    if not reasons:
        expected_total = (
            int(usage["input_tokens"])
            + int(usage["cached_input_tokens"])
            + int(usage["output_tokens"])
        )
        if usage["total_tokens"] != expected_total:
            reasons.append("spent_usage_total_mismatch")
    return usage, tuple(reasons)


def receipt_accounting_fields(receipt: FoilRuntimeReceiptV2) -> dict[str, object]:
    """Project canonical receipt accounting into a benchmark row.

    An incomplete receipt may still contain observed partial spend.  The spend
    is retained verbatim, while the row is marked accounting-invalid.  Missing
    or malformed usage remains ``None``/malformed; it is never converted to a
    synthetic zero-token receipt.
    """

    if not isinstance(receipt, FoilRuntimeReceiptV2):
        raise TypeError("receipt must be FoilRuntimeReceiptV2")

    ledger_after = receipt.ledger_after
    reasons: list[str] = []
    if not receipt.cost_accounting_complete:
        reasons.append("runtime_marked_accounting_incomplete")
    if not isinstance(ledger_after, Mapping):
        usage = None
        reasons.append("ledger_after_missing")
    else:
        usage, usage_reasons = _usage_validation(ledger_after.get("spent_usage"))
        reasons.extend(usage_reasons)

    return {
        "accounting_status": ACCOUNTING_VALID if not reasons else ACCOUNTING_INVALID,
        "cost_accounting_complete": receipt.cost_accounting_complete,
        "spent_usage": usage,
        "accounting_invalid_reasons": reasons,
    }


def run_benchmark_row(
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
) -> tuple[str, dict[str, Any]]:
    """Run one item through the canonical boundary and return row-safe fields."""

    final, receipt = run_foil(
        raw_task,
        a0,
        obligation,
        adapters=adapters,
        ledger=ledger,
        policy=policy,
        archive=archive,
        constructor_runner=constructor_runner,
        semantic_comparator=semantic_comparator,
    )
    row: dict[str, Any] = {
        "foil_final": final,
        "foil_runtime_outcome": receipt.outcome.value,
        "foil_runtime_receipt": receipt.trace(),
    }
    row.update(receipt_accounting_fields(receipt))
    return final, row


__all__ = [
    "ACCOUNTING_INVALID",
    "ACCOUNTING_VALID",
    "receipt_accounting_fields",
    "run_benchmark_row",
]
