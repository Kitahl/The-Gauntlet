from __future__ import annotations

import ast
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import power_runtime as power  # noqa: E402
from egrt_candidate_gate import (  # noqa: E402
    AdmissionState,
    CandidateBinding,
    CheckStatus,
    SemanticVerification,
    StructuralCertificate,
)
from egrt_types import Verdict  # noqa: E402


def init_root(path: Path) -> None:
    (path / ".gauntlet.json").write_text(
        json.dumps({"state_dir": ".egrt/state", "runtime": {"enabled": True}}),
        encoding="utf-8",
    )


def hash_of(char: str) -> str:
    return char * 64


class PowerVNextTests(unittest.TestCase):
    def _source(self, root: Path, name: str, *, valid: bool = True) -> Path:
        path = root / name
        path.write_text("value = 1\n" if valid else "def broken(:\n", encoding="utf-8")
        return path

    def _entrypoint(self, root: Path, name: str = "entrypoint.py") -> Path:
        path = root / name
        path.write_text("raise SystemExit(0)\n", encoding="utf-8")
        return path

    def _hypothesis(
        self,
        *,
        hypothesis_id: str = "hyp-1",
        task_id: str = "task-1",
        obligation_id: str = "obl-1",
        plan_id: str = "plan-1",
        failure_class: str = "wrong-result",
        trigger: str = "candidate is exercised",
        expected_symptom: str = "observable mismatch",
        refuter: str = "named executable check clears",
        load_bearing: bool = True,
        candidate_hash: str | None = None,
        scope_hash: str | None = None,
        metadata: dict | None = None,
    ) -> power.FailureHypothesis:
        return power.FailureHypothesis(
            hypothesis_id=hypothesis_id,
            task_id=task_id,
            obligation_id=obligation_id,
            plan_id=plan_id,
            candidate_hash=candidate_hash,
            scope_hash=scope_hash,
            failure_class=failure_class,
            trigger=trigger,
            expected_symptom=expected_symptom,
            refuter=refuter,
            load_bearing=load_bearing,
            metadata=metadata or {},
        )

    def _check(
        self,
        path: Path,
        *,
        check_id: str,
        check_type: power.VerificationCheckType,
        hypothesis_id: str = "hyp-1",
        failure_class: str = "wrong-result",
        expected_exit: int = 0,
        mandatory: bool = True,
        applicable: bool = True,
        applicability_reason: str | None = None,
        entrypoint: str | None = None,
        suspected_origin: power.DefectOrigin = power.DefectOrigin.UNKNOWN,
        discriminator_success_exit: int | None = None,
        metadata: dict | None = None,
        kind: str = "compileall",
        command: tuple[str, ...] | None = None,
        oracle: str = "process exit matches the declared oracle",
    ) -> power.VerificationCheck:
        return power.VerificationCheck(
            check_id=check_id,
            kind=kind,
            command=command
            if command is not None
            else (sys.executable, "-m", "compileall", "-q", str(path)),
            expected_exit=expected_exit,
            mandatory=mandatory,
            defect_classes=(failure_class,),
            metadata=metadata or {},
            check_type=check_type,
            failure_hypothesis_id=hypothesis_id,
            failure_class=failure_class,
            oracle=oracle,
            expected_invariant="the declared software invariant holds",
            expected_support_signal="check exits at the discriminator success code",
            expected_failure_signal="check exits at a different code",
            applicable=applicable,
            applicability_reason=applicability_reason,
            entrypoint=entrypoint,
            suspected_origin=suspected_origin,
            discriminator_success_exit=discriminator_success_exit,
        )

    def _plan(
        self,
        checks: tuple[power.VerificationCheck, ...],
        hypotheses: tuple[power.FailureHypothesis, ...],
        **kwargs,
    ) -> power.VerificationPlan:
        return power.VerificationPlan(
            plan_id="plan-1",
            obligation_id="obl-1",
            system_boundary="bounded test system",
            claim="implementation satisfies the named invariants",
            invariants=("output is stable",),
            checks=checks,
            task_id="task-1",
            failure_hypotheses=hypotheses,
            **kwargs,
        )

    def test_failure_hypothesis_binding_fails_closed(self) -> None:
        hypothesis = self._hypothesis(
            candidate_hash=hash_of("a"), scope_hash=hash_of("b")
        )
        plan = power.VerificationPlan(
            "plan-1",
            "obl-1",
            "system",
            "claim",
            (),
            (),
            task_id="task-other",
            candidate_hash=hash_of("a"),
            scope_hash=hash_of("b"),
            failure_hypotheses=(hypothesis,),
        )
        with self.assertRaisesRegex(ValueError, "task_id binding mismatch"):
            power.validate_plan(plan)

    def test_hypothesis_metadata_content_binding_detects_mutation(self) -> None:
        hypothesis = self._hypothesis(metadata={"seed": 7})
        hypothesis.metadata["seed"] = 9
        plan = self._plan((), (hypothesis,))
        with self.assertRaisesRegex(ValueError, "content binding changed"):
            power.validate_plan(plan)

    def test_duplicate_semantic_hypotheses_do_not_consume_rounds(self) -> None:
        first = self._hypothesis(hypothesis_id="hyp-a")
        second = self._hypothesis(hypothesis_id="hyp-b")
        plan = self._plan((), (first, second))
        with self.assertRaisesRegex(ValueError, "duplicate semantically identical"):
            power.validate_plan(plan)

    def test_direct_targeted_check_is_claim_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            source = self._source(root, "target.py")
            hypothesis = self._hypothesis()
            check = self._check(
                source,
                check_id="direct",
                check_type=power.VerificationCheckType.DIRECT_TARGETED,
            )
            receipt, result = power.run_plan(root, self._plan((check,), (hypothesis,)))
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(result["checks"][0]["check_type"], "DIRECT_TARGETED")
            self.assertEqual(result["hypotheses"][0]["evaluated_status"], "REFUTED")

    def test_regression_check_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            source = self._source(root, "regression.py")
            hypothesis = self._hypothesis()
            check = self._check(
                source,
                check_id="regression",
                check_type=power.VerificationCheckType.REGRESSION,
            )
            _, result = power.run_plan(root, self._plan((check,), (hypothesis,)))
            self.assertEqual(result["checks"][0]["check_type"], "REGRESSION")
            self.assertEqual(result["verdict"], Verdict.CLEARED.value)

    def test_real_entrypoint_required_when_relevant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root, "target.py")
            hypothesis = self._hypothesis()
            direct = self._check(
                source,
                check_id="direct",
                check_type=power.VerificationCheckType.DIRECT_TARGETED,
            )
            regression = self._check(
                source,
                check_id="regression",
                check_type=power.VerificationCheckType.REGRESSION,
            )
            metamorphic = self._check(
                source,
                check_id="metamorphic",
                check_type=power.VerificationCheckType.METAMORPHIC,
                metadata={
                    "relation_id": "round-trip",
                    "input_transform": "serialize then deserialize",
                    "expected_output_relation": "identity",
                    "applicable_scope": "target.py",
                },
            )
            plan = self._plan(
                (direct, regression, metamorphic),
                (hypothesis,),
                substantial_change=True,
                actual_entrypoint="python entrypoint.py",
                entrypoint_applicable=True,
                residual_failure_classes=("cross-process-race",),
            )
            with self.assertRaisesRegex(ValueError, "real entrypoint check"):
                power.validate_plan(plan)

    def test_real_entrypoint_not_applicable_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            source = self._source(root, "target.py")
            hypothesis = self._hypothesis()
            direct = self._check(
                source,
                check_id="direct",
                check_type=power.VerificationCheckType.DIRECT_TARGETED,
            )
            regression = self._check(
                source,
                check_id="regression",
                check_type=power.VerificationCheckType.REGRESSION,
            )
            relation = self._check(
                source,
                check_id="relation",
                check_type=power.VerificationCheckType.METAMORPHIC,
                metadata={
                    "relation_id": "encoding-equivalence",
                    "input_transform": "equivalent encoding",
                    "expected_output_relation": "same outcome",
                    "applicable_scope": "target.py",
                },
            )
            not_applicable = self._check(
                source,
                check_id="entrypoint-na",
                check_type=power.VerificationCheckType.REAL_ENTRYPOINT,
                command=(),
                mandatory=False,
                applicable=False,
                applicability_reason="library-only change has no executable entrypoint",
            )
            plan = self._plan(
                (direct, regression, relation, not_applicable),
                (hypothesis,),
                substantial_change=True,
                entrypoint_applicable=False,
                entrypoint_reason="library-only change has no executable entrypoint",
                residual_failure_classes=("foreign-runtime-loader",),
            )
            receipt, result = power.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(result["checks"][-1]["check_status"], "NOT_APPLICABLE")
            self.assertFalse(
                result["substantial_change_requirements"]["real_entrypoint"]["applicable"]
            )

    def test_real_python_entrypoint_is_bound_and_executed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            entry = self._entrypoint(root)
            hypothesis = self._hypothesis()
            label = f"python {entry.name}"
            check = self._check(
                entry,
                check_id="entrypoint",
                check_type=power.VerificationCheckType.REAL_ENTRYPOINT,
                kind="python-script",
                command=(sys.executable, str(entry)),
                entrypoint=label,
            )
            plan = self._plan(
                (check,),
                (hypothesis,),
                actual_entrypoint=label,
                entrypoint_applicable=True,
            )
            receipt, result = power.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(result["checks"][0]["entrypoint"], label)

    def test_metamorphic_relation_pass_proves_only_named_relation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            source = self._source(root, "relation.py")
            hypothesis = self._hypothesis()
            check = self._check(
                source,
                check_id="metamorphic",
                check_type=power.VerificationCheckType.METAMORPHIC,
                metadata={
                    "relation_id": "permutation-invariance",
                    "input_transform": "permute inputs",
                    "expected_output_relation": "same normalized output",
                    "applicable_scope": "relation.py",
                },
            )
            receipt, result = power.run_plan(root, self._plan((check,), (hypothesis,)))
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            row = result["checks"][0]
            self.assertEqual(row["relation_outcome"], "HOLDS")
            self.assertEqual(row["relation_id"], "permutation-invariance")
            self.assertIn("Only named checks", result["coverage_boundary"])

    def test_metamorphic_relation_failure_is_issue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            source = self._source(root, "bad_relation.py", valid=False)
            hypothesis = self._hypothesis()
            check = self._check(
                source,
                check_id="metamorphic",
                check_type=power.VerificationCheckType.METAMORPHIC,
                metadata={
                    "relation_id": "round-trip",
                    "input_transform": "encode then decode",
                    "expected_output_relation": "identity",
                    "applicable_scope": "bad_relation.py",
                },
            )
            receipt, result = power.run_plan(root, self._plan((check,), (hypothesis,)))
            self.assertEqual(receipt.verdict, Verdict.ISSUE)
            self.assertEqual(result["checks"][0]["relation_outcome"], "VIOLATED")
            self.assertEqual(result["hypotheses"][0]["evaluated_status"], "SUPPORTED")

    def test_mutation_killed_demonstrates_discriminator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            mutant = self._source(root, "mutant.py", valid=False)
            hypothesis = self._hypothesis()
            check = self._check(
                mutant,
                check_id="mutation",
                check_type=power.VerificationCheckType.MUTATION,
                discriminator_success_exit=1,
            )
            receipt, result = power.run_plan(root, self._plan((check,), (hypothesis,)))
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(result["checks"][0]["discriminator_outcome"], "KILLED")

    def test_mutation_survives_and_blocks_fixed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            mutant = self._source(root, "surviving_mutant.py", valid=True)
            hypothesis = self._hypothesis()
            check = self._check(
                mutant,
                check_id="mutation",
                check_type=power.VerificationCheckType.MUTATION,
                discriminator_success_exit=1,
            )
            receipt, result = power.run_plan(root, self._plan((check,), (hypothesis,)))
            self.assertEqual(receipt.verdict, Verdict.ISSUE)
            self.assertEqual(result["checks"][0]["discriminator_outcome"], "SURVIVED")
            self.assertFalse(result["repair_promotion_authorized"])

    def test_negative_control_cannot_reuse_normal_success_exit_silently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root, "control.py")
            hypothesis = self._hypothesis()
            check = self._check(
                source,
                check_id="negative",
                check_type=power.VerificationCheckType.NEGATIVE_CONTROL,
                discriminator_success_exit=0,
            )
            with self.assertRaisesRegex(ValueError, "cannot share the normal success"):
                power.validate_plan(self._plan((check,), (hypothesis,)))

    def test_property_generated_case_is_bound_to_named_failure_class(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root, "property_case.py")
            hypothesis = self._hypothesis(failure_class="boundary-overflow")
            check = self._check(
                source,
                check_id="property",
                check_type=power.VerificationCheckType.PROPERTY_GENERATED,
                failure_class="wrong-result",
            )
            with self.assertRaisesRegex(ValueError, "failure_class binding mismatch"):
                power.validate_plan(self._plan((check,), (hypothesis,)))

    def test_differential_verification_executes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            source = self._source(root, "differential.py")
            hypothesis = self._hypothesis(failure_class="implementation-divergence")
            check = self._check(
                source,
                check_id="differential",
                check_type=power.VerificationCheckType.DIFFERENTIAL,
                failure_class="implementation-divergence",
                oracle="reference and candidate implementations agree",
            )
            receipt, result = power.run_plan(root, self._plan((check,), (hypothesis,)))
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(result["checks"][0]["check_type"], "DIFFERENTIAL")

    def test_environment_integration_mismatch_is_issue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            source = self._source(root, "environment.py", valid=False)
            hypothesis = self._hypothesis(failure_class="environment-mismatch")
            check = self._check(
                source,
                check_id="environment",
                check_type=power.VerificationCheckType.ENVIRONMENT_INTEGRATION,
                failure_class="environment-mismatch",
                suspected_origin=power.DefectOrigin.TOOL_ENVIRONMENT,
                metadata={"attribution_discriminator": "reproduce under frozen runtime"},
            )
            receipt, result = power.run_plan(root, self._plan((check,), (hypothesis,)))
            self.assertEqual(receipt.verdict, Verdict.ISSUE)
            self.assertEqual(
                result["checks"][0]["suspected_origin"], "TOOL_ENVIRONMENT"
            )

    def test_missing_mandatory_tool_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            check = power.VerificationCheck("missing", "z3", ("z3",), mandatory=True)
            plan = power.VerificationPlan("p", "o", "s", "c", (), (check,))
            with patch.object(power.shutil, "which", return_value=None):
                receipt, result = power.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.UNAVAILABLE)
            self.assertEqual(result["checks"][0]["check_status"], "UNAVAILABLE")

    def test_artifact_and_harness_defect_candidates_remain_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            source = self._source(root, "origin.py")
            artifact_hypothesis = self._hypothesis(
                hypothesis_id="hyp-artifact",
                failure_class="artifact-defect",
                trigger="artifact path executes",
                expected_symptom="artifact output is wrong",
            )
            harness_hypothesis = self._hypothesis(
                hypothesis_id="hyp-harness",
                failure_class="harness-defect",
                trigger="harness path executes",
                expected_symptom="harness misreports output",
            )
            artifact = self._check(
                source,
                check_id="artifact",
                check_type=power.VerificationCheckType.DIRECT_TARGETED,
                hypothesis_id="hyp-artifact",
                failure_class="artifact-defect",
                suspected_origin=power.DefectOrigin.TASK_ARTIFACT,
                metadata={"attribution_discriminator": "run artifact outside harness"},
            )
            harness = self._check(
                source,
                check_id="harness",
                check_type=power.VerificationCheckType.ENVIRONMENT_INTEGRATION,
                hypothesis_id="hyp-harness",
                failure_class="harness-defect",
                suspected_origin=power.DefectOrigin.AGENT_HARNESS,
                metadata={"attribution_discriminator": "swap harness, hold artifact fixed"},
            )
            _, result = power.run_plan(
                root,
                self._plan(
                    (artifact, harness), (artifact_hypothesis, harness_hypothesis)
                ),
            )
            self.assertEqual(result["checks"][0]["suspected_origin"], "TASK_ARTIFACT")
            self.assertEqual(result["checks"][1]["suspected_origin"], "AGENT_HARNESS")
            self.assertEqual(result["checks"][0]["attribution_status"], "DISCRIMINATOR_DECLARED")

    def test_changed_harness_or_oracle_changes_evidence_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root, "identity.py")
            left = power.VerificationCheck(
                "identity",
                "compileall",
                (sys.executable, "-m", "compileall", "-q", str(source)),
                oracle="oracle-a",
            )
            right = power.VerificationCheck(
                "identity",
                "compileall",
                (sys.executable, "-m", "compileall", "-q", str(source)),
                oracle="oracle-b",
            )
            left_result = power.run_check(root, left)
            right_result = power.run_check(root, right)
            self.assertNotEqual(
                left_result["check_evidence_identity"],
                right_result["check_evidence_identity"],
            )

    def test_repair_self_certification_is_rejected(self) -> None:
        candidate = CandidateBinding(
            "candidate",
            hash_of("a"),
            hash_of("b"),
            hash_of("c"),
            hash_of("d"),
            "repair-producer",
            "1",
        )
        structural = StructuralCertificate(
            hash_of("a"),
            hash_of("b"),
            hash_of("c"),
            hash_of("d"),
            "repair-producer",
            "1",
            hash_of("e"),
            CheckStatus.PASS,
        )
        decision = power.verify_repair_candidate(candidate, structural)
        self.assertEqual(decision.state, AdmissionState.REJECTED)
        self.assertEqual(decision.reason, "repair_producer_self_certified")
        self.assertFalse(decision.execution_authorized)

    def test_repair_dual_verifier_binding_never_authorizes_execution(self) -> None:
        candidate = CandidateBinding(
            "candidate",
            hash_of("a"),
            hash_of("b"),
            hash_of("c"),
            hash_of("d"),
            "repair-producer",
            "1",
        )
        structural = StructuralCertificate(
            hash_of("a"),
            hash_of("b"),
            hash_of("c"),
            hash_of("d"),
            "structural-verifier",
            "1",
            hash_of("e"),
            CheckStatus.PASS,
        )
        semantic = SemanticVerification(
            hash_of("a"),
            hash_of("b"),
            hash_of("c"),
            hash_of("d"),
            "semantic-verifier",
            "1",
            hash_of("e"),
            CheckStatus.PASS,
        )
        decision = power.verify_repair_candidate(candidate, structural, semantic)
        self.assertEqual(decision.state, AdmissionState.COMMITTABLE)
        self.assertFalse(decision.execution_authorized)
        self.assertTrue(decision.host_commit_required)

    def test_shell_escape_remains_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            check = power.VerificationCheck(
                "escape",
                "python-unittest",
                (sys.executable, "-m", "unittest", "-c"),
            )
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("EGR_POWER_ALLOW_CUSTOM_COMMANDS", None)
                result = power.run_check(root, check)
            self.assertEqual(result["verdict"], Verdict.UNAVAILABLE.value)
            self.assertIn("disallowed flag", result["reason"])

    def test_untrusted_executable_remains_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "z3"
            fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            if os.name != "nt":
                fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            check = power.VerificationCheck("untrusted", "z3", (str(fake),))
            with patch.object(power.shutil, "which", return_value=None):
                result = power.run_check(root, check)
            self.assertEqual(result["verdict"], Verdict.UNAVAILABLE.value)
            self.assertIn("tool not found on PATH", result["reason"])

    def test_timeout_remains_check_scoped_and_hashes_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root, "timeout.py")
            check = power.VerificationCheck(
                "timeout",
                "compileall",
                (sys.executable, "-m", "compileall", "-q", str(source)),
                timeout_seconds=3,
            )
            error = subprocess.TimeoutExpired(
                cmd=list(check.command), timeout=3, output=b"partial", stderr=b"error"
            )
            with patch.object(power.subprocess, "run", side_effect=error) as mocked:
                result = power.run_check(root, check)
            self.assertEqual(result["verdict"], Verdict.UNKNOWN.value)
            self.assertEqual(result["reason"], "timeout")
            self.assertIn("stdout_hash", result)
            self.assertEqual(mocked.call_args.kwargs["timeout"], 3)
            self.assertFalse(mocked.call_args.kwargs["shell"])

    def test_historical_power_receipt_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            source = self._source(root, "legacy.py")
            check = power.VerificationCheck(
                "legacy",
                "compileall",
                (sys.executable, "-m", "compileall", "-q", str(source)),
                defect_classes=("syntax-regression",),
            )
            plan = power.VerificationPlan(
                "legacy-plan", "legacy-obligation", "system", "claim", (), (check,)
            )
            receipt, result = power.run_plan(root, plan)
            self.assertEqual(receipt.module, "power")
            self.assertEqual(receipt.action, "verification-plan")
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(result["coverage"]["legacy"], ["syntax-regression"])

    def test_no_non_foil_import_of_foil_modules(self) -> None:
        source = (ROOT / "tools" / "power_runtime.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        self.assertFalse(
            [name for name in imported if name == "foil" or name.startswith("foil_")]
        )

    def test_local_typed_repair_requires_all_three_guards(self) -> None:
        self.assertEqual(
            power.select_repair_strategy(
                fault_localized=True,
                invariants_known=True,
                independently_verifiable=True,
            ),
            power.RepairStrategy.LOCAL_TYPED,
        )
        self.assertEqual(
            power.select_repair_strategy(
                fault_localized=True,
                invariants_known=False,
                independently_verifiable=True,
            ),
            power.RepairStrategy.DEFER_OR_BROADER_REVIEW,
        )


if __name__ == "__main__":
    unittest.main()
