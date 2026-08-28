from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_evidence_contract import (  # noqa: E402
    AnswerKind,
    ComputationBinding,
    ComputationReceipt,
    EvidenceDocument,
    EvidencePacket,
    EvidenceSpan,
    QuestionObligation,
    SourceClass,
)


class EvidenceContractTests(unittest.TestCase):
    def test_computation_bindings_require_canonical_rationals(self) -> None:
        with self.assertRaisesRegex(ValueError, "canonical rational"):
            ComputationBinding("B", "10/2")

    def test_obligation_closed_round_trip_and_tamper(self) -> None:
        item = QuestionObligation("task-1", digest("question"), AnswerKind.EXACT_TEXT)
        self.assertEqual(QuestionObligation.from_mapping(item.trace()), item)
        raw = copy.deepcopy(item.trace())
        raw["gold"] = "answer"
        with self.assertRaisesRegex(ValueError, "closed question-obligation"):
            QuestionObligation.from_mapping(raw)
        raw = copy.deepcopy(item.trace())
        raw["answer_kind"] = "NUMBER"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            QuestionObligation.from_mapping(raw)

    def test_span_must_be_exact_document_slice(self) -> None:
        document = EvidenceDocument(
            "doc-1", "https://example.com/source", "Source", "prefix section 7 suffix",
            "2026-08-28T00:00:00Z", SourceClass.PRIMARY, "source-1",
        )
        span = EvidenceSpan("span-1", "doc-1", 7, 16, "section 7")
        packet = EvidencePacket(digest("question"), (document,), (span,), tool_calls=1)
        self.assertEqual(packet.span("span-1"), span)
        self.assertFalse(packet.trace()["raw_evidence_stored"])
        with self.assertRaisesRegex(ValueError, "exact document slice"):
            EvidencePacket(
                digest("question"),
                (document,),
                (EvidenceSpan("span-1", "doc-1", 7, 16, "section 3"),),
            )

    def test_exact_computation_and_provenance(self) -> None:
        document = EvidenceDocument(
            "doc-1", "https://example.com/value", "Value", "5",
            "2026-08-28T00:00:00Z", SourceClass.PRIMARY, "source-1",
        )
        span = EvidenceSpan("span-1", "doc-1", 0, 1, "5")
        receipt = ComputationReceipt(
            "compute-1", "6 * B", (ComputationBinding("B", "5", "span-1"),), "30"
        )
        packet = EvidencePacket(digest("question"), (document,), (span,), (receipt,))
        self.assertEqual(packet.computation("compute-1").output, "30")
        with self.assertRaisesRegex(ValueError, "does not match"):
            ComputationReceipt(
                "compute-2", "6 * B", (ComputationBinding("B", "5", "span-1"),), "29"
            )
        with self.assertRaisesRegex(ValueError, "unknown span"):
            EvidencePacket(
                digest("question"),
                (document,),
                (span,),
                (ComputationReceipt(
                    "compute-3", "6 * B", (ComputationBinding("B", "5", "missing"),), "30"
                ),),
            )

    def test_call_conservation_and_https_boundary(self) -> None:
        with self.assertRaisesRegex(ValueError, "canonical HTTPS"):
            EvidenceDocument(
                "doc", "http://example.com", "Title", "content",
                "2026-08-28", SourceClass.UNKNOWN, "group",
            )
        with self.assertRaisesRegex(ValueError, "exceed total"):
            EvidencePacket(digest("q"), (), (), tool_calls=1, search_calls=1, fetch_calls=1)


if __name__ == "__main__":
    unittest.main()
