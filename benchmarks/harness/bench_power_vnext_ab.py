from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
FIXTURE = ROOT / "benchmarks" / "fixtures" / "power_runtime_space_base.py"
sys.path.insert(0, str(TOOLS))

import power_runtime as new_power  # noqa: E402
from egrt_candidate_gate import (  # noqa: E402
    AdmissionState,
    CandidateBinding,
    CheckStatus,
    SemanticVerification,
    StructuralCertificate,
)

OLD_RUNTIME_BLOB = "5b2c0e6f06df99bac77973f70485cd3c465729e4"
NEW_RUNTIME_BLOB = "99f5b955b782b61ccaa5fa481ecd347963c3a35a"
OLD_REVISION = "01c07faf1848284bda3c13d1c1eec972629be9c4"
NEW_REVISION = "b8e6557253a642ccc85d27a22c79241256eb3f9b"


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def _load_old_power() -> Any:
    spec = importlib.util.spec_from_file_location("power_runtime_space_base", FIXTURE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load pinned Space-base Power fixture")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _init_root(root: Path) -> None:
    (root / ".gauntlet.json").write_text(
        json.dumps({"state_dir": ".egrt/state", "runtime": {"enabled": True}}),
        encoding="utf-8",
    )


def _source(root: Path, name: str, *, valid: bool = True) -> Path:
    path = root / name
    path.write_text("value = 1\n" if valid else "def broken(:\n", encoding="utf-8")
    return path


def _legacy_check(mod: Any, path: Path, *, check_id: str, valid_kind: str = "compileall") -> Any:
    if valid_kind == "compileall":
        command = (sys.executable, "-m", "compileall", "-q", str(path))
    else:
        command = (valid_kind,)
    return mod.VerificationCheck(check_id, valid_kind, command)


def _legacy_plan(mod: Any, checks: tuple[Any, ...]) -> Any:
    return mod.VerificationPlan(
        "bench-plan",
        "bench-obligation",
        "bench-system",
        "bench-claim",
        ("bench-invariant",),
        checks,
    )


def _case(name: str, family: str, old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    return {"case": name, "family": family, "old": old, "new": new}


def _obs(passed: bool, observed: Any, expected: Any) -> dict[str, Any]:
    return {"pass": bool(passed), "observed": observed, "expected": expected}


def _run_pair(fn: Callable[[Any], dict[str, Any]], old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    return fn(old_power), fn(new_power)


def _shared_clean_compile(mod: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = _source(root, "clean.py")
        result = mod.run_check(root, _legacy_check(mod, src, check_id="clean"))
        return _obs(result["verdict"] == "CLEARED", result["verdict"], "CLEARED")


def _shared_syntax_failure(mod: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = _source(root, "broken.py", valid=False)
        result = mod.run_check(root, _legacy_check(mod, src, check_id="broken"))
        return _obs(result["verdict"] == "ISSUE", result["verdict"], "ISSUE")


def _shared_custom_disabled(mod: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {}, clear=False):
        os.environ.pop("EGR_POWER_ALLOW_CUSTOM_COMMANDS", None)
        root = Path(d)
        check = mod.VerificationCheck("custom", "custom", ("echo", "hello"))
        result = mod.run_check(root, check)
        return _obs(result["verdict"] == "UNAVAILABLE", result["verdict"], "UNAVAILABLE")


def _shared_blocked_module_flag(mod: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {}, clear=False):
        os.environ.pop("EGR_POWER_ALLOW_CUSTOM_COMMANDS", None)
        root = Path(d)
        check = mod.VerificationCheck(
            "blocked-flag",
            "python-unittest",
            (sys.executable, "-m", "unittest", "-c"),
        )
        result = mod.run_check(root, check)
        return _obs(
            result["verdict"] == "UNAVAILABLE" and "disallowed flag" in result.get("reason", ""),
            {"verdict": result["verdict"], "reason": result.get("reason")},
            "UNAVAILABLE/disallowed flag",
        )


def _shared_arbitrary_module_refused(mod: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {}, clear=False):
        os.environ.pop("EGR_POWER_ALLOW_CUSTOM_COMMANDS", None)
        root = Path(d)
        check = mod.VerificationCheck(
            "arbitrary-module",
            "python-unittest",
            (sys.executable, "-m", "unittest", "definitely_not_a_path_or_test_file"),
        )
        result = mod.run_check(root, check)
        return _obs(
            result["verdict"] == "UNAVAILABLE" and "arbitrary module names" in result.get("reason", ""),
            {"verdict": result["verdict"], "reason": result.get("reason")},
            "UNAVAILABLE/arbitrary module names refused",
        )


def _shared_missing_tool(mod: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        check = mod.VerificationCheck("missing-z3", "z3", ("z3",))
        with patch.object(mod.shutil, "which", return_value=None):
            result = mod.run_check(root, check)
        return _obs(result["verdict"] == "UNAVAILABLE", result["verdict"], "UNAVAILABLE")


def _shared_untrusted_executable(mod: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        fake = root / "z3"
        fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        if os.name != "nt":
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        check = mod.VerificationCheck("fake-z3", "z3", (str(fake),))
        with patch.object(mod.shutil, "which", return_value=None):
            result = mod.run_check(root, check)
        return _obs(
            result["verdict"] == "UNAVAILABLE",
            {"verdict": result["verdict"], "reason": result.get("reason")},
            "UNAVAILABLE",
        )


def _shared_timeout(mod: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = _source(root, "slow.py")
        check = _legacy_check(mod, src, check_id="timeout")
        error = subprocess.TimeoutExpired(
            cmd=list(check.command), timeout=check.timeout_seconds, output=b"partial", stderr=b"error"
        )
        with patch.object(mod.subprocess, "run", side_effect=error):
            result = mod.run_check(root, check)
        passed = (
            result["verdict"] == "UNKNOWN"
            and result.get("reason") == "timeout"
            and bool(result.get("stdout_hash"))
            and bool(result.get("stderr_hash"))
        )
        return _obs(
            passed,
            {k: result.get(k) for k in ("verdict", "reason", "stdout_hash", "stderr_hash")},
            "UNKNOWN timeout with hashed partial output",
        )


def _shared_issue_dominates_unavailable(mod: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _init_root(root)
        broken = _source(root, "broken.py", valid=False)
        checks = (
            _legacy_check(mod, broken, check_id="issue"),
            mod.VerificationCheck("missing", "z3", ("z3",)),
        )
        with patch.object(mod.shutil, "which", return_value=None):
            receipt, _ = mod.run_plan(root, _legacy_plan(mod, checks))
        return _obs(receipt.verdict.value == "ISSUE", receipt.verdict.value, "ISSUE")


def _shared_unavailable_dominates_unknown(mod: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _init_root(root)
        src = _source(root, "timeout.py")
        timeout_check = _legacy_check(mod, src, check_id="timeout")
        missing = mod.VerificationCheck("missing", "z3", ("z3",))
        error = subprocess.TimeoutExpired(
            cmd=list(timeout_check.command), timeout=timeout_check.timeout_seconds
        )
        with patch.object(mod.subprocess, "run", side_effect=error), patch.object(
            mod.shutil, "which", return_value=None
        ):
            receipt, _ = mod.run_plan(root, _legacy_plan(mod, (timeout_check, missing)))
        return _obs(receipt.verdict.value == "UNAVAILABLE", receipt.verdict.value, "UNAVAILABLE")


def _new_hyp(
    failure_class: str = "wrong-result",
    *,
    hypothesis_id: str = "hyp-1",
    trigger: str = "candidate is exercised",
    symptom: str = "observable mismatch",
) -> Any:
    return new_power.FailureHypothesis(
        hypothesis_id=hypothesis_id,
        task_id="task-1",
        obligation_id="obl-1",
        plan_id="plan-1",
        failure_class=failure_class,
        trigger=trigger,
        expected_symptom=symptom,
        refuter="named executable discriminator clears",
        load_bearing=True,
    )


def _new_check(
    path: Path,
    *,
    check_id: str,
    check_type: Any,
    hypothesis_id: str = "hyp-1",
    failure_class: str = "wrong-result",
    expected_exit: int = 0,
    discriminator_success_exit: int | None = None,
    metadata: dict[str, Any] | None = None,
    kind: str = "compileall",
    command: tuple[str, ...] | None = None,
    entrypoint: str | None = None,
    suspected_origin: Any = None,
) -> Any:
    return new_power.VerificationCheck(
        check_id=check_id,
        kind=kind,
        command=command or (sys.executable, "-m", "compileall", "-q", str(path)),
        expected_exit=expected_exit,
        mandatory=True,
        defect_classes=(failure_class,),
        metadata=metadata or {},
        check_type=check_type,
        failure_hypothesis_id=hypothesis_id,
        failure_class=failure_class,
        oracle="process exit matches the frozen oracle",
        expected_invariant="the named invariant holds",
        expected_support_signal="the discriminator supports the hypothesis",
        expected_failure_signal="the discriminator refutes the hypothesis",
        entrypoint=entrypoint,
        suspected_origin=(
            new_power.DefectOrigin.UNKNOWN if suspected_origin is None else suspected_origin
        ),
        discriminator_success_exit=discriminator_success_exit,
    )


def _new_plan(
    checks: tuple[Any, ...],
    hypotheses: tuple[Any, ...],
    **kwargs: Any,
) -> Any:
    return new_power.VerificationPlan(
        plan_id="plan-1",
        obligation_id="obl-1",
        system_boundary="benchmark system",
        claim="candidate satisfies named engineering invariants",
        invariants=("named invariant",),
        checks=checks,
        task_id="task-1",
        failure_hypotheses=hypotheses,
        **kwargs,
    )


def _vnext_duplicate_hypotheses(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    old = _obs(False, hasattr(old_power, "FailureHypothesis"), "duplicate semantic hypotheses rejected")
    first = _new_hyp(hypothesis_id="hyp-a")
    second = _new_hyp(hypothesis_id="hyp-b")
    try:
        new_power.validate_plan(_new_plan((), (first, second)))
        observed = "accepted"
        passed = False
    except ValueError as exc:
        observed = str(exc)
        passed = "duplicate semantically identical" in observed
    return old, _obs(passed, observed, "duplicate semantic hypotheses rejected")


def _vnext_binding_mismatch(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    old = _obs(False, hasattr(old_power, "FailureHypothesis"), "task binding mismatch rejected")
    hyp = _new_hyp()
    plan = new_power.VerificationPlan(
        "plan-1",
        "obl-1",
        "system",
        "claim",
        (),
        (),
        task_id="task-other",
        failure_hypotheses=(hyp,),
    )
    try:
        new_power.validate_plan(plan)
        observed = "accepted"
        passed = False
    except ValueError as exc:
        observed = str(exc)
        passed = "task_id binding mismatch" in observed
    return old, _obs(passed, observed, "task binding mismatch rejected")


def _vnext_substantial_minimum(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    old = _obs(False, hasattr(old_power, "validate_plan"), "missing regression rejected")
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = _source(root, "target.py")
        hyp = _new_hyp()
        direct = _new_check(
            src, check_id="direct", check_type=new_power.VerificationCheckType.DIRECT_TARGETED
        )
        relation = _new_check(
            src,
            check_id="relation",
            check_type=new_power.VerificationCheckType.METAMORPHIC,
            metadata={
                "relation_id": "identity",
                "input_transform": "identity",
                "expected_output_relation": "identity",
                "applicable_scope": "target.py",
            },
        )
        na = new_power.VerificationCheck(
            check_id="entry-na",
            kind="compileall",
            command=(),
            mandatory=False,
            check_type=new_power.VerificationCheckType.REAL_ENTRYPOINT,
            failure_hypothesis_id="hyp-1",
            failure_class="wrong-result",
            oracle="no entrypoint exists",
            expected_invariant="no runtime surface is applicable",
            expected_support_signal="not applicable",
            expected_failure_signal="unexpected runtime surface",
            applicable=False,
            applicability_reason="library-only benchmark change",
        )
        plan = _new_plan(
            (direct, relation, na),
            (hyp,),
            substantial_change=True,
            entrypoint_applicable=False,
            entrypoint_reason="library-only benchmark change",
            residual_failure_classes=("race-condition",),
        )
        try:
            new_power.validate_plan(plan)
            observed = "accepted"
            passed = False
        except ValueError as exc:
            observed = str(exc)
            passed = "regression" in observed
    return old, _obs(passed, observed, "missing regression rejected")


def _vnext_mutation_killed(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _init_root(root)
        mutant = _source(root, "mutant.py", valid=False)
        old_check = _legacy_check(old_power, mutant, check_id="mutation")
        old_receipt, _ = old_power.run_plan(root, _legacy_plan(old_power, (old_check,)))
        old = _obs(False, old_receipt.verdict.value, "KILLED discriminator clears")

        hyp = _new_hyp()
        check = _new_check(
            mutant,
            check_id="mutation",
            check_type=new_power.VerificationCheckType.MUTATION,
            discriminator_success_exit=1,
        )
        receipt, result = new_power.run_plan(root, _new_plan((check,), (hyp,)))
        row = result["checks"][0]
        new = _obs(
            receipt.verdict.value == "CLEARED" and row.get("discriminator_outcome") == "KILLED",
            {"verdict": receipt.verdict.value, "outcome": row.get("discriminator_outcome")},
            "CLEARED/KILLED",
        )
    return old, new


def _vnext_mutation_survives(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _init_root(root)
        mutant = _source(root, "survivor.py", valid=True)
        old_receipt, _ = old_power.run_plan(
            root,
            _legacy_plan(old_power, (_legacy_check(old_power, mutant, check_id="mutation"),)),
        )
        old = _obs(old_receipt.verdict.value == "ISSUE", old_receipt.verdict.value, "ISSUE/SURVIVED")

        hyp = _new_hyp()
        check = _new_check(
            mutant,
            check_id="mutation",
            check_type=new_power.VerificationCheckType.MUTATION,
            discriminator_success_exit=1,
        )
        receipt, result = new_power.run_plan(root, _new_plan((check,), (hyp,)))
        row = result["checks"][0]
        new = _obs(
            receipt.verdict.value == "ISSUE" and row.get("discriminator_outcome") == "SURVIVED",
            {"verdict": receipt.verdict.value, "outcome": row.get("discriminator_outcome")},
            "ISSUE/SURVIVED",
        )
    return old, new


def _vnext_real_entrypoint_inside(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _init_root(root)
        marker = root / "ran.txt"
        entry = root / "entry.py"
        entry.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('ran', encoding='utf-8')\n",
            encoding="utf-8",
        )
        old_check = old_power.VerificationCheck("entry", "python-script", (sys.executable, str(entry)))
        old_result = old_power.run_check(root, old_check)
        old = _obs(
            old_result["verdict"] == "CLEARED" and marker.exists(),
            {"verdict": old_result["verdict"], "executed": marker.exists()},
            "CLEARED/executed",
        )
        marker.unlink(missing_ok=True)

        label = f"python {entry.name}"
        hyp = _new_hyp()
        new_check = _new_check(
            entry,
            check_id="entry",
            check_type=new_power.VerificationCheckType.REAL_ENTRYPOINT,
            kind="python-script",
            command=(sys.executable, str(entry)),
            entrypoint=label,
        )
        receipt, _ = new_power.run_plan(
            root,
            _new_plan(
                (new_check,),
                (hyp,),
                actual_entrypoint=label,
                entrypoint_applicable=True,
            ),
        )
        new = _obs(
            receipt.verdict.value == "CLEARED" and marker.exists(),
            {"verdict": receipt.verdict.value, "executed": marker.exists()},
            "CLEARED/executed",
        )
    return old, new


def _vnext_real_entrypoint_escape(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory() as d:
        parent = Path(d)
        root = parent / "repo"
        root.mkdir()
        marker = parent / "outside-ran.txt"
        outside = parent / "outside.py"
        outside.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('ran', encoding='utf-8')\n",
            encoding="utf-8",
        )
        old_check = old_power.VerificationCheck(
            "outside", "python-script", (sys.executable, str(outside))
        )
        old_result = old_power.run_check(root, old_check)
        old_reason = old_result.get("reason", "")
        old = _obs(
            old_result["verdict"] == "UNAVAILABLE"
            and "outside the repository root" in old_reason
            and not marker.exists(),
            {"verdict": old_result["verdict"], "reason": old_reason, "executed": marker.exists()},
            "UNAVAILABLE/root-confinement/not executed",
        )
        marker.unlink(missing_ok=True)

        new_check = new_power.VerificationCheck(
            "outside", "python-script", (sys.executable, str(outside))
        )
        new_result = new_power.run_check(root, new_check)
        new_reason = new_result.get("reason", "")
        new = _obs(
            new_result["verdict"] == "UNAVAILABLE"
            and "outside the repository root" in new_reason
            and not marker.exists(),
            {"verdict": new_result["verdict"], "reason": new_reason, "executed": marker.exists()},
            "UNAVAILABLE/root-confinement/not executed",
        )
    return old, new


def _vnext_metamorphic_scope(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _init_root(root)
        broken = _source(root, "relation.py", valid=False)
        old_result = old_power.run_check(
            root, _legacy_check(old_power, broken, check_id="relation")
        )
        old = _obs(
            old_result.get("relation_outcome") == "VIOLATED",
            {"verdict": old_result["verdict"], "relation_outcome": old_result.get("relation_outcome")},
            "ISSUE/VIOLATED/named relation",
        )

        hyp = _new_hyp()
        check = _new_check(
            broken,
            check_id="relation",
            check_type=new_power.VerificationCheckType.METAMORPHIC,
            metadata={
                "relation_id": "round-trip",
                "input_transform": "encode then decode",
                "expected_output_relation": "identity",
                "applicable_scope": "relation.py",
            },
        )
        receipt, result = new_power.run_plan(root, _new_plan((check,), (hyp,)))
        row = result["checks"][0]
        new = _obs(
            receipt.verdict.value == "ISSUE"
            and row.get("relation_outcome") == "VIOLATED"
            and row.get("relation_id") == "round-trip",
            {
                "verdict": receipt.verdict.value,
                "relation_outcome": row.get("relation_outcome"),
                "relation_id": row.get("relation_id"),
            },
            "ISSUE/VIOLATED/round-trip",
        )
    return old, new


def _vnext_origin_distinction(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    old = _obs(False, hasattr(old_power, "DefectOrigin"), "TASK_ARTIFACT distinct from AGENT_HARNESS")
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _init_root(root)
        src = _source(root, "origin.py")
        h_art = _new_hyp(
            "artifact-defect",
            hypothesis_id="hyp-artifact",
            trigger="artifact executes",
            symptom="artifact output mismatch",
        )
        h_harness = _new_hyp(
            "harness-defect",
            hypothesis_id="hyp-harness",
            trigger="harness executes",
            symptom="harness misreports output",
        )
        c_art = _new_check(
            src,
            check_id="artifact",
            check_type=new_power.VerificationCheckType.DIRECT_TARGETED,
            hypothesis_id="hyp-artifact",
            failure_class="artifact-defect",
            suspected_origin=new_power.DefectOrigin.TASK_ARTIFACT,
            metadata={"attribution_discriminator": "run artifact outside harness"},
        )
        c_harness = _new_check(
            src,
            check_id="harness",
            check_type=new_power.VerificationCheckType.ENVIRONMENT_INTEGRATION,
            hypothesis_id="hyp-harness",
            failure_class="harness-defect",
            suspected_origin=new_power.DefectOrigin.AGENT_HARNESS,
            metadata={"attribution_discriminator": "swap harness, hold artifact fixed"},
        )
        receipt, result = new_power.run_plan(
            root, _new_plan((c_art, c_harness), (h_art, h_harness))
        )
        origins = [row.get("suspected_origin") for row in result["checks"]]
        new = _obs(
            receipt.verdict.value == "CLEARED"
            and origins == ["TASK_ARTIFACT", "AGENT_HARNESS"],
            {"verdict": receipt.verdict.value, "origins": origins},
            ["TASK_ARTIFACT", "AGENT_HARNESS"],
        )
    return old, new


def _vnext_oracle_identity(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = _source(root, "identity.py")
        old_left = old_power.VerificationCheck(
            "identity",
            "compileall",
            (sys.executable, "-m", "compileall", "-q", str(src)),
            metadata={"oracle": "oracle-a"},
        )
        old_right = old_power.VerificationCheck(
            "identity",
            "compileall",
            (sys.executable, "-m", "compileall", "-q", str(src)),
            metadata={"oracle": "oracle-b"},
        )
        old_a = old_power.run_check(root, old_left).get("check_evidence_identity")
        old_b = old_power.run_check(root, old_right).get("check_evidence_identity")
        old = _obs(
            bool(old_a and old_b and old_a != old_b),
            [old_a, old_b],
            "different non-null evidence identities",
        )

        common = (sys.executable, "-m", "compileall", "-q", str(src))
        new_left = new_power.VerificationCheck("identity", "compileall", common, oracle="oracle-a")
        new_right = new_power.VerificationCheck("identity", "compileall", common, oracle="oracle-b")
        new_a = new_power.run_check(root, new_left).get("check_evidence_identity")
        new_b = new_power.run_check(root, new_right).get("check_evidence_identity")
        new = _obs(
            bool(new_a and new_b and new_a != new_b),
            [new_a, new_b],
            "different non-null evidence identities",
        )
    return old, new


def _h(char: str) -> str:
    return char * 64


def _vnext_self_certification(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    old = _obs(False, hasattr(old_power, "verify_repair_candidate"), "REJECTED/self-certification")
    candidate = CandidateBinding("candidate", _h("a"), _h("b"), _h("c"), _h("d"), "producer", "1")
    structural = StructuralCertificate(
        _h("a"), _h("b"), _h("c"), _h("d"), "producer", "1", _h("e"), CheckStatus.PASS
    )
    decision = new_power.verify_repair_candidate(candidate, structural)
    new = _obs(
        decision.state is AdmissionState.REJECTED
        and decision.reason == "repair_producer_self_certified"
        and not decision.execution_authorized,
        {
            "state": decision.state.value,
            "reason": decision.reason,
            "execution_authorized": decision.execution_authorized,
        },
        "REJECTED/repair_producer_self_certified/execution_authorized=false",
    )
    return old, new


def _vnext_dual_verifier(old_power: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    old = _obs(
        False,
        hasattr(old_power, "verify_repair_candidate"),
        "COMMITTABLE but execution_authorized=false",
    )
    candidate = CandidateBinding("candidate", _h("a"), _h("b"), _h("c"), _h("d"), "producer", "1")
    structural = StructuralCertificate(
        _h("a"), _h("b"), _h("c"), _h("d"), "structural", "1", _h("e"), CheckStatus.PASS
    )
    semantic = SemanticVerification(
        _h("a"), _h("b"), _h("c"), _h("d"), "semantic", "1", _h("e"), CheckStatus.PASS
    )
    decision = new_power.verify_repair_candidate(candidate, structural, semantic)
    new = _obs(
        decision.state is AdmissionState.COMMITTABLE
        and not decision.execution_authorized
        and decision.host_commit_required,
        {
            "state": decision.state.value,
            "execution_authorized": decision.execution_authorized,
            "host_commit_required": decision.host_commit_required,
        },
        "COMMITTABLE/execution_authorized=false/host_commit_required=true",
    )
    return old, new


def run_benchmark() -> dict[str, Any]:
    old_blob = _git_blob_sha(FIXTURE)
    new_blob = _git_blob_sha(TOOLS / "power_runtime.py")
    if old_blob != OLD_RUNTIME_BLOB:
        raise RuntimeError(f"old runtime fixture drift: {old_blob}")
    if new_blob != NEW_RUNTIME_BLOB:
        raise RuntimeError(f"new runtime drift: {new_blob}")
    old_power = _load_old_power()

    cases: list[dict[str, Any]] = []
    shared = [
        ("shared.clean_compile", _shared_clean_compile),
        ("shared.syntax_failure", _shared_syntax_failure),
        ("shared.custom_disabled", _shared_custom_disabled),
        ("shared.blocked_module_flag", _shared_blocked_module_flag),
        ("shared.arbitrary_module_refused", _shared_arbitrary_module_refused),
        ("shared.missing_tool", _shared_missing_tool),
        ("shared.untrusted_executable", _shared_untrusted_executable),
        ("shared.timeout", _shared_timeout),
        ("shared.issue_dominates_unavailable", _shared_issue_dominates_unavailable),
        ("shared.unavailable_dominates_unknown", _shared_unavailable_dominates_unknown),
    ]
    for name, fn in shared:
        old, new = _run_pair(fn, old_power)
        cases.append(_case(name, "shared", old, new))

    vnext = [
        ("vnext.duplicate_semantic_hypotheses", _vnext_duplicate_hypotheses),
        ("vnext.binding_mismatch", _vnext_binding_mismatch),
        ("vnext.substantial_change_minimum", _vnext_substantial_minimum),
        ("vnext.mutation_killed", _vnext_mutation_killed),
        ("vnext.mutation_survives", _vnext_mutation_survives),
        ("vnext.real_entrypoint_inside_root", _vnext_real_entrypoint_inside),
        ("vnext.real_entrypoint_escape", _vnext_real_entrypoint_escape),
        ("vnext.metamorphic_relation_scope", _vnext_metamorphic_scope),
        ("vnext.defect_origin_distinction", _vnext_origin_distinction),
        ("vnext.oracle_changes_evidence_identity", _vnext_oracle_identity),
        ("vnext.self_certification_rejected", _vnext_self_certification),
        ("vnext.dual_verifier_host_control", _vnext_dual_verifier),
    ]
    for name, fn in vnext:
        old, new = fn(old_power)
        cases.append(_case(name, "vnext", old, new))

    def score(version: str, family: str | None = None) -> dict[str, int]:
        selected = [c for c in cases if family is None or c["family"] == family]
        passed = sum(1 for c in selected if c[version]["pass"])
        return {"passed": passed, "total": len(selected)}

    old_total = score("old")
    new_total = score("new")
    result = {
        "schema": "power-vnext-ab.v1",
        "benchmark_kind": "deterministic mechanism-conformance and adversarial-discrimination",
        "old": {
            "revision": OLD_REVISION,
            "runtime_blob": old_blob,
            "shared": score("old", "shared"),
            "vnext": score("old", "vnext"),
            "total": old_total,
        },
        "new": {
            "revision": NEW_REVISION,
            "runtime_blob": new_blob,
            "shared": score("new", "shared"),
            "vnext": score("new", "vnext"),
            "total": new_total,
        },
        "delta_passes": new_total["passed"] - old_total["passed"],
        "cases": cases,
        "claim_boundary": (
            "This benchmark measures only the frozen mechanical cases named here. "
            "It is not a benchmark of general software correctness, repair efficacy, "
            "or production reliability."
        ),
    }
    return result


def main() -> int:
    result = run_benchmark()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["new"]["total"]["passed"] == result["new"]["total"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
