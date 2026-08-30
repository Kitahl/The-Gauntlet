from __future__ import annotations

import ast
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import foil_certified_rule_bank_audit as pilot_audit  # noqa: E402
import foil_certified_rule_bank_pilot as pilot  # noqa: E402
from egrt_host_finalizer import answer_digest  # noqa: E402
from egrt_types import digest  # noqa: E402
from egrt_verifiers import DEFAULT_REGISTRY, VerificationStatus  # noqa: E402
from foil_arithmetic_rule_bank import (  # noqa: E402
    RULE_BANK_ROUTE_ID,
    RULE_BANK_VERSION,
    ArithmeticRuleBankEnvelope,
    discover_arithmetic_rule_bank,
)
from foil_certified_arithmetic import (  # noqa: E402
    CERTIFIED_LANGUAGE,
    POWER_LANGUAGE,
    RAW_NUMERIC_LANGUAGE,
    extract_step,
)
from foil_formalization_admission import (  # noqa: E402
    FormalizationAdmissionReceipt,
    FormalizationAdmissionStatus,
    FormalizationRouteBinding,
    TranslationDistance,
)
from foil_obligation_compiler import TASK_SPEC_SCHEMA, compile_task_spec  # noqa: E402
from foil_obligation_discovery import (  # noqa: E402
    DiscoveryPolicy,
    DiscoveryRequestError,
    DiscoveryStatus,
)
from foil_obligation_discovery_admission import compile_admitted_discovery  # noqa: E402
from foil_residual_scanner import scan  # noqa: E402
from foil_v5_metrics import ScanStatus  # noqa: E402


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _request(task: str, answer: str) -> dict[str, str]:
    return {
        "task_text": task,
        "a0_text": answer,
        "task_digest": _digest(task),
        "a0_digest": answer_digest(answer),
    }


def _envelope(answer: str) -> ArithmeticRuleBankEnvelope:
    return discover_arithmetic_rule_bank(
        _request("Check the arithmetic trace.", answer),
        policy=DiscoveryPolicy(enabled=True),
    )


def _statuses(envelope: ArithmeticRuleBankEnvelope) -> tuple[ScanStatus, ...]:
    if envelope.status is not DiscoveryStatus.FOUND or envelope.task_spec is None:
        return ()
    compiled = compile_task_spec(
        envelope.task_spec,
        observed_a0_digest=envelope.a0_digest,
    )
    return tuple(
        scan(plan, envelope.a0_digest, compiled.deterministic_cases(plan.claim_id)).status
        for plan in compiled.deterministic_scanner_plans()
    )


def _binding(envelope: ArithmeticRuleBankEnvelope) -> FormalizationRouteBinding:
    return FormalizationRouteBinding(
        route_id=RULE_BANK_ROUTE_ID,
        route_version=RULE_BANK_VERSION,
        translation_distance=TranslationDistance.EXECUTION,
        formalizer_fingerprints_sha256=("a" * 64,),
        task_regime_sha256=envelope.route_binding_digest,
        target_schema=TASK_SPEC_SCHEMA,
    )


def _receipt(
    envelope: ArithmeticRuleBankEnvelope,
    binding: FormalizationRouteBinding,
    *,
    status: FormalizationAdmissionStatus = FormalizationAdmissionStatus.ADMITTED,
) -> FormalizationAdmissionReceipt:
    assert envelope.task_spec_digest is not None
    return FormalizationAdmissionReceipt(
        status=status,
        reason_code="test_route_receipt",
        route_binding_digest=binding.binding_digest,
        target_schema=TASK_SPEC_SCHEMA,
        source_text_sha256=envelope.input_digest,
        generated_spec_sha256=envelope.task_spec_digest,
        calibration_sha256="b" * 64,
        policy_sha256="c" * 64,
        fidelity_lower_ppm=1_000_000,
        extraction_recall_lower_ppm=1_000_000,
        mutation_suite_complete=True,
        instance_checks_passed=True,
    )


class CertifiedLanguageSeparationTests(unittest.TestCase):
    def test_frozen_v2_still_abstains_on_powers(self) -> None:
        source = r"\[2^3 = 9\]"
        self.assertEqual(
            extract_step(source, step_index=0, language=CERTIFIED_LANGUAGE),
            (),
        )
        findings = extract_step(source, step_index=0, language=POWER_LANGUAGE)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].violating)

    def test_power_rule_requires_a_power_and_keeps_bounds(self) -> None:
        self.assertEqual(
            extract_step(r"\[2+3=5\]", step_index=0, language=POWER_LANGUAGE),
            (),
        )
        self.assertEqual(
            extract_step(r"\[2^13=8192\]", step_index=0, language=POWER_LANGUAGE),
            (),
        )
        finding = extract_step(
            r"\[2^{12}=4096\]",
            step_index=0,
            language=POWER_LANGUAGE,
        )[0]
        self.assertFalse(finding.violating)

    def test_raw_rule_accepts_only_a_complete_numeric_line(self) -> None:
        finding = extract_step(
            "1. 12 / 3 = 5",
            step_index=0,
            language=RAW_NUMERIC_LANGUAGE,
        )[0]
        self.assertTrue(finding.violating)
        rejected = (
            "Therefore 12 / 3 = 5",
            "$12 / 3 = 5",
            "12 kg = 12",
            "50% = 0.5",
            r"\(12 / 3 = 5\)",
            "2^3 = 9",
        )
        for source in rejected:
            with self.subTest(source=source):
                self.assertEqual(
                    extract_step(
                        source,
                        step_index=0,
                        language=RAW_NUMERIC_LANGUAGE,
                    ),
                    (),
                )


