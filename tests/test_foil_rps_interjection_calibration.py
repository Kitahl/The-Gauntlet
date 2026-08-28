"""Regression tests for evidence-gated no-tools RPS interjection."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_rps import CheckKind  # noqa: E402
from foil_rps_host_verifier import (  # noqa: E402
    HostTaskDescriptor,
    HostTaskType,
    select_check,
    verify_answer,
)
from foil_rps_v062 import (  # noqa: E402
    BlindRivalReceipt,
    HostVerifierOutcome,
    HostVerifierReceipt,
    PrecommittedHostCheck,
    check_commitment_digest,
)
from foil_rps_v063 import (  # noqa: E402
    RPSV063Action,
    RPSV063Policy,
    evaluate_unique_host_result,
    evaluate_verified_correction,
)
from foil_smart_tool_calibration import BenchmarkTarget  # noqa: E402


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _check() -> PrecommittedHostCheck:
    task_digest = _digest("task")
    answer_form_digest = _digest("integer")
    specification_digest = _digest("exact expected integer")
    commitment_digest = check_commitment_digest(
        task_digest=task_digest,
        answer_form_digest=answer_form_digest,
        check_id="integer-check",
        kind=CheckKind.EXACT_RELATION,
        check_spec_digest=specification_digest,
    )
    return PrecommittedHostCheck(
        task_digest=task_digest,
        answer_form_digest=answer_form_digest,
        check_id="integer-check",
        kind=CheckKind.EXACT_RELATION,
        check_spec_digest=specification_digest,
        commitment_digest=commitment_digest,
    )


def _host(answer: str, outcome: HostVerifierOutcome) -> HostVerifierReceipt:
    frozen = _check()
    return HostVerifierReceipt(
        task_digest=frozen.task_digest,
        check_commitment_digest=frozen.commitment_digest,
        candidate_digest=_digest(answer),
        outcome=outcome,
        observation_digest=(
            None
            if outcome is HostVerifierOutcome.NOT_APPLICABLE
            else _digest(f"observation:{answer}:{outcome.value}")
        ),
    )


def _rival(answer: str) -> BlindRivalReceipt:
    frozen = _check()
    return BlindRivalReceipt(
        task_digest=frozen.task_digest,
        answer_form_digest=frozen.answer_form_digest,
        rival_digest=_digest(answer),
        request_digest=_digest("task-only-rival-request"),
        model_route_digest=_digest("different-route"),
        incumbent_withheld=True,
        input_tokens=10,
        output_tokens=2,
    )


def _load_harness():
    path = ROOT / "benchmarks" / "harness" / "foil_rps_interjection_calibration.py"
    spec = importlib.util.spec_from_file_location("foil_rps_interjection_report", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load interjection calibration harness")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RPSInterjectionCalibrationTests(unittest.TestCase):
    def test_default_policy_disables_blind_rival(self) -> None:
        self.assertEqual(RPSV063Policy().max_blind_rivals, 0)

    def test_zero_rival_policy_keeps_host_verified_benchmark_correction(self) -> None:
        selected = select_check(
            HostTaskDescriptor(
                task_digest=_digest("processbench-task"),
                answer_form_digest=_digest("processbench-answer"),
                task_type=HostTaskType.PROCESSBENCH_FIRST_ERROR,
                source_steps=(r"\[2+2=4\]", r"\[3+3=7\]"),
            )
        )
        base = verify_answer(selected, {"answer": "OK", "abstain": False})
        decision = evaluate_unique_host_result(
            selected,
            base,
            {"answer": "1", "abstain": False},
            policy=RPSV063Policy(enabled=True, max_blind_rivals=0),
        )
        self.assertEqual(decision.action, RPSV063Action.SELECT_HOST_RESULT)
        self.assertTrue(decision.answer_change_authorized)
        self.assertFalse(decision.production_authorized)

    def test_zero_rival_policy_preserves_decline_and_abstains_on_contradiction(self) -> None:
        policy = RPSV063Policy(enabled=True, max_blind_rivals=0)
        declined = evaluate_verified_correction(
            _check(),
            _host("A", HostVerifierOutcome.NOT_APPLICABLE),
            policy=policy,
        )
        contradicted = evaluate_verified_correction(
            _check(),
            _host("A", HostVerifierOutcome.CONTRADICTED),
            policy=policy,
        )
        self.assertEqual(declined.action, RPSV063Action.KEEP_BASE)
        self.assertEqual(
            declined.reason, "blind_rival_disabled_after_host_decline"
        )
        self.assertEqual(contradicted.action, RPSV063Action.ABSTAIN)
        self.assertEqual(
            contradicted.reason,
            "blind_rival_disabled_after_host_contradiction",
        )

    def test_zero_rival_policy_rejects_rival_and_invalid_ceiling(self) -> None:
        policy = RPSV063Policy(enabled=True, max_blind_rivals=0)
        with self.assertRaisesRegex(ValueError, "zero-rival"):
            evaluate_verified_correction(
                _check(),
                _host("A", HostVerifierOutcome.NOT_APPLICABLE),
                policy=policy,
                rival=_rival("B"),
                rival_host=_host("B", HostVerifierOutcome.NOT_APPLICABLE),
            )
        with self.assertRaisesRegex(ValueError, "zero or one"):
            RPSV063Policy(enabled=True, max_blind_rivals=2)

    def test_frozen_evidence_disables_model_interjection(self) -> None:
        harness = _load_harness()
        report = harness.build_report(
            harness._read(
                ROOT
                / "benchmark_runs"
                / "2026-08-26"
                / "hle_active_20"
                / "independent_audit.json"
            ),
            harness._read(
                ROOT
                / "benchmark_runs"
                / "2026-08-25"
                / "rps_v063_active_replay"
                / "report.json"
            ),
            harness._read(
                ROOT
                / "benchmark_runs"
                / "2026-08-25"
                / "rps_v063_stage2_small"
                / "predictions.json"
            ),
            harness._read(
                ROOT
                / "benchmark_runs"
                / "2026-08-25"
                / "rps_v063_stage2_small"
                / "report.json"
            ),
            target=BenchmarkTarget(60, 11, 22, 250_000),
        )
        interjection = report["interjection"]
        self.assertEqual(
            interjection["same_context_review_evidence"]["status"],
            "STAND_DOWN",
        )
        self.assertEqual(
            interjection["blind_rival_evidence"]["status"],
            "UNCALIBRATED",
        )
        self.assertEqual(interjection["runtime_policy"]["max_blind_rivals"], 0)
        self.assertTrue(interjection["host_verified_selection_enabled"])
        self.assertFalse(interjection["blind_rival_enabled"])
        self.assertEqual(report["measured_stage2"]["added_total_tokens"], 55_407)
        self.assertEqual(report["measured_stage2"]["rescues"], 0)
        self.assertEqual(report["new_token_spend"], 0)

    def test_frozen_report_hash_is_deterministic(self) -> None:
        harness = _load_harness()
        args = (
            harness._read(
                ROOT
                / "benchmark_runs"
                / "2026-08-26"
                / "hle_active_20"
                / "independent_audit.json"
            ),
            harness._read(
                ROOT
                / "benchmark_runs"
                / "2026-08-25"
                / "rps_v063_active_replay"
                / "report.json"
            ),
            harness._read(
                ROOT
                / "benchmark_runs"
                / "2026-08-25"
                / "rps_v063_stage2_small"
                / "predictions.json"
            ),
            harness._read(
                ROOT
                / "benchmark_runs"
                / "2026-08-25"
                / "rps_v063_stage2_small"
                / "report.json"
            ),
        )
        target = BenchmarkTarget(60, 11, 22, 250_000)
        first = harness.build_report(*args, target=target)
        second = harness.build_report(*args, target=target)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
