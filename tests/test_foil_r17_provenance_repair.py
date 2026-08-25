from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_host_finalizer import answer_digest  # noqa: E402
from egrt_verifiers import DEFAULT_REGISTRY, VerificationStatus  # noqa: E402
from foil_obligation_compiler import compile_task_spec  # noqa: E402
from foil_obligation_discovery import (  # noqa: E402
    DiscoveryPolicy,
    DiscoveryRequestError,
    DiscoveryStatus,
    discover_obligations,
)
from foil_obligation_discovery_admission import compile_admitted_discovery  # noqa: E402
from foil_obligation_discovery_v2 import (  # noqa: E402
    DISCOVERY_ROUTE_ID,
    discover_obligations_v2,
)
from foil_residual_scanner import scan  # noqa: E402
from foil_v5_metrics import ScanStatus  # noqa: E402


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _request(question: str, answer: str) -> dict[str, str]:
    return {
        "task_text": question,
        "a0_text": answer,
        "task_digest": _digest(question),
        "a0_digest": answer_digest(answer),
    }


def _detected(question: str, answer: str) -> bool:
    envelope = discover_obligations_v2(
        _request(question, answer), policy=DiscoveryPolicy(enabled=True)
    )
    if envelope.status is not DiscoveryStatus.FOUND:
        return False
    compiled = compile_task_spec(envelope.task_spec, observed_a0_digest=envelope.a0_digest)
    reports = [
        scan(plan, envelope.a0_digest, compiled.deterministic_cases(plan.claim_id))
        for plan in compiled.deterministic_scanner_plans()
    ]
    return any(report.status is ScanStatus.FAIL for report in reports)


CORRECT_CASES = (
    (
        "Raphael bought 4 pens at $1.5, 2 notebooks at $4, and a ream at $20.",
        "Pens <<1.5*4=6>>6. Notebooks <<4*2=8>>8. Ream <<20*1=20>>20. "
        "Total <<6+8+20=34>>34.\nA: 34",
    ),
    (
        "There are 25 bars and 80 apples. A bar is twice an apple. A bar weighs 40g.",
        "Bars <<25*40=1000>>1000. Apples <<80*20=1600>>1600. "
        "Total <<1000+1600=2600>>2600.\nA: 2600",
    ),
    (
        "A company spends $15000, then a third of that amount.",
        "Second year <<15000/3=5000>>5000. Total <<15000+5000=20000>>20000.\nA: 20000",
    ),
    (
        "There are 50 cats. 4 boats take 5 each. Then 3/5 of the rest run away.",
        "Boats <<4*5=20>>20. Remain <<50-20=30>>30. Run <<30*3/5=18>>18. "
        "Left <<30-18=12>>12.\nA: 12",
    ),
    (
        "Shondra has 7 fewer plants. Toni has 60% more than Frederick, who has 10.",
        "More <<10*.6=6>>6. Toni <<10+6=16>>16. Shondra <<16-7=9>>9.\nA: 9",
    ),
    (
        "There are 4 rows with 18 seats. One-fourth are administrators and one-third of the rest are parents.",
        "Seats <<18*4=72>>72. After admins <<72-18=54>>54. Parents <<54*1/3=18>>18. "
        "Students <<54-18=36>>36.\nA: 36",
    ),
    (
        "There are 2 brothers and 3 sisters. The sisters are 16. A 12 year old brother is half the older brother's age.",
        "Older <<12*2=24>>24. Sisters <<16*3=48>>48. Total <<48+24+12=84>>84.\nA: 84",
    ),
)


