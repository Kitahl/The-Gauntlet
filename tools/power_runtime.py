"""Claim-scoped Engineering Verification with typed adversarial evidence.

Power executes frozen verification plans.  It never uses a shell, never treats prose
as executable evidence, and never promotes a repair candidate.  Known verifier
families retain constrained command shapes; custom commands remain disabled unless the
outer execution environment explicitly opts in with
``EGR_POWER_ALLOW_CUSTOM_COMMANDS=1``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from egrt_candidate_gate import (
    AdmissionDecision,
    CandidateBinding,
    CandidateRepair,
    SemanticVerification,
    StructuralCertificate,
    decide_admission,
)
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import (
    EvidenceClass,
    EvidenceRef,
    Receipt,
    Verdict,
    canonical_json,
    digest,
    text_digest,
)

POWER_SCHEMA_VERSION = "egrt.power.v2"


class FailureHypothesisStatus(str, Enum):
    """Declared or evaluated state of a named engineering failure hypothesis."""

    OPEN = "OPEN"
    REFUTED = "REFUTED"
    SUPPORTED = "SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class VerificationCheckType(str, Enum):
    DIRECT_TARGETED = "DIRECT_TARGETED"
    REGRESSION = "REGRESSION"
    REAL_ENTRYPOINT = "REAL_ENTRYPOINT"
    NEGATIVE_CONTROL = "NEGATIVE_CONTROL"
    MUTATION = "MUTATION"
    PROPERTY_GENERATED = "PROPERTY_GENERATED"
    METAMORPHIC = "METAMORPHIC"
    DIFFERENTIAL = "DIFFERENTIAL"
    ENVIRONMENT_INTEGRATION = "ENVIRONMENT_INTEGRATION"


class DefectOrigin(str, Enum):
    """Evidence-conditioned failure-location candidates, not automatic facts."""

    TASK_ARTIFACT = "TASK_ARTIFACT"
    AGENT_HARNESS = "AGENT_HARNESS"
    TOOL_ENVIRONMENT = "TOOL_ENVIRONMENT"
    TEST_ORACLE = "TEST_ORACLE"
    UNKNOWN = "UNKNOWN"


class RepairStrategy(str, Enum):
    LOCAL_TYPED = "LOCAL_TYPED"
    DEFER_OR_BROADER_REVIEW = "DEFER_OR_BROADER_REVIEW"


@dataclass(frozen=True)
class FailureHypothesis:
    hypothesis_id: str
    task_id: str
    obligation_id: str
    plan_id: str
    failure_class: str
    trigger: str
    expected_symptom: str
    refuter: str
    load_bearing: bool
    status: FailureHypothesisStatus = FailureHypothesisStatus.OPEN
    candidate_hash: str | None = None
    scope_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "hypothesis_id",
            "task_id",
            "obligation_id",
            "plan_id",
            "failure_class",
            "trigger",
            "expected_symptom",
            "refuter",
        ):
            _require_text(name, getattr(self, name))
        if not isinstance(self.load_bearing, bool):
            raise TypeError("load_bearing must be bool")
        if not isinstance(self.status, FailureHypothesisStatus):
            raise TypeError("status must be FailureHypothesisStatus")
        _require_optional_hash("candidate_hash", self.candidate_hash)
        _require_optional_hash("scope_hash", self.scope_hash)
        _require_metadata(self.metadata)
        # Canonicalize a detached copy so the caller's original mapping cannot later
        # change this hypothesis.  A mutation of the retained dict is also detected
        # again before execution by ``_validate_hypothesis_content``.
        canonical_metadata = _canonical_metadata(self.metadata)
        object.__setattr__(self, "metadata", canonical_metadata)
        object.__setattr__(self, "content_hash", digest(_hypothesis_payload(self)))

    def semantic_key(self) -> str:
        """Identity for duplicate-round suppression, excluding cosmetic IDs/metadata."""

        return digest(
            {
                "task_id": self.task_id,
                "obligation_id": self.obligation_id,
                "plan_id": self.plan_id,
                "candidate_hash": self.candidate_hash,
                "scope_hash": self.scope_hash,
                "failure_class": _normalize_semantic_text(self.failure_class),
                "trigger": _normalize_semantic_text(self.trigger),
                "expected_symptom": _normalize_semantic_text(self.expected_symptom),
                "refuter": _normalize_semantic_text(self.refuter),
            }
        )


@dataclass(frozen=True)
class VerificationCheck:
    # The first eight fields preserve the historical constructor and receipt surface.
    check_id: str
    kind: str
    command: tuple[str, ...]
    expected_exit: int = 0
    timeout_seconds: int = 60
    mandatory: bool = True
    defect_classes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    # Additive Power v2 contract.
    check_type: VerificationCheckType = VerificationCheckType.DIRECT_TARGETED
    failure_hypothesis_id: str | None = None
    failure_class: str | None = None
    oracle: str | None = None
    expected_invariant: str | None = None
    expected_support_signal: str | None = None
    expected_failure_signal: str | None = None
    applicable: bool = True
    applicability_reason: str | None = None
    entrypoint: str | None = None
    suspected_origin: DefectOrigin = DefectOrigin.UNKNOWN
    discriminator_success_exit: int | None = None

    def __post_init__(self) -> None:
        _require_text("check_id", self.check_id)
        _require_text("kind", self.kind)
        if not isinstance(self.command, tuple) or any(
            not isinstance(token, str) for token in self.command
        ):
            raise TypeError("command must be tuple[str, ...]")
        for name in ("expected_exit", "timeout_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be int")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not isinstance(self.mandatory, bool) or not isinstance(self.applicable, bool):
            raise TypeError("mandatory and applicable must be bool")
        if not isinstance(self.defect_classes, tuple) or any(
            not isinstance(value, str) or not value.strip()
            for value in self.defect_classes
        ):
            raise ValueError("defect_classes must contain non-empty strings")
        _require_metadata(self.metadata)
        if not isinstance(self.check_type, VerificationCheckType):
            raise TypeError("check_type must be VerificationCheckType")
        if not isinstance(self.suspected_origin, DefectOrigin):
            raise TypeError("suspected_origin must be DefectOrigin")
        for name in (
            "failure_hypothesis_id",
            "failure_class",
            "oracle",
            "expected_invariant",
            "expected_support_signal",
            "expected_failure_signal",
            "applicability_reason",
            "entrypoint",
        ):
            _require_optional_text(name, getattr(self, name))
        if self.discriminator_success_exit is not None and (
            isinstance(self.discriminator_success_exit, bool)
            or not isinstance(self.discriminator_success_exit, int)
        ):
            raise TypeError("discriminator_success_exit must be int or None")


@dataclass(frozen=True)
class VerificationPlan:
    # Historical fields remain positional and unchanged.
    plan_id: str
    obligation_id: str
    system_boundary: str
    claim: str
    invariants: tuple[str, ...]
    checks: tuple[VerificationCheck, ...]
    # Additive Power v2 binding and minimum-gate fields.
    task_id: str | None = None
    candidate_hash: str | None = None
    scope_hash: str | None = None
    obligation_set_hash: str | None = None
    failure_hypotheses: tuple[FailureHypothesis, ...] = ()
    substantial_change: bool = False
    actual_entrypoint: str | None = None
    entrypoint_applicable: bool | None = None
    entrypoint_reason: str | None = None
    residual_failure_classes: tuple[str, ...] = ()
    schema: str = POWER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("plan_id", "obligation_id", "system_boundary", "claim"):
            _require_text(name, getattr(self, name))
        if not isinstance(self.invariants, tuple) or any(
            not isinstance(value, str) or not value.strip() for value in self.invariants
        ):
            raise ValueError("invariants must contain non-empty strings")
        if not isinstance(self.checks, tuple) or any(
            not isinstance(value, VerificationCheck) for value in self.checks
        ):
            raise TypeError("checks must contain VerificationCheck values")
        _require_optional_text("task_id", self.task_id)
        _require_optional_hash("candidate_hash", self.candidate_hash)
        _require_optional_hash("scope_hash", self.scope_hash)
        _require_optional_hash("obligation_set_hash", self.obligation_set_hash)
        if not isinstance(self.failure_hypotheses, tuple) or any(
            not isinstance(value, FailureHypothesis) for value in self.failure_hypotheses
        ):
            raise TypeError("failure_hypotheses must contain FailureHypothesis values")
        if not isinstance(self.substantial_change, bool):
            raise TypeError("substantial_change must be bool")
        _require_optional_text("actual_entrypoint", self.actual_entrypoint)
        if self.entrypoint_applicable is not None and not isinstance(
            self.entrypoint_applicable, bool
        ):
            raise TypeError("entrypoint_applicable must be bool or None")
        _require_optional_text("entrypoint_reason", self.entrypoint_reason)
        if not isinstance(self.residual_failure_classes, tuple) or any(
            not isinstance(value, str) or not value.strip()
            for value in self.residual_failure_classes
        ):
            raise ValueError("residual_failure_classes must contain non-empty strings")
        if self.schema != POWER_SCHEMA_VERSION:
            raise ValueError(f"schema must be {POWER_SCHEMA_VERSION}")


KNOWN_KINDS = {
    "python-unittest",
    "python-script",
    "compileall",
    "pytest",
    "ruff",
    "z3",
    "semgrep",
    "mutmut",
    "custom",
}
# Modules the constrained python-module families may invoke via ``-m``.
ALLOWED_PY_MODULES = {"unittest", "pytest", "compileall", "ruff"}
# Flags that turn a constrained module command into an arbitrary-code vector:
# ``-c`` executes source, ``-W`` can import an arbitrary module, ``-p`` loads a plugin.
BLOCKED_MODULE_FLAGS = ("-c", "-W", "-p")
_PATHY_SUFFIXES = (".py", ".pyi", ".txt", ".cfg", ".toml", ".json", ".ini")
_ADVERSARIAL_TYPES = frozenset(
    {
        VerificationCheckType.NEGATIVE_CONTROL,
        VerificationCheckType.MUTATION,
        VerificationCheckType.PROPERTY_GENERATED,
        VerificationCheckType.METAMORPHIC,
        VerificationCheckType.DIFFERENTIAL,
        VerificationCheckType.ENVIRONMENT_INTEGRATION,
    }
)
_NEGATIVE_TYPES = frozenset(
    {VerificationCheckType.NEGATIVE_CONTROL, VerificationCheckType.MUTATION}
)


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_optional_text(name: str, value: object) -> None:
    if value is not None:
        _require_text(name, value)


def _require_optional_hash(name: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str or None")
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase 64-character SHA-256 digest")


def _require_metadata(value: object) -> None:
    if not isinstance(value, dict):
        raise TypeError("metadata must be dict")
    if any(not isinstance(key, str) for key in value):
        raise TypeError("metadata keys must be str")


def _canonical_metadata(value: dict[str, Any]) -> dict[str, Any]:
    """Return a detached JSON-shaped copy or fail before evidence is accepted."""

    import json

    decoded = json.loads(canonical_json(value))
    if not isinstance(decoded, dict):  # pragma: no cover - guarded by _require_metadata
        raise TypeError("metadata must canonically encode to an object")
    return decoded


def _hypothesis_payload(hypothesis: FailureHypothesis) -> dict[str, Any]:
    return {
        "hypothesis_id": hypothesis.hypothesis_id,
        "task_id": hypothesis.task_id,
        "obligation_id": hypothesis.obligation_id,
        "plan_id": hypothesis.plan_id,
        "candidate_hash": hypothesis.candidate_hash,
        "scope_hash": hypothesis.scope_hash,
        "failure_class": hypothesis.failure_class,
        "trigger": hypothesis.trigger,
        "expected_symptom": hypothesis.expected_symptom,
        "refuter": hypothesis.refuter,
        "load_bearing": hypothesis.load_bearing,
        "status": hypothesis.status.value,
        "metadata": hypothesis.metadata,
    }


def _validate_hypothesis_content(hypothesis: FailureHypothesis) -> None:
    if digest(_hypothesis_payload(hypothesis)) != hypothesis.content_hash:
        raise ValueError(
            f"failure hypothesis {hypothesis.hypothesis_id!r} content binding changed"
        )


def _normalize_semantic_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _is_v2_plan(plan: VerificationPlan) -> bool:
    return bool(
        plan.task_id is not None
        or plan.candidate_hash is not None
        or plan.scope_hash is not None
        or plan.obligation_set_hash is not None
        or plan.failure_hypotheses
        or plan.substantial_change
        or plan.actual_entrypoint is not None
        or plan.entrypoint_applicable is not None
        or plan.entrypoint_reason is not None
        or plan.residual_failure_classes
        or any(_is_typed_check(check) for check in plan.checks)
    )


def _is_typed_check(check: VerificationCheck) -> bool:
    return bool(
        check.check_type is not VerificationCheckType.DIRECT_TARGETED
        or check.failure_hypothesis_id is not None
        or check.failure_class is not None
        or check.oracle is not None
        or check.expected_invariant is not None
        or check.expected_support_signal is not None
        or check.expected_failure_signal is not None
        or not check.applicable
        or check.applicability_reason is not None
        or check.entrypoint is not None
        or check.suspected_origin is not DefectOrigin.UNKNOWN
        or check.discriminator_success_exit is not None
    )


def validate_plan(plan: VerificationPlan) -> dict[str, Any]:
    """Validate binding and applicability before any verifier process may run."""

    check_ids = [check.check_id for check in plan.checks]
    if len(set(check_ids)) != len(check_ids):
        raise ValueError("verification check IDs must be unique")
    if not _is_v2_plan(plan):
        return {
            "contract": "HISTORICAL_COMPATIBILITY",
            "substantial_change": False,
            "requirements": {},
        }
    if plan.task_id is None:
        raise ValueError("Power v2 plan requires task_id")
    if not plan.failure_hypotheses:
        raise ValueError("Power v2 plan requires at least one FailureHypothesis")

    hypotheses: dict[str, FailureHypothesis] = {}
    semantic_keys: dict[str, str] = {}
    for hypothesis in plan.failure_hypotheses:
        _validate_hypothesis_content(hypothesis)
        if hypothesis.hypothesis_id in hypotheses:
            raise ValueError("failure hypothesis IDs must be unique")
        if hypothesis.task_id != plan.task_id:
            raise ValueError("failure hypothesis task_id binding mismatch")
        if hypothesis.obligation_id != plan.obligation_id:
            raise ValueError("failure hypothesis obligation_id binding mismatch")
        if hypothesis.plan_id != plan.plan_id:
            raise ValueError("failure hypothesis plan_id binding mismatch")
        if hypothesis.candidate_hash != plan.candidate_hash:
            raise ValueError("failure hypothesis candidate_hash binding mismatch")
        if hypothesis.scope_hash != plan.scope_hash:
            raise ValueError("failure hypothesis scope_hash binding mismatch")
        semantic_key = hypothesis.semantic_key()
        if semantic_key in semantic_keys:
            raise ValueError(
                "duplicate semantically identical failure hypotheses: "
                f"{semantic_keys[semantic_key]} and {hypothesis.hypothesis_id}"
            )
        hypotheses[hypothesis.hypothesis_id] = hypothesis
        semantic_keys[semantic_key] = hypothesis.hypothesis_id

    for check in plan.checks:
        if not _is_typed_check(check):
            raise ValueError(
                f"Power v2 check {check.check_id!r} lacks the typed adversarial contract"
            )
        if not check.applicable:
            if check.mandatory:
                raise ValueError("NOT_APPLICABLE checks must not be mandatory")
            if not check.applicability_reason:
                raise ValueError("NOT_APPLICABLE check requires applicability_reason")
        for name in (
            "failure_hypothesis_id",
            "failure_class",
            "oracle",
            "expected_invariant",
            "expected_support_signal",
            "expected_failure_signal",
        ):
            if getattr(check, name) is None:
                raise ValueError(f"typed check {check.check_id!r} requires {name}")
        hypothesis = hypotheses.get(str(check.failure_hypothesis_id))
        if hypothesis is None:
            raise ValueError("verification check references unknown failure hypothesis")
        if check.failure_class != hypothesis.failure_class:
            raise ValueError("verification check failure_class binding mismatch")
        if hypothesis.load_bearing and check.applicable and not check.mandatory:
            raise ValueError("checks for load-bearing failure hypotheses must be mandatory")
        if (
            check.suspected_origin is not DefectOrigin.UNKNOWN
            and not check.metadata.get("attribution_discriminator")
        ):
            raise ValueError(
                "non-UNKNOWN defect origin requires an attribution_discriminator"
            )
        if check.check_type in _NEGATIVE_TYPES:
            if check.discriminator_success_exit is None:
                raise ValueError(
                    "mutation/negative-control check requires discriminator_success_exit"
                )
            if (
                check.discriminator_success_exit == check.expected_exit
                and not check.metadata.get("external_mutation_harness")
            ):
                raise ValueError(
                    "negative control cannot share the normal success exit unless an "
                    "external mutation harness is explicitly bound"
                )
        elif check.discriminator_success_exit is not None:
            raise ValueError(
                "discriminator_success_exit is only valid for mutation/negative controls"
            )
        if check.check_type is VerificationCheckType.METAMORPHIC:
            for key in (
                "relation_id",
                "input_transform",
                "expected_output_relation",
                "applicable_scope",
            ):
                if not isinstance(check.metadata.get(key), str) or not str(
                    check.metadata[key]
                ).strip():
                    raise ValueError(f"metamorphic check requires metadata[{key!r}]")
        if check.check_type is VerificationCheckType.REAL_ENTRYPOINT and check.applicable:
            if plan.actual_entrypoint is None:
                raise ValueError("applicable REAL_ENTRYPOINT check requires plan entrypoint")
            if check.entrypoint != plan.actual_entrypoint:
                raise ValueError("REAL_ENTRYPOINT check is not bound to plan entrypoint")

    requirements: dict[str, dict[str, Any]] = {}
    if plan.substantial_change:
        direct = _checks_of_type(plan, VerificationCheckType.DIRECT_TARGETED, True)
        regression = _checks_of_type(plan, VerificationCheckType.REGRESSION, True)
        adversarial = [
            check
            for check in plan.checks
            if check.applicable and check.check_type in _ADVERSARIAL_TYPES
        ]
        requirements["direct_targeted"] = {
            "applicable": True,
            "reason": "substantial_change",
            "satisfied": bool(direct),
        }
        requirements["regression"] = {
            "applicable": True,
            "reason": "substantial_change",
            "satisfied": bool(regression),
        }
        requirements["adversarial_discriminator"] = {
            "applicable": True,
            "reason": "substantial_change",
            "satisfied": bool(adversarial),
        }
        if not direct:
            raise ValueError("substantial change requires a direct targeted check")
        if not regression:
            raise ValueError("substantial change requires a regression check")
        if not adversarial:
            raise ValueError("substantial change requires an adversarial discriminator")
        if plan.entrypoint_applicable is None:
            raise ValueError("substantial change requires explicit entrypoint applicability")
        entrypoint_checks = [
            check
            for check in plan.checks
            if check.check_type is VerificationCheckType.REAL_ENTRYPOINT
        ]
        if plan.entrypoint_applicable:
            satisfied = bool(
                plan.actual_entrypoint
                and any(check.applicable for check in entrypoint_checks)
            )
            requirements["real_entrypoint"] = {
                "applicable": True,
                "reason": "declared_runtime_surface",
                "satisfied": satisfied,
            }
            if not satisfied:
                raise ValueError("substantial change requires the real entrypoint check")
        else:
            satisfied = bool(
                plan.entrypoint_reason
                and any(not check.applicable for check in entrypoint_checks)
            )
            requirements["real_entrypoint"] = {
                "applicable": False,
                "reason": plan.entrypoint_reason,
                "satisfied": satisfied,
            }
            if not satisfied:
                raise ValueError(
                    "irrelevant real entrypoint requires a reason and NOT_APPLICABLE check"
                )
        if not plan.residual_failure_classes:
            raise ValueError("substantial change requires a residual failure class")
        requirements["residual_failure_class"] = {
            "applicable": True,
            "reason": "coverage_boundary",
            "satisfied": True,
        }
    return {
        "contract": POWER_SCHEMA_VERSION,
        "substantial_change": plan.substantial_change,
        "requirements": requirements,
    }


def _checks_of_type(
    plan: VerificationPlan,
    check_type: VerificationCheckType,
    applicable: bool,
) -> list[VerificationCheck]:
    return [
        check
        for check in plan.checks
        if check.check_type is check_type and check.applicable is applicable
    ]


def select_repair_strategy(
    *,
    fault_localized: bool,
    invariants_known: bool,
    independently_verifiable: bool,
) -> RepairStrategy:
    """Apply the local typed-repair preference only when all guards are established."""

    for name, value in (
        ("fault_localized", fault_localized),
        ("invariants_known", invariants_known),
        ("independently_verifiable", independently_verifiable),
    ):
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be bool")
    if fault_localized and invariants_known and independently_verifiable:
        return RepairStrategy.LOCAL_TYPED
    return RepairStrategy.DEFER_OR_BROADER_REVIEW


def verify_repair_candidate(
    candidate: CandidateBinding | CandidateRepair,
    structural: StructuralCertificate | None = None,
    semantic: SemanticVerification | None = None,
) -> AdmissionDecision:
    """Delegate to the neutral gate; this function never applies or promotes a patch."""

    return decide_admission(candidate, structural, semantic)


def _basename(value: str) -> str:
    return Path(value).name.lower()


def _has_sep(value: str) -> bool:
    return os.sep in value or "/" in value


def _same_file(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _looks_like_path(token: str) -> bool:
    if token == "discover":
        return True
    if _has_sep(token) or token.endswith(_PATHY_SUFFIXES):
        return True
    return Path(token).exists()


def _module_args_allowed(
    args: list[str], *, allow_custom: bool
) -> tuple[bool, str | None]:
    """A constrained module command may carry only paths and safe flags.

    A bare non-path token after ``-m unittest``/``-m pytest`` is a dotted module name,
    which executes arbitrary code at import; that is exactly the vector this guards.
    """

    if allow_custom:
        return True, None
    for token in args:
        if token.startswith("-"):
            if any(token == flag or token.startswith(flag) for flag in BLOCKED_MODULE_FLAGS):
                return False, (
                    f"disallowed flag {token!r} in constrained module command; "
                    "set EGR_POWER_ALLOW_CUSTOM_COMMANDS=1 at the outer boundary to override"
                )
            continue
        if not _looks_like_path(token):
            return False, (
                f"argument {token!r} is not a path or safe flag; arbitrary module names are "
                "refused (set EGR_POWER_ALLOW_CUSTOM_COMMANDS=1 at the outer boundary to "
                "override)"
            )
    return True, None


def _entrypoint_inside_root(root: Path, value: str) -> tuple[bool, str | None]:
    """Require a real Python entrypoint to resolve inside the supplied repository root."""

    root_path = root.resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root_path / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        return False, "python-script entrypoint does not exist"
    if not resolved.is_file():
        return False, "python-script entrypoint is not a file"
    try:
        resolved.relative_to(root_path)
    except ValueError:
        return False, "python-script entrypoint resolves outside the repository root"
    return True, None


def _command_shape_allowed(root: Path, check: VerificationCheck) -> tuple[bool, str | None]:
    if check.kind not in KNOWN_KINDS:
        return False, f"unknown verifier kind: {check.kind}"
    if not check.command:
        return False, "empty command"
    command = list(check.command)
    exe = _basename(command[0])
    pythonish = exe.startswith("python") or exe in {"py"}
    allow_custom = os.environ.get("EGR_POWER_ALLOW_CUSTOM_COMMANDS") == "1"
    if check.kind == "custom":
        if not allow_custom:
            return False, (
                "custom command disabled; set EGR_POWER_ALLOW_CUSTOM_COMMANDS=1 "
                "at the outer execution boundary"
            )
        return True, None
    if check.kind == "python-script":
        if not pythonish or len(command) < 2 or not command[1].endswith(".py"):
            return False, "python-script command must be python <entrypoint.py> ..."
        inside, reason = _entrypoint_inside_root(root, command[1])
        if not inside:
            return False, reason
        return _module_args_allowed(command[2:], allow_custom=allow_custom)
    if check.kind in {"python-unittest", "compileall"}:
        module = "unittest" if check.kind == "python-unittest" else "compileall"
        if not (pythonish and command[1:3] == ["-m", module]):
            return False, f"{check.kind} command must be python -m {module} ..."
        return _module_args_allowed(command[3:], allow_custom=allow_custom)
    if check.kind == "pytest":
        if pythonish and command[1:3] == ["-m", "pytest"]:
            return _module_args_allowed(command[3:], allow_custom=allow_custom)
        if exe == "pytest":
            return _module_args_allowed(command[1:], allow_custom=allow_custom)
        return False, "pytest command must be pytest ... or python -m pytest ..."
    if check.kind == "ruff":
        if pythonish and command[1:3] == ["-m", "ruff"]:
            return _module_args_allowed(command[3:], allow_custom=allow_custom)
        if exe == "ruff":
            return _module_args_allowed(command[1:], allow_custom=allow_custom)
        return False, "ruff command must be ruff ... or python -m ruff ..."
    expected = {"z3": "z3", "semgrep": "semgrep", "mutmut": "mutmut"}[check.kind]
    return exe == expected, f"{check.kind} command must execute {expected} directly"


def _resolve_executable(check: VerificationCheck) -> tuple[str | None, str | None]:
    """Resolve argv[0] to a trusted absolute path or refuse it.

    Path-existence is not trust: a binary named ``z3``/``ruff``/``pytest`` in a
    scratch directory must not run just because its file exists. Python families must
    be the active interpreter; direct-binary families must resolve on PATH by name.
    """

    argv0 = check.command[0]
    exe = _basename(argv0)
    pythonish = exe.startswith("python") or exe in {"py"}
    if pythonish or check.kind in {"python-unittest", "compileall"}:
        if _same_file(argv0, sys.executable):
            return sys.executable, None
        resolved = shutil.which(argv0)
        if resolved and _same_file(resolved, sys.executable):
            return resolved, None
        return None, (
            "python-family verifier must run the active interpreter "
            f"(sys.executable), got {argv0!r}"
        )
    on_path = shutil.which(exe)
    if on_path is None:
        return None, f"tool not found on PATH: {exe}"
    if _has_sep(argv0) and not _same_file(argv0, on_path):
        return None, f"refusing {argv0!r}: not the {exe} resolved on PATH"
    return on_path, None


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def _coverage_classes(check: VerificationCheck) -> list[str]:
    values = list(check.defect_classes)
    if check.failure_class and check.failure_class not in values:
        values.append(check.failure_class)
    return values


def _check_common(check: VerificationCheck) -> dict[str, Any]:
    attribution_status = (
        "DISCRIMINATOR_DECLARED"
        if check.suspected_origin is not DefectOrigin.UNKNOWN
        else "UNRESOLVED"
    )
    return {
        "check_id": check.check_id,
        "kind": check.kind,
        "check_type": check.check_type.value,
        "failure_hypothesis_id": check.failure_hypothesis_id,
        "failure_class": check.failure_class,
        "oracle": check.oracle,
        "expected_invariant": check.expected_invariant,
        "expected_support_signal": check.expected_support_signal,
        "expected_failure_signal": check.expected_failure_signal,
        "defect_classes": _coverage_classes(check),
        "suspected_origin": check.suspected_origin.value,
        "attribution_status": attribution_status,
        "check_evidence_identity": digest(check),
    }


def run_check(root: Path, check: VerificationCheck) -> dict[str, Any]:
    common = _check_common(check)
    if not check.applicable:
        return {
            **common,
            "verdict": Verdict.CLEARED.value,
            "check_status": "NOT_APPLICABLE",
            "reason": check.applicability_reason,
            "entrypoint": check.entrypoint,
        }
    allowed, reason = _command_shape_allowed(root, check)
    if not allowed:
        return {
            **common,
            "verdict": Verdict.UNAVAILABLE.value,
            "check_status": "UNAVAILABLE",
            "reason": reason,
        }
    resolved, resolve_reason = _resolve_executable(check)
    if resolved is None:
        return {
            **common,
            "verdict": Verdict.UNAVAILABLE.value,
            "check_status": "UNAVAILABLE",
            "reason": resolve_reason,
        }
    command = [resolved, *list(check.command)[1:]]
    environment_identity = digest(
        {
            "resolved_executable": resolved,
            "python": sys.version,
            "platform": sys.platform,
            "check_evidence_identity": common["check_evidence_identity"],
        }
    )
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=check.timeout_seconds,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            **common,
            "verdict": Verdict.UNKNOWN.value,
            "check_status": "TIMEOUT",
            "reason": "timeout",
            "elapsed_seconds": time.monotonic() - started,
            "stdout_hash": text_digest(_as_text(exc.stdout)),
            "stderr_hash": text_digest(_as_text(exc.stderr)),
            "environment_identity": environment_identity,
        }
    except OSError as exc:
        return {
            **common,
            "verdict": Verdict.UNAVAILABLE.value,
            "check_status": "UNAVAILABLE",
            "reason": type(exc).__name__,
            "environment_identity": environment_identity,
        }

    effective_exit = (
        check.discriminator_success_exit
        if check.check_type in _NEGATIVE_TYPES
        else check.expected_exit
    )
    assert effective_exit is not None
    cleared = proc.returncode == effective_exit
    verdict = Verdict.CLEARED if cleared else Verdict.ISSUE
    result: dict[str, Any] = {
        **common,
        "verdict": verdict.value,
        "check_status": "EXECUTED",
        "exit_code": proc.returncode,
        "expected_exit": check.expected_exit,
        "effective_success_exit": effective_exit,
        "elapsed_seconds": time.monotonic() - started,
        "stdout_hash": text_digest(proc.stdout),
        "stderr_hash": text_digest(proc.stderr),
        "environment_identity": environment_identity,
        "entrypoint": check.entrypoint,
    }
    if check.check_type in _NEGATIVE_TYPES:
        if cleared:
            result["discriminator_outcome"] = "KILLED"
        elif proc.returncode == check.expected_exit:
            result["discriminator_outcome"] = "SURVIVED"
        else:
            result["discriminator_outcome"] = "NOT_KILLED"
    if check.check_type is VerificationCheckType.METAMORPHIC:
        result["relation_id"] = check.metadata.get("relation_id")
        result["relation_outcome"] = "HOLDS" if cleared else "VIOLATED"
        result["relation_scope"] = check.metadata.get("applicable_scope")
    return result


def _aggregate_mandatory(
    checks: tuple[VerificationCheck, ...], results: list[dict[str, Any]]
) -> Verdict:
    by_id = {check.check_id: check for check in checks}
    mandatory = [
        row
        for row in results
        if by_id[row["check_id"]].mandatory and by_id[row["check_id"]].applicable
    ]
    if any(row["verdict"] == Verdict.ISSUE.value for row in mandatory):
        return Verdict.ISSUE
    if any(row["verdict"] == Verdict.UNAVAILABLE.value for row in mandatory):
        return Verdict.UNAVAILABLE
    if any(row["verdict"] == Verdict.UNKNOWN.value for row in mandatory):
        return Verdict.UNKNOWN
    if mandatory and all(row["verdict"] == Verdict.CLEARED.value for row in mandatory):
        return Verdict.CLEARED
    return Verdict.UNKNOWN


def _hypothesis_results(
    plan: VerificationPlan, results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    evaluated: list[dict[str, Any]] = []
    for hypothesis in plan.failure_hypotheses:
        rows = [
            row
            for row in results
            if row.get("failure_hypothesis_id") == hypothesis.hypothesis_id
        ]
        applicable = [row for row in rows if row.get("check_status") != "NOT_APPLICABLE"]
        if hypothesis.status is FailureHypothesisStatus.NOT_APPLICABLE:
            status = FailureHypothesisStatus.NOT_APPLICABLE
        elif not applicable:
            status = FailureHypothesisStatus.INCONCLUSIVE
        elif any(row["verdict"] == Verdict.ISSUE.value for row in applicable):
            status = FailureHypothesisStatus.SUPPORTED
        elif any(row["verdict"] == Verdict.UNAVAILABLE.value for row in applicable):
            status = FailureHypothesisStatus.UNAVAILABLE
        elif any(row["verdict"] == Verdict.UNKNOWN.value for row in applicable):
            status = FailureHypothesisStatus.INCONCLUSIVE
        elif all(row["verdict"] == Verdict.CLEARED.value for row in applicable):
            status = FailureHypothesisStatus.REFUTED
        else:  # pragma: no cover - defensive over the four-verdict algebra
            status = FailureHypothesisStatus.INCONCLUSIVE
        evaluated.append(
            {
                "hypothesis_id": hypothesis.hypothesis_id,
                "failure_class": hypothesis.failure_class,
                "load_bearing": hypothesis.load_bearing,
                "declared_status": hypothesis.status.value,
                "evaluated_status": status.value,
                "content_hash": hypothesis.content_hash,
                "check_ids": [row["check_id"] for row in rows],
            }
        )
    return evaluated


def _apply_hypothesis_gate(
    verdict: Verdict, hypothesis_rows: list[dict[str, Any]]
) -> Verdict:
    load_bearing = [row for row in hypothesis_rows if row["load_bearing"]]
    if any(
        row["evaluated_status"] == FailureHypothesisStatus.SUPPORTED.value
        for row in load_bearing
    ):
        return Verdict.ISSUE
    if verdict is Verdict.ISSUE:
        return verdict
    if any(
        row["evaluated_status"] == FailureHypothesisStatus.UNAVAILABLE.value
        for row in load_bearing
    ):
        return Verdict.UNAVAILABLE
    if verdict is Verdict.UNAVAILABLE:
        return verdict
    if any(
        row["evaluated_status"]
        in {
            FailureHypothesisStatus.OPEN.value,
            FailureHypothesisStatus.INCONCLUSIVE.value,
        }
        for row in load_bearing
    ):
        return Verdict.UNKNOWN
    return verdict


def run_plan(root: Path, plan: VerificationPlan) -> tuple[Receipt, dict[str, Any]]:
    contract = validate_plan(plan)
    store = RuntimeStore(root)
    results = [run_check(root, check) for check in plan.checks]
    verdict = _aggregate_mandatory(plan.checks, results)
    hypotheses = _hypothesis_results(plan, results)
    if _is_v2_plan(plan):
        verdict = _apply_hypothesis_gate(verdict, hypotheses)
    coverage = {row["check_id"]: row.get("defect_classes", []) for row in results}
    plan_identity = digest(plan)
    evidence_identity = digest(
        {
            "plan_identity": plan_identity,
            "check_evidence_identities": [
                row.get("check_evidence_identity") for row in results
            ],
            "environment_identities": [row.get("environment_identity") for row in results],
        }
    )
    coverage_boundary = (
        "Only named checks, relations, and failure classes are covered; green checks "
        "do not imply exhaustive correctness. Residual classes remain outside this gate."
    )
    result = {
        "schema": POWER_SCHEMA_VERSION,
        "plan_id": plan.plan_id,
        "task_id": plan.task_id,
        "obligation_id": plan.obligation_id,
        "verdict": verdict.value,
        "checks": results,
        "hypotheses": hypotheses,
        "coverage": coverage,
        "coverage_boundary": coverage_boundary,
        "residual_failure_classes": list(plan.residual_failure_classes),
        "substantial_change_requirements": contract["requirements"],
        "actual_entrypoint": plan.actual_entrypoint,
        "entrypoint_applicable": plan.entrypoint_applicable,
        "entrypoint_reason": plan.entrypoint_reason,
        "plan_identity": plan_identity,
        "evidence_identity": evidence_identity,
        "custom_commands_enabled": os.environ.get("EGR_POWER_ALLOW_CUSTOM_COMMANDS")
        == "1",
        "authority": "ENGINEERING_VERIFICATION_ONLY",
        "repair_promotion_authorized": False,
        "execution_authorized": False,
    }
    unresolved: list[str] = []
    by_id = {check.check_id: check for check in plan.checks}
    for row in results:
        check = by_id[row["check_id"]]
        if check.mandatory and check.applicable and row["verdict"] in {
            Verdict.UNAVAILABLE.value,
            Verdict.UNKNOWN.value,
        }:
            unresolved.append(
                f"{row['check_id']}: {row.get('reason', row['verdict'])}"
            )
    for row in hypotheses:
        if row["load_bearing"] and row["evaluated_status"] in {
            FailureHypothesisStatus.INCONCLUSIVE.value,
            FailureHypothesisStatus.UNAVAILABLE.value,
        }:
            unresolved.append(
                f"{row['hypothesis_id']}: {row['evaluated_status'].lower()}"
            )
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="power",
        obligation_id=plan.obligation_id,
        verdict=verdict,
        action="verification-plan",
        input_hash=plan_identity,
        output_hash=digest(result),
        evidence=(
            EvidenceRef(
                evidence_class=EvidenceClass.MEASURED,
                verifier="power_runtime",
                metadata={
                    "coverage": coverage,
                    "evidence_identity": evidence_identity,
                    "residual_failure_classes": list(plan.residual_failure_classes),
                    "power_schema": POWER_SCHEMA_VERSION,
                },
            ),
        ),
        verifier="power_runtime",
        tool_version=POWER_SCHEMA_VERSION,
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=tuple(unresolved),
        notes=coverage_boundary,
        task_id=plan.task_id,
    )
    store.write_named_state("power", plan.plan_id, result)
    store.write_receipt(receipt)
    return receipt, result


# Explicit alias for the normal Soul-routed host invocation.  Soul retains routing and
# release authority; this function only executes the already frozen Power plan.
run_automatic_verification = run_plan


__all__ = [
    "DefectOrigin",
    "FailureHypothesis",
    "FailureHypothesisStatus",
    "POWER_SCHEMA_VERSION",
    "RepairStrategy",
    "VerificationCheck",
    "VerificationCheckType",
    "VerificationPlan",
    "run_automatic_verification",
    "run_check",
    "run_plan",
    "select_repair_strategy",
    "validate_plan",
    "verify_repair_candidate",
]
