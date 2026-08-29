from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gauntlet_automatic as automatic  # noqa: E402
import gauntlet_evidence_context as ec  # noqa: E402
from egrt_types import Verdict, digest  # noqa: E402

POLICY = "context" + "_policy"
ARTIFACT = digest("artifact")
STATE = digest("state")
FIELDS = tuple(sorted((POLICY, "evaluator_version", "harness_identity", "oracle_semantics", "source_artifact_hash")))


def qualifiers(**overrides: object) -> ec.EvidenceQualifiers:
    values = dict(
        execution_status=ec.ExecutionStatus.TESTED,
        validity_status=ec.ValidityStatus.DETERMINISTIC_PASS,
        fidelity_status=ec.FidelityStatus.PASSED,
        independence_status=ec.IndependenceStatus.INDEPENDENT,
        provenance_status=ec.ProvenanceStatus.BOUND,
        admission_status=ec.AdmissionStatus.ADMITTED,
    )
    values.update(overrides)
    return ec.EvidenceQualifiers(**values)


def evaluator(*, oracle: str = "exact", harness: str = "h1", policy: str = "fresh", session: ec.SessionState = ec.SessionState.WARMED_STATE) -> ec.EvaluationContextIdentity:
    return ec.EvaluationContextIdentity(
        harness_identity=harness,
        evaluator_version="v1",
        oracle_semantics=oracle,
        **{POLICY: policy},
        source_artifact_hash=ARTIFACT,
        session_state=session,
    )


def envelope(*, values: ec.EvidenceQualifiers | None = None, session: ec.SessionState = ec.SessionState.WARMED_STATE, generation: int = 0, evaluation: ec.EvaluationContextIdentity | None = None, transition: ec.LifecycleTransitionAuthority | None = None, lineage: str | None = None, failures: tuple[str, ...] = ()) -> ec.EvidenceContextEnvelope:
    return ec.EvidenceContextEnvelope(
        qualifiers=values or qualifiers(),
        source_artifact_hash=ARTIFACT,
        source_state_hash=STATE,
        session_state=session,
        lifecycle_transition=transition or ec.LifecycleTransitionAuthority(
            cause=ec.TransitionCause.BOUND_RECEIPT,
            target_state="DONE",
            source_state_hash=STATE,
            receipt_id="r1",
            evidence_generation=generation,
        ),
        evaluation_context=evaluation or evaluator(session=session),
        provenance=ec.ProvenanceAdapterBinding(
            backend="in-toto",
            adapter_version="v1",
            record_digest=digest("record"),
            subject_digest=ARTIFACT,
        ),
        required_evaluation_fields=FIELDS,
        session_lineage_hash=lineage,
        rerun_generation=generation,
        failure_categories=failures,
    )


def requirement(**overrides: object) -> ec.EvidenceContextRequirement:
    values = dict(
        required=True,
        require_tested_execution=True,
        require_fidelity=True,
        require_independence=True,
        require_bound_provenance=True,
        require_evaluation_identity=True,
        required_evaluation_fields=FIELDS,
        current_source_artifact_hash=ARTIFACT,
        current_source_state_hash=STATE,
        current_generation=0,
    )
    values.update(overrides)
    return ec.EvidenceContextRequirement(**values)


def assess(item: ec.EvidenceContextEnvelope, profile: ec.EvidenceContextRequirement | None = None) -> ec.EvidenceContextAssessment:
    return ec.assess_envelope(
        item,
        profile or requirement(),
        receipt_id="r1",
        current_source_state_hash=STATE,
        current_source_artifact_hash=ARTIFACT,
        current_generation=0,
    )


