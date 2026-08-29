from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_evidence_contract import (  # noqa: E402
    AnswerKind,
    CandidateOrigin,
    ComputationReceipt,
    EvidencePacket,
    QuestionObligation,
    single_answer_candidate,
)
from foil_retrieval_claim_comparator import ClaimStatus, ComparatorPolicy  # noqa: E402
from foil_retrieval_claim_comparator_v2 import compare_candidate_v2  # noqa: E402


class ComparatorV2ObligationTests(unittest.TestCase):
    def packet(self, question: str) -> EvidencePacket:
        return EvidencePacket(
            digest(question),
            (),
            (),
            (ComputationReceipt("compute-five", "5", (), "5"),),
        )

    def test_unique_number_cannot_contradict_exact_text_answer(self) -> None:
        question = "Can two graphs have different numbers of 5-cycles?"
        assessment = compare_candidate_v2(
            single_answer_candidate(
                "No", answer_kind=AnswerKind.EXACT_TEXT, origin=CandidateOrigin.BASE
            ),
            self.packet(question),
            obligation=QuestionObligation("task", digest(question), AnswerKind.EXACT_TEXT),
            policy=ComparatorPolicy(),
        )
        self.assertEqual(assessment.verdicts[0].status, ClaimStatus.INSUFFICIENT)
        self.assertEqual(assessment.contradicted, 0)
        self.assertFalse(assessment.selection_eligible)

    def test_unique_number_still_adjudicates_numeric_answer(self) -> None:
        question = "Compute 2 + 3."
        assessment = compare_candidate_v2(
            single_answer_candidate(
                "4", answer_kind=AnswerKind.NUMBER, origin=CandidateOrigin.BASE
            ),
            self.packet(question),
            obligation=QuestionObligation("task", digest(question), AnswerKind.NUMBER),
            policy=ComparatorPolicy(),
        )
        self.assertEqual(assessment.verdicts[0].status, ClaimStatus.CONTRADICTED)
        self.assertEqual(assessment.contradicted, 1)


if __name__ == "__main__":
    unittest.main()