class RuleBankBoundaryTests(unittest.TestCase):
    def test_default_off_closed_no_oracle_boundary_and_a0_identity(self) -> None:
        request = _request("Compute.", r"\[2+2=5\]")
        disabled = discover_arithmetic_rule_bank(request)
        enabled = discover_arithmetic_rule_bank(
            request,
            policy=DiscoveryPolicy(enabled=True),
        )
        self.assertIs(disabled.status, DiscoveryStatus.ABSTAIN)
        self.assertIs(enabled.status, DiscoveryStatus.FOUND)
        self.assertEqual(enabled.origin, "GENERATED_UNADMITTED")
        self.assertTrue(enabled.admission_required)
        self.assertFalse(enabled.execution_authorized)
        self.assertIs(enabled.base_answer, request["a0_text"])
        self.assertEqual(enabled.a0_digest, request["a0_digest"])
        self.assertEqual(
            (
                enabled.provider_calls,
                enabled.token_count,
                enabled.profile_writes,
                enabled.action_count,
            ),
            (0, 0, 0, 0),
        )
        self.assertFalse(enabled.answer_mutated)
        for forbidden in ("gold", "ground_truth", "expected", "is_correct"):
            contaminated = dict(request)
            contaminated[forbidden] = "hidden"
            with self.subTest(forbidden=forbidden), self.assertRaises(
                DiscoveryRequestError
            ):
                discover_arithmetic_rule_bank(
                    contaminated,
                    policy=DiscoveryPolicy(enabled=True),
                )

    def test_hidden_gold_cannot_affect_output_but_a0_can(self) -> None:
        first = _envelope(r"\[2+2=4\]")
        repeated = _envelope(r"\[2+2=4\]")
        changed = _envelope(r"\[2+2=5\]")
        self.assertEqual(first.to_dict(), repeated.to_dict())
        self.assertNotEqual(first.input_digest, changed.input_digest)
        self.assertNotEqual(first.task_spec_digest, changed.task_spec_digest)

    def test_rules_compile_and_detect_without_mutating_a0(self) -> None:
        cases = (
            (r"\[2+3=6\]", CERTIFIED_LANGUAGE),
            (r"\[2^3=9\]", POWER_LANGUAGE),
            ("2+3=6", RAW_NUMERIC_LANGUAGE),
        )
        for answer, rule in cases:
            with self.subTest(rule=rule):
                envelope = _envelope(answer)
                self.assertEqual(envelope.rule_counts[rule], 1)
                self.assertIn(ScanStatus.FAIL, _statuses(envelope))
                self.assertEqual(envelope.base_answer, answer)
        correct = _envelope(r"\[2^3=8\]")
        self.assertEqual(_statuses(correct), (ScanStatus.PASS,))

    def test_trace_rule_names_joint_inconsistency_without_localization(self) -> None:
        inconsistent = _envelope("6B = 30; B = 4")
        consistent = _envelope("6B = 30; B = 5")
        self.assertEqual(
            inconsistent.rule_counts["trace-constraint-consistency-v1"],
            1,
        )
        self.assertEqual(_statuses(inconsistent), (ScanStatus.FAIL,))
        self.assertEqual(_statuses(consistent), (ScanStatus.PASS,))
        claim = inconsistent.task_spec["claims"][0]
        self.assertIn("joint trace constraint", claim["obligations"][0]["description"])
        self.assertIn("no step localization or repair", claim["obligations"][0]["description"])
        self.assertNotIn("blame", str(claim).lower())

    def test_trace_rule_rejects_ambiguous_commas(self) -> None:
        envelope = _envelope("1,2B = 12; B = 1")
        self.assertIs(envelope.status, DiscoveryStatus.PARTIAL)
        self.assertEqual(
            envelope.rule_counts["trace-constraint-consistency-v1"],
            0,
        )

    def test_unknown_equalities_fail_closed_as_partial(self) -> None:
        envelope = _envelope("The result is x = 4.")
        self.assertIs(envelope.status, DiscoveryStatus.PARTIAL)
        self.assertIsNone(envelope.task_spec)

    def test_module_has_no_network_io_provider_or_dynamic_execution(self) -> None:
        source = (ROOT / "tools" / "foil_arithmetic_rule_bank.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        forbidden_imports = {
            "asyncio",
            "http",
            "importlib",
            "os",
            "requests",
            "socket",
            "subprocess",
            "urllib",
        }
        imported = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertFalse(imported & forbidden_imports)
        self.assertFalse(called & {"__import__", "compile", "eval", "exec", "open"})


