from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_tool_contract import (  # noqa: E402
    EvidenceAdmission,
    EvidenceEnvelope,
    ToolContract,
    ToolCost,
    ToolFamily,
    ToolOperation,
    ToolOutcome,
    ToolReceipt,
)


def contract(*, retrieval: bool = False) -> ToolContract:
    return ToolContract(
        task_id="task-1",
        question_digest=digest("question"),
        a0_digest=digest("A"),
        tool_id="tool",
        tool_version="1",
        capability="WEB_SEARCH" if retrieval else "SYMBOLIC_COMPUTATION",
        family=ToolFamily.RETRIEVAL if retrieval else ToolFamily.COMPUTATION,
        operation=(
            ToolOperation.WEB_RETRIEVAL
            if retrieval
            else ToolOperation.EXACT_ARITHMETIC
        ),
        operation_input_digest=digest("input"),
        cost=ToolCost(
            maximum_input_tokens=10 if retrieval else 0,
            maximum_output_tokens=5 if retrieval else 0,
            maximum_latency_ms=100,
        ),
        timeout_ms=100,
        provider_cap_enforced=True,
    )


class ToolContractTests(unittest.TestCase):
    def test_closed_round_trip_and_digest(self) -> None:
        original = contract()
        parsed = ToolContract.from_mapping(original.trace())
        self.assertEqual(parsed, original)
        tampered = copy.deepcopy(original.trace())
        tampered["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "closed contract schema"):
            ToolContract.from_mapping(tampered)
        tampered = copy.deepcopy(original.trace())
        tampered["tool_version"] = "2"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            ToolContract.from_mapping(tampered)

    def test_cost_conservation_fails_closed(self) -> None:
        raw = contract(retrieval=True).trace()
        raw["cost"]["maximum_total_tokens"] = 999
        with self.assertRaisesRegex(ValueError, "not conserved"):
            ToolContract.from_mapping(raw)

    def test_operation_capability_and_authority_are_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "operation does not match"):
            ToolContract(
                **{
                    **contract().__dict__,
                    "capability": "CODE_EXECUTION",
                }
            )
        with self.assertRaisesRegex(ValueError, "non-authoritative"):
            ToolContract(
                **{
                    **contract().__dict__,
                    "answer_change_authority": True,
                }
            )

    def test_mechanical_evidence_is_corrective(self) -> None:
        item = contract()
        receipt = ToolReceipt(
            call_id="call-1",
            contract_digest=item.contract_digest,
            outcome=ToolOutcome.VERIFIED,
            candidate_answer="4",
            evidence_digest=digest("2+2=4"),
            mechanically_verified=True,
            latency_ms=1,
        )
        envelope = EvidenceEnvelope.from_receipt(item, receipt)
        self.assertEqual(envelope.admission, EvidenceAdmission.BENCHMARK_CORRECTIVE_UNADMITTED)

    def test_retrieval_is_support_only_and_needs_sources(self) -> None:
        item = contract(retrieval=True)
        receipt = ToolReceipt(
            call_id="call-2",
            contract_digest=item.contract_digest,
            outcome=ToolOutcome.SUPPORTING,
            candidate_answer="B",
            evidence_digest=digest("source says B"),
            source_urls=("https://example.com/source",),
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
        )
        envelope = EvidenceEnvelope.from_receipt(item, receipt)
        self.assertEqual(envelope.admission, EvidenceAdmission.SUPPORT_ONLY)
        self.assertFalse(envelope.trace()["answer_change_authority"])
        with self.assertRaisesRegex(ValueError, "sources"):
            ToolReceipt(
                call_id="call-3",
                contract_digest=item.contract_digest,
                outcome=ToolOutcome.SUPPORTING,
                evidence_digest=digest("missing source"),
            )

    def test_receipt_overrun_and_retrieval_privilege_escalation_rejected(self) -> None:
        item = contract(retrieval=True)
        overrun = ToolReceipt(
            call_id="call-4",
            contract_digest=item.contract_digest,
            outcome=ToolOutcome.SUPPORTING,
            evidence_digest=digest("evidence"),
            source_urls=("https://example.com/",),
            input_tokens=11,
            output_tokens=5,
        )
        with self.assertRaisesRegex(ValueError, "token envelope"):
            overrun.validate_against(item)
        with self.assertRaisesRegex(ValueError, "mechanically verified"):
            ToolReceipt(
                call_id="call-5",
                contract_digest=item.contract_digest,
                outcome=ToolOutcome.VERIFIED,
                candidate_answer="B",
                mechanically_verified=False,
            )


if __name__ == "__main__":
    unittest.main()
