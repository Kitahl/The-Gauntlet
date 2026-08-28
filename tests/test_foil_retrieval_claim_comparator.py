from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_evidence_contract import (  # noqa: E402
    AnswerKind,
    AtomicClaim,
    CandidateAnswer,
    CandidateOrigin,
    ClaimKind,
    EvidenceDocument,
    EvidencePacket,
    EvidenceSpan,
    QuestionObligation,
    SourceClass,
)
from foil_retrieval_claim_comparator import (  # noqa: E402
    ClaimStatus,
    ComparatorPolicy,
    SemanticComparison,
    compare_candidate,
)


def evidence(*, temporal: str | None = None, jurisdiction: str | None = None) -> EvidencePacket:
    document = EvidenceDocument(
        "doc", "https://example.com/source", "Source", "section 7",
        "2026-08-28", SourceClass.PRIMARY, "source",
        temporal_scope=temporal, jurisdiction=jurisdiction,
    )
    return EvidencePacket(
        digest("question"), (document,), (EvidenceSpan("span", "doc", 0, 9, "section 7"),)
    )


def candidate(claim: AtomicClaim) -> CandidateAnswer:
    return CandidateAnswer(
        "candidate", claim.text, AnswerKind.EXACT_TEXT, (claim,),
        CandidateOrigin.EVIDENCE_CONSTRUCTED,
    )


class RetrievalClaimComparatorTests(unittest.TestCase):
    def test_omitted_binding_is_preserved_in_conservation(self) -> None:
        item = candidate(AtomicClaim("claim", "section 7", ClaimKind.ANSWER, "section 7"))
        assessment = compare_candidate(
            item, evidence(), obligation=QuestionObligation("task", digest("question"), AnswerKind.EXACT_TEXT),
            policy=ComparatorPolicy(),
        )
        self.assertEqual((assessment.supported, assessment.contradicted, assessment.unresolved, assessment.omitted), (0, 0, 0, 1))
        self.assertTrue(assessment.trace()["claim_conservation"])
        self.assertFalse(assessment.selection_eligible)

    def test_ambiguous_evidence_is_not_averaged_into_support(self) -> None:
        item = candidate(AtomicClaim(
            "claim", "section 7", ClaimKind.ANSWER, "section 7",
            evidence_span_ids=("span",),
        ))
        # Avoid exact-bound-span shortcut so the semantic ambiguity is exercised.
        item = candidate(AtomicClaim(
            "claim", "section seven applies", ClaimKind.ANSWER, "section seven applies",
            evidence_span_ids=("span",),
        ))
        assessment = compare_candidate(
            item, evidence(), obligation=QuestionObligation("task", digest("question"), AnswerKind.EXACT_TEXT),
            policy=ComparatorPolicy(semantic_enabled=True, allow_unadmitted_benchmark_selection=True),
            semantic_comparator=lambda claim, spans: SemanticComparison(
                ClaimStatus.AMBIGUOUS, 990_000, ("span",), "sources_conflict"
            ),
        )
        self.assertEqual(assessment.unresolved, 1)
        self.assertFalse(assessment.selection_eligible)

    def test_unknown_span_from_comparator_is_citation_laundering(self) -> None:
        item = candidate(AtomicClaim(
            "claim", "section seven applies", ClaimKind.ANSWER, "section seven applies",
            evidence_span_ids=("span",),
        ))
        with self.assertRaisesRegex(ValueError, "unknown evidence span"):
            compare_candidate(
                item, evidence(), obligation=QuestionObligation("task", digest("question"), AnswerKind.EXACT_TEXT),
                policy=ComparatorPolicy(semantic_enabled=True),
                semantic_comparator=lambda claim, spans: SemanticComparison(
                    ClaimStatus.SUPPORTED, 990_000, ("invented",), "laundered_citation"
                ),
            )

    def test_constructed_claim_cannot_swap_to_an_unbound_citation(self) -> None:
        document = EvidenceDocument(
            "doc", "https://example.com/source", "Source", "alpha beta",
            "2026-08-28", SourceClass.PRIMARY, "source",
        )
        packet = EvidencePacket(
            digest("question"), (document,),
            (
                EvidenceSpan("bound", "doc", 0, 5, "alpha"),
                EvidenceSpan("other", "doc", 6, 10, "beta"),
            ),
        )
        item = candidate(AtomicClaim(
            "claim", "alpha applies", ClaimKind.ANSWER, "alpha applies",
            evidence_span_ids=("bound",),
        ))
        with self.assertRaisesRegex(ValueError, "outside constructed claim binding"):
            compare_candidate(
                item, packet,
                obligation=QuestionObligation("task", digest("question"), AnswerKind.EXACT_TEXT),
                policy=ComparatorPolicy(semantic_enabled=True),
                semantic_comparator=lambda claim, spans: SemanticComparison(
                    ClaimStatus.SUPPORTED, 990_000, ("other",), "citation_swap"
                ),
            )

    def test_source_class_policy_fails_closed(self) -> None:
        item = candidate(AtomicClaim(
            "claim", "section seven applies", ClaimKind.ANSWER,
            "section seven applies", evidence_span_ids=("span",),
        ))
        assessment = compare_candidate(
            item, evidence(),
            obligation=QuestionObligation("task", digest("question"), AnswerKind.EXACT_TEXT),
            policy=ComparatorPolicy(
                semantic_enabled=True,
                allowed_source_classes=(SourceClass.SCHOLARLY,),
            ),
            semantic_comparator=lambda claim, spans: SemanticComparison(
                ClaimStatus.SUPPORTED, 990_000, (), "must_not_apply"
            ),
        )
        self.assertEqual(assessment.verdicts[0].status, ClaimStatus.OUT_OF_SCOPE)

    def test_temporal_jurisdiction_and_unit_mismatch_are_out_of_scope(self) -> None:
        claim = AtomicClaim(
            "claim", "section 7", ClaimKind.ANSWER, "section 7",
            evidence_span_ids=("span",), unit="kg", temporal_scope="2025", jurisdiction="CA",
        )
        item = candidate(claim)
        obligation = QuestionObligation(
            "task", digest("question"), AnswerKind.EXACT_TEXT,
            requested_unit="m", temporal_scope="2026", jurisdiction="US",
        )
        assessment = compare_candidate(
            item, evidence(temporal="2025", jurisdiction="CA"), obligation=obligation,
            policy=ComparatorPolicy(),
        )
        self.assertEqual(assessment.verdicts[0].status, ClaimStatus.OUT_OF_SCOPE)
        self.assertFalse(assessment.selection_eligible)


if __name__ == "__main__":
    unittest.main()