class VerifierAndAdmissionTests(unittest.TestCase):
    def test_certified_verifier_is_closed_bounded_and_exact(self) -> None:
        passed = DEFAULT_REGISTRY.run(
            "builtin.certified_arithmetic_equality",
            {"left_expression": "2**12", "right_expression": "4096"},
        )
        failed = DEFAULT_REGISTRY.run(
            "builtin.certified_arithmetic_equality",
            {"left_expression": "2**3", "right_expression": "9"},
        )
        unsupported = DEFAULT_REGISTRY.run(
            "builtin.certified_arithmetic_equality",
            {"left_expression": "2**13", "right_expression": "8192"},
        )
        leaked = DEFAULT_REGISTRY.run(
            "builtin.certified_arithmetic_equality",
            {
                "left_expression": "2+2",
                "right_expression": "4",
                "gold": "4",
            },
        )
        self.assertIs(passed.status, VerificationStatus.PASS)
        self.assertIs(failed.status, VerificationStatus.FAIL)
        self.assertIs(unsupported.status, VerificationStatus.UNKNOWN)
        self.assertIs(leaked.status, VerificationStatus.UNKNOWN)

    def test_trace_verifier_reports_only_joint_consistency(self) -> None:
        data = {
            "variable": "B",
            "constraints": [
                {"coefficient": "6/1", "constant": "-30/1"},
                {"coefficient": "1/1", "constant": "-4/1"},
            ],
        }
        result = DEFAULT_REGISTRY.run("builtin.trace_constraint_consistency", data)
        self.assertIs(result.status, VerificationStatus.FAIL)
        self.assertEqual(result.reason, "trace constraints are jointly inconsistent")
        oversized = {
            "variable": "B",
            "constraints": [
                {"coefficient": "9" * 129 + "/1", "constant": "0/1"},
                {"coefficient": "1/1", "constant": "-4/1"},
            ],
        }
        self.assertIs(
            DEFAULT_REGISTRY.run(
                "builtin.trace_constraint_consistency",
                oversized,
            ).status,
            VerificationStatus.UNKNOWN,
        )

    def test_admission_bridge_accepts_known_envelope_but_cannot_be_bypassed(self) -> None:
        envelope = _envelope(r"\[2^3=8\]")
        binding = _binding(envelope)
        receipt = _receipt(envelope, binding)
        admitted = compile_admitted_discovery(
            envelope,
            admission=receipt,
            binding=binding,
        )
        self.assertEqual(
            admitted.compiled.source_spec_digest,
            envelope.task_spec_digest,
        )
        with self.assertRaisesRegex(ValueError, "not admitted"):
            compile_admitted_discovery(
                envelope,
                admission=_receipt(
                    envelope,
                    binding,
                    status=FormalizationAdmissionStatus.STAND_DOWN,
                ),
                binding=binding,
            )
        wrong_binding = FormalizationRouteBinding(
            route_id="wrong.route",
            route_version=RULE_BANK_VERSION,
            translation_distance=TranslationDistance.EXECUTION,
            formalizer_fingerprints_sha256=("a" * 64,),
            task_regime_sha256=envelope.route_binding_digest,
            target_schema=TASK_SPEC_SCHEMA,
        )
        with self.assertRaisesRegex(ValueError, "route binding"):
            compile_admitted_discovery(
                envelope,
                admission=receipt,
                binding=wrong_binding,
            )

    def test_generated_origin_and_config_binding_remain_visible(self) -> None:
        envelope = _envelope("2+2=4")
        self.assertEqual(envelope.task_spec["config_digest"], envelope.route_binding_digest)
        self.assertEqual(envelope.origin, "GENERATED_UNADMITTED")
        self.assertEqual(digest(dict(envelope.task_spec)), envelope.task_spec_digest)


class SmallPilotTests(unittest.TestCase):
    def test_frozen_pilot_is_deterministic_and_conserves_every_case(self) -> None:
        first = pilot.build_report()
        second = pilot.build_report()
        self.assertEqual(first, second)
        self.assertEqual(first["decision"], "PASS_SYNTHETIC_INTEGRATION")
        self.assertEqual(first["counts"]["attempted"], 12)
        self.assertEqual(first["counts"]["matched"], 12)
        self.assertEqual(first["counts"]["control_false_fires"], 0)
        self.assertEqual(first["counts"]["defects_detected"], 4)
        self.assertTrue(
            first["conservation"]["attempted_equals_executed_plus_stand_down"]
        )
        self.assertTrue(all(value == 0 for value in first["cost_and_authority"].values()))
        audited = pilot_audit.verify(first)
        self.assertEqual(audited["verified_rows"], 12)

    def test_frozen_report_cannot_be_relabelled_current_after_implementation_change(self) -> None:
        report_path = (
            ROOT
            / "benchmark_runs"
            / "foil_certified_rule_bank_small_pilot"
            / "report.json"
        )
        if not report_path.is_file():
            self.skipTest("frozen small-pilot report is absent")
        import json

        with self.assertRaisesRegex(
            AssertionError, "implementation/protocol file binding"
        ):
            pilot_audit.verify(json.loads(report_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
