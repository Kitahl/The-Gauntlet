from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_evidence as ev  # noqa: E402
import foil_signal_boundary as boundary  # noqa: E402
from foil_policy import ProfileSignal  # noqa: E402


class SignalAuthorityTests(unittest.TestCase):
    def test_control_signal_cannot_satisfy_factual_obligation(self):
        signal = boundary.RoutedSignal("predicted_complement_usefulness", score=0.9)
        self.assertFalse(
            boundary.may_satisfy_factual_obligation(signal, ordinary_admission_passed=True)
        )

    def test_control_signal_cannot_promote_competence(self):
        signal = boundary.RoutedSignal("router_score", score=0.95)
        observation = ev.Observation(True, ev.EvidenceTier.REAL_WORK, verifier="rubric")
        with self.assertRaises(boundary.EvidenceAdmissionError):
            boundary.admit_competence_observation(
                signal, observation, ordinary_admission_passed=True
            )

    def test_evidence_candidate_still_requires_ordinary_admission(self):
        signal = boundary.RoutedSignal("tool_result", boundary.SignalAuthority.EVIDENCE_CANDIDATE)
        observation = ev.Observation(True, ev.EvidenceTier.REAL_WORK, verifier="rubric")
        with self.assertRaises(boundary.EvidenceAdmissionError):
            boundary.admit_competence_observation(signal, observation)
        admitted = boundary.admit_competence_observation(
            signal, observation, ordinary_admission_passed=True
        )
        self.assertIs(admitted, observation)

    def test_existing_estimator_still_controls_candidate_weight(self):
        signal = boundary.RoutedSignal(
            "unverified_result", boundary.SignalAuthority.EVIDENCE_CANDIDATE
        )
        observation = ev.Observation(True, ev.EvidenceTier.UNVERIFIED)
        admitted = boundary.admit_competence_observation(
            signal, observation, ordinary_admission_passed=True
        )
        summary = ev.summarize([admitted])
        self.assertEqual(summary.classification, ev.Classification.INSUFFICIENT_EVIDENCE)

    def test_profile_router_refuses_evidence_authority(self):
        with self.assertRaises(ValueError):
            ProfileSignal(authority=boundary.SignalAuthority.EVIDENCE_CANDIDATE)

    def test_trace_contains_no_raw_signal(self):
        trace = boundary.RoutedSignal("candidate_rank", score=0.5).trace()
        self.assertEqual(trace["authority"], "CONTROL_ONLY")
        self.assertFalse(trace["raw_signal_stored"])


if __name__ == "__main__":
    unittest.main()