class ProvenanceV2BoundaryTests(unittest.TestCase):
    def test_v2_is_default_off_versioned_unadmitted_and_preserves_a0(self) -> None:
        question, answer = CORRECT_CASES[0]
        disabled = discover_obligations_v2(_request(question, answer))
        enabled = discover_obligations_v2(
            _request(question, answer), policy=DiscoveryPolicy(enabled=True)
        )
        self.assertIs(disabled.status, DiscoveryStatus.ABSTAIN)
        self.assertIs(enabled.status, DiscoveryStatus.FOUND)
        self.assertEqual(enabled.route, DISCOVERY_ROUTE_ID)
        self.assertEqual(enabled.origin, "GENERATED_UNADMITTED")
        self.assertTrue(enabled.admission_required)
        self.assertFalse(enabled.execution_authorized)
        self.assertFalse(enabled.answer_mutated)
        self.assertIs(enabled.base_answer, answer)
        self.assertEqual(enabled.a0_digest, answer_digest(answer))
        self.assertEqual((enabled.provider_calls, enabled.profile_writes, enabled.action_count), (0, 0, 0))
        with self.assertRaisesRegex(TypeError, "DiscoveryEnvelope"):
            compile_admitted_discovery(enabled, admission=object())

    def test_gold_and_labels_are_rejected_and_hidden_changes_cannot_affect_output(self) -> None:
        question, answer = CORRECT_CASES[0]
        first = discover_obligations_v2(
            _request(question, answer), policy=DiscoveryPolicy(enabled=True)
        )
        second = discover_obligations_v2(
            _request(question, answer), policy=DiscoveryPolicy(enabled=True)
        )
        self.assertEqual(first.to_dict(), second.to_dict())
        for forbidden in ("gold", "ground_truth", "is_correct", "expected"):
            request = _request(question, answer)
            request[forbidden] = "hidden"
            with self.subTest(forbidden=forbidden), self.assertRaises(DiscoveryRequestError):
                discover_obligations_v2(request, policy=DiscoveryPolicy(enabled=True))

    def test_v1_route_behavior_remains_separate(self) -> None:
        question, answer = CORRECT_CASES[4]
        old = discover_obligations(
            _request(question, answer), policy=DiscoveryPolicy(enabled=True)
        )
        new = discover_obligations_v2(
            _request(question, answer), policy=DiscoveryPolicy(enabled=True)
        )
        self.assertEqual(old.route, "gsm8k.annotated-arithmetic.v1")
        self.assertEqual(new.route, "gsm8k.annotated-arithmetic.v2")
        self.assertNotEqual(old.route_binding_digest, new.route_binding_digest)


class StructuredProvenanceVerifierTests(unittest.TestCase):
    def test_mechanical_derivations_pass_and_forged_derivations_fail(self) -> None:
        valid_sources = [
            {"value": "60/1", "kind": "ROOT", "parents": [], "operator": "NONE"},
            {"value": "3/5", "kind": "PERCENT", "parents": ["60/1"], "operator": "DIVIDE_100"},
            {"value": "1/1", "kind": "IDENTITY", "parents": [], "operator": "NONE"},
            {"value": "8/5", "kind": "ONE_STEP", "parents": ["1/1", "3/5"], "operator": "ADD"},
        ]
        passed = DEFAULT_REGISTRY.run(
            "builtin.numeric_provenance_v2",
            {"operands": ["3/5", "8/5"], "sources": valid_sources},
        )
        forged = [dict(row) for row in valid_sources]
        forged[-1] = {**forged[-1], "value": "9/5"}
        failed = DEFAULT_REGISTRY.run(
            "builtin.numeric_provenance_v2",
            {"operands": ["9/5"], "sources": forged},
        )
        unknown = DEFAULT_REGISTRY.run(
            "builtin.numeric_provenance_v2",
            {"operands": ["3/5"], "sources": [{**valid_sources[0], "extra": True}]},
        )
        self.assertIs(passed.status, VerificationStatus.PASS)
        self.assertIs(failed.status, VerificationStatus.FAIL)
        self.assertIs(unknown.status, VerificationStatus.UNKNOWN)

    def test_all_seven_r16_false_fire_shapes_now_stand_down(self) -> None:
        for question, answer in CORRECT_CASES:
            with self.subTest(question=question):
                self.assertFalse(_detected(question, answer))

    def test_widening_does_not_admit_nearby_unsupported_operands(self) -> None:
        cases = (
            (
                CORRECT_CASES[1][0],
                "Bars <<25*40=1000>>1000. Apples <<80*21=1680>>1680. "
                "Total <<1000+1680=2680>>2680.\nA: 2680",
            ),
            (
                CORRECT_CASES[4][0],
                "More <<10*.7=7>>7. Toni <<10+7=17>>17. Shondra <<17-7=10>>10.\nA: 10",
            ),
            (
                CORRECT_CASES[3][0],
                "Boats <<4*5=20>>20. Remain <<50-20=30>>30. Run <<30*7/9=70/3>>70/3. "
                "Left <<30-70/3=20/3>>20/3.\nA: 20/3",
            ),
        )
        for question, answer in cases:
            with self.subTest(answer=answer):
                self.assertTrue(_detected(question, answer))


if __name__ == "__main__":
    unittest.main()