class EvidenceContextTests(unittest.TestCase):
    def test_qualifiers_are_orthogonal(self) -> None:
        cases = (
            (dict(execution_status=ec.ExecutionStatus.CLAIMED), Verdict.ISSUE, "SELF_ATTESTED_EXECUTION_ONLY"),
            (dict(validity_status=ec.ValidityStatus.FORMAL_PASS, fidelity_status=ec.FidelityStatus.FAILED), Verdict.ISSUE, "FIDELITY_FAILED"),
            (dict(validity_status=ec.ValidityStatus.FORMAL_PASS, fidelity_status=ec.FidelityStatus.UNCHECKED, admission_status=ec.AdmissionStatus.PENDING), Verdict.UNKNOWN, "FIDELITY_REQUIRED_BUT_UNRESOLVED"),
            (dict(validity_status=ec.ValidityStatus.UNCHECKED, admission_status=ec.AdmissionStatus.PENDING), Verdict.UNKNOWN, "VALIDITY_UNCHECKED_OR_OUT_OF_PROFILE"),
            (dict(admission_status=ec.AdmissionStatus.PENDING), Verdict.UNKNOWN, "ADMISSION_PENDING"),
        )
        for changes, verdict, reason in cases:
            with self.subTest(reason=reason):
                result = assess(envelope(values=qualifiers(**changes)))
                self.assertEqual(result.verdict, verdict)
                self.assertIn(reason, result.reasons)

    def test_evaluator_identity_binds_load_bearing_context(self) -> None:
        baseline = evaluator()
        changed = (
            evaluator(oracle="semantic"),
            evaluator(harness="h2"),
            evaluator(policy="resumed"),
            evaluator(session=ec.SessionState.COLD_START),
        )
        self.assertTrue(all(baseline.identity_hash != row.identity_hash for row in changed))
        incomplete = ec.EvaluationContextIdentity(
            harness_identity="h1",
            source_artifact_hash=ARTIFACT,
            session_state=ec.SessionState.WARMED_STATE,
        )
        self.assertTrue(any(r.startswith("EVALUATION_CONTEXT_MISSING:") for r in assess(envelope(evaluation=incomplete)).reasons))

    def test_state_lineage_tamper_and_rerun_guards(self) -> None:
        for state in (ec.SessionState.STALE_STATE, ec.SessionState.SUPERSEDED_STATE):
            self.assertNotEqual(assess(envelope(session=state, evaluation=evaluator(session=state))).verdict, Verdict.CLEARED)
        resumed = envelope(
            session=ec.SessionState.RESUMED_STATE,
            evaluation=evaluator(session=ec.SessionState.RESUMED_STATE),
            lineage=digest("prior"),
        )
        parsed = ec.EvidenceContextEnvelope.from_mapping(resumed.to_dict())
        self.assertEqual(parsed.session_lineage_hash, digest("prior"))
        raw = envelope().to_dict()
        raw["qualifiers"]["validity_status"] = ec.ValidityStatus.FAIL.value
        receipt = {"receipt_id": "r1", "evidence": [{"metadata": {ec.EVIDENCE_CONTEXT_METADATA_KEY: raw}}]}
        self.assertEqual(ec.assess_receipt_context(receipt, requirement()).status, "INVALID_OR_TAMPERED_EVIDENCE_CONTEXT")
        self.assertIn("SOURCE_STATE_CHANGED", assess(envelope(), requirement(current_source_state_hash=digest("new"))).reasons)
        self.assertIn("RERUN_GENERATION_INVALIDATED", assess(envelope(), requirement(current_generation=1)).reasons)

    def test_transition_rule_and_external_taxonomy_boundaries(self) -> None:
        transition = ec.LifecycleTransitionAuthority(
            cause=ec.TransitionCause.DETERMINISTIC_RULE,
            target_state="DONE",
            source_state_hash=STATE,
            rule_id="rule",
            rule_version="1",
            evidence_generation=0,
        )
        item = envelope(transition=transition)
        self.assertIn("DETERMINISTIC_RULE_NOT_REGISTERED", assess(item).reasons)
        self.assertEqual(assess(item, replace(requirement(), registered_transition_rules=("rule@1",))).verdict, Verdict.CLEARED)
        categorized = envelope(failures=("AUTORESEARCHEVAL:TOOL_ERROR",))
        self.assertEqual(assess(categorized).verdict, assess(envelope()).verdict)
        self.assertNotEqual(categorized.content_hash, envelope().content_hash)

    def test_legacy_receipt_is_readable_but_not_promoted(self) -> None:
        legacy = ec.assess_receipt_context({"receipt_id": "old", "evidence": []}, ec.EvidenceContextRequirement())
        self.assertEqual(legacy.status, "LEGACY_UNQUALIFIED_READABLE")
        self.assertTrue(legacy.legacy_readable)
        self.assertIsNone(legacy.admission_status)
        self.assertEqual(ec.assess_receipt_context({"receipt_id": "old", "evidence": []}, requirement()).verdict, Verdict.UNKNOWN)

    def test_task_gate_and_automatic_authority(self) -> None:
        profile = requirement().to_dict()
        task = {
            "content_hash": STATE,
            "metadata": {},
            "obligations": [
                {
                    "obligation_id": "proof",
                    "required_module": "mind",
                    "load_bearing": True,
                    "metadata": {ec.EVIDENCE_REQUIREMENT_METADATA_KEY: profile},
                },
                {"obligation_id": "assure", "required_module": "gauntlet", "load_bearing": True},
            ],
        }
        receipt = {
            "receipt_id": "r1",
            "module": "mind",
            "obligation_id": "proof",
            "task_id": "t1",
            "evidence": [{"metadata": {ec.EVIDENCE_CONTEXT_METADATA_KEY: envelope().to_dict()}}],
        }
        admitted = ec.assess_task_evidence_context(task, [receipt], task_id="t1", assurance_obligation_id="assure")
        self.assertEqual(admitted.verdict, Verdict.CLEARED)
        missing = ec.assess_task_evidence_context(task, [{**receipt, "evidence": []}], task_id="t1", assurance_obligation_id="assure")
        self.assertEqual(missing.verdict, Verdict.UNKNOWN)
        self.assertEqual(ec.ASSURANCE_AUTHORITY, "ASSURANCE_ONLY")
        self.assertEqual(len(automatic.low_level.OPERATIONS), 10)
        full = automatic.AutomaticAssurancePolicy(mode="AUTOMATIC_FULL", max_operations=0, max_cost_units=0)
        selective = automatic.AutomaticAssurancePolicy(mode="SELECTIVE_EXPERIMENTAL", max_operations=1, max_cost_units=1)
        self.assertFalse(full.stop_on_issue)
        self.assertTrue(selective.mode.endswith("EXPERIMENTAL"))


if __name__ == "__main__":
    unittest.main()
