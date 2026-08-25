"""Closed structured-spec compiler for FOIL v5 residual obligations.

This compiler accepts only a versioned declarative schema.  It never extracts
checks from prose: every axis, verifier, exact verifier input, coverage range,
and binding is supplied by the source spec.  Its only executable surface is the
closed in-process built-ins already exposed by ``DEFAULT_REGISTRY``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from egrt_claims import (
    Applicability,
    ClaimKind,
    Decidability,
    ImmutableBindings,
    PostSolveClaim,
    PostSolveObligation,
)
from egrt_types import digest
from egrt_verifiers import DEFAULT_REGISTRY
from foil_residual_scanner import DiagnosticCase, ResidualScanPlan, contains_forbidden_metadata
from foil_v5_metrics import ResidualDiagnosticNeed

TASK_SPEC_SCHEMA = "egrt.foil-v5.structured-task-spec.v1"
COMPILER_VERSION = "foil-obligation-compiler.v1"

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ROOT_FIELDS = frozenset(
    {"schema", "compiler_version", "task_digest", "a0_digest", "config_digest", "claims"}
)
_CLAIM_FIELDS = frozenset(
    {
        "claim_key",
        "statement_digest",
        "claim_kind",
        "decidability",
        "applicability",
        "reason",
        "obligations",
    }
)
_OBLIGATION_FIELDS = frozenset(
    {
        "obligation_key",
        "description",
        "weight_range",
        "predicate_kind",
        "verifier_id",
        "verifier_version",
        "verifier_input",
    }
)
_RANGE_FIELDS = frozenset({"start", "end"})


@dataclass(frozen=True)
class PredicateSpec:
    claim_kind: ClaimKind
    verifier_id: str


_PREDICATES: Mapping[str, PredicateSpec] = {
    "EXACT_ARITHMETIC": PredicateSpec(ClaimKind.EXACT_ARITHMETIC, "builtin.exact_arithmetic"),
    "JSON": PredicateSpec(ClaimKind.JSON, "builtin.json_exact"),
    "DIGEST": PredicateSpec(ClaimKind.DIGEST, "builtin.digest_exact"),
    "EXACT_MATCH": PredicateSpec(ClaimKind.EXACT_MATCH, "builtin.exact_match"),
    "NUMERIC_TOLERANCE": PredicateSpec(ClaimKind.NUMERIC_TOLERANCE, "builtin.numeric_tolerance"),
    "NUMERIC_PROVENANCE": PredicateSpec(ClaimKind.NUMERIC_PROVENANCE, "builtin.numeric_provenance"),
    "NUMERIC_PROVENANCE_V2": PredicateSpec(ClaimKind.NUMERIC_PROVENANCE, "builtin.numeric_provenance_v2"),
}
COMPILER_DIGEST = digest(
    {
        "schema": TASK_SPEC_SCHEMA,
        "version": COMPILER_VERSION,
        "predicates": {
            kind: {
                "claim_kind": item.claim_kind.value,
                "verifier_id": item.verifier_id,
                "verifier_version": DEFAULT_REGISTRY.resolve(item.verifier_id).version,
                "input_keys": DEFAULT_REGISTRY.resolve(item.verifier_id).input_keys,
            }
            for kind, item in sorted(_PREDICATES.items())
        },
    }
)


class TaskSpecError(ValueError):
    """A task spec cannot be compiled without weakening its declared boundary."""


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TaskSpecError(f"{name} must be an object")
    return value


def _sequence(name: str, value: object) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TaskSpecError(f"{name} must be a list")
    return value


def _strict_fields(name: str, value: Mapping[str, Any], required: frozenset[str]) -> None:
    fields = set(value)
    if fields != required:
        unknown = sorted(fields - required)
        missing = sorted(required - fields)
        raise TaskSpecError(f"{name} fields are not closed (unknown={unknown}, missing={missing})")


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TaskSpecError(f"{name} must be non-empty text")
    return value


def _digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise TaskSpecError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TaskSpecError(f"{name} must be a positive integer")
    return value


def _enum(enum_type: type, name: str, value: object):
    if not isinstance(value, str):
        raise TaskSpecError(f"{name} must be an enum string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise TaskSpecError(f"{name} is not a supported enum value") from exc


def _stable_id(prefix: str, value: object) -> str:
    return f"{prefix}-{digest(value)[:24]}"


@dataclass(frozen=True)
class ObligationBundle:
    """One immutable obligation and, only when safe, its executable scanner case."""

    obligation: PostSolveObligation
    need: ResidualDiagnosticNeed
    predicate_kind: str
    verifier_version: str
    case: DiagnosticCase | None

    def __post_init__(self) -> None:
        if not isinstance(self.obligation, PostSolveObligation):
            raise TypeError("obligation must be PostSolveObligation")
        if not isinstance(self.need, ResidualDiagnosticNeed):
            raise TypeError("need must be ResidualDiagnosticNeed")
        if self.obligation.obligation_id != self.need.need_id:
            raise ValueError("obligation and diagnostic need ids must match")
        _text("predicate_kind", self.predicate_kind)
        _text("verifier_version", self.verifier_version)
        if self.case is not None:
            if not isinstance(self.case, DiagnosticCase):
                raise TypeError("case must be DiagnosticCase or None")
            if self.case.need_id != self.need.need_id or self.case.metadata:
                raise ValueError("executable cases must be need-scoped and metadata-free")

    @property
    def deterministic(self) -> bool:
        return (
            self.need.decidability is Decidability.DETERMINISTIC
            and self.need.applicability is Applicability.APPLICABLE
        )


@dataclass(frozen=True)
class ClaimBundle:
    """A source claim with all declared residual obligations retained."""

    claim_id: str
    claim_key: str
    claim: PostSolveClaim | None
    decidability: Decidability
    applicability: Applicability
    obligations: tuple[ObligationBundle, ...]

    def __post_init__(self) -> None:
        _text("claim_id", self.claim_id)
        _text("claim_key", self.claim_key)
        if self.claim is not None and self.claim.claim_id != self.claim_id:
            raise ValueError("compiled claim id must match the bundle")
        if not isinstance(self.decidability, Decidability):
            raise TypeError("decidability must be Decidability")
        if not isinstance(self.applicability, Applicability):
            raise TypeError("applicability must be Applicability")
        if not isinstance(self.obligations, tuple) or not self.obligations:
            raise ValueError("claims must retain one or more obligations")
        if any(item.obligation.claim_id != self.claim_id for item in self.obligations):
            raise ValueError("obligations must belong to their claim bundle")

    @property
    def deterministic(self) -> bool:
        return (
            self.decidability is Decidability.DETERMINISTIC
            and self.applicability is Applicability.APPLICABLE
        )


@dataclass(frozen=True)
class CompilationSummary:
    source_spec_digest: str
    compiler_version: str
    compiler_digest: str
    compiled_count: int
    empirical_count: int
    semantic_count: int
    undecidable_count: int
    unknown_count: int
    not_applicable_count: int
    deterministic_obligation_count: int
    residual_obligation_count: int
    summary_digest: str

    def __post_init__(self) -> None:
        for name in ("source_spec_digest", "compiler_digest", "summary_digest"):
            _digest(name, getattr(self, name))
        if self.compiler_version != COMPILER_VERSION:
            raise ValueError("compiler version is fixed")
        for name in (
            "compiled_count",
            "empirical_count",
            "semantic_count",
            "undecidable_count",
            "unknown_count",
            "not_applicable_count",
            "deterministic_obligation_count",
            "residual_obligation_count",
        ):
            if isinstance(getattr(self, name), bool) or getattr(self, name) < 0:
                raise ValueError(f"{name} must be a non-negative integer")


@dataclass(frozen=True)
class CompiledTaskSpec:
    source_spec_digest: str
    bindings: ImmutableBindings
    claims: tuple[ClaimBundle, ...]
    summary: CompilationSummary

    def __post_init__(self) -> None:
        _digest("source_spec_digest", self.source_spec_digest)
        if not isinstance(self.bindings, ImmutableBindings):
            raise TypeError("bindings must be ImmutableBindings")
        if self.bindings.spec_digest != self.source_spec_digest:
            raise ValueError("source digest must match immutable bindings")
        if not isinstance(self.claims, tuple) or not self.claims:
            raise ValueError("compiled task must contain claims")
        if not isinstance(self.summary, CompilationSummary):
            raise TypeError("summary must be CompilationSummary")
        if self.summary.source_spec_digest != self.source_spec_digest:
            raise ValueError("summary must bind the source spec")

    @property
    def compilation_digest(self) -> str:
        return digest(
            {
                "source_spec_digest": self.source_spec_digest,
                "bindings": self.bindings,
                "claim_ids": tuple(item.claim_id for item in self.claims),
                "summary_digest": self.summary.summary_digest,
            }
        )

    def deterministic_scanner_plans(self) -> tuple[ResidualScanPlan, ...]:
        """Return plans that contain only declared deterministic obligations.

        These plans are deliberately partial diagnostic surfaces.  Residual
        empirical, semantic, undecidable, unknown, and N/A obligations remain
        in ``claims`` and never acquire an executable case or decidable mass.
        """

        plans: list[ResidualScanPlan] = []
        for claim in self.claims:
            needs = tuple(item.need for item in claim.obligations if item.deterministic)
            if needs:
                plans.append(
                    ResidualScanPlan(claim.claim_id, self.bindings.a0_digest, self.bindings, needs)
                )
        return tuple(plans)

    def deterministic_cases(self, claim_id: str) -> tuple[DiagnosticCase, ...]:
        _text("claim_id", claim_id)
        for claim in self.claims:
            if claim.claim_id == claim_id:
                return tuple(item.case for item in claim.obligations if item.case is not None)
        raise KeyError(f"unknown compiled claim: {claim_id}")


def _parse_range(value: object, claim_key: str, obligation_key: str) -> tuple[int, int]:
    data = _mapping(f"{claim_key}.{obligation_key}.weight_range", value)
    _strict_fields("weight_range", data, _RANGE_FIELDS)
    start = _positive_int("weight_range.start", data["start"])
    end = _positive_int("weight_range.end", data["end"])
    if end < start:
        raise TaskSpecError("weight_range.end must not be below weight_range.start")
    return start, end


def _claim_count_key(decidability: Decidability, applicability: Applicability) -> str:
    if applicability is Applicability.NOT_APPLICABLE:
        return "not_applicable_count"
    if applicability is Applicability.UNKNOWN or decidability is Decidability.UNKNOWN:
        return "unknown_count"
    if decidability is Decidability.UNDECIDABLE:
        return "undecidable_count"
    if decidability is Decidability.EMPIRICAL:
        return "empirical_count"
    if decidability is Decidability.SEMANTIC:
        return "semantic_count"
    return "compiled_count"


def compile_task_spec(spec: object, *, observed_a0_digest: str) -> CompiledTaskSpec:
    """Compile a fully declared multi-claim task spec after exact A0 binding."""

    data = _mapping("task_spec", spec)
    _strict_fields("task_spec", data, _ROOT_FIELDS)
    if data["schema"] != TASK_SPEC_SCHEMA:
        raise TaskSpecError("task_spec.schema is unsupported")
    if data["compiler_version"] != COMPILER_VERSION:
        raise TaskSpecError("task_spec.compiler_version does not match this compiler")
    a0_digest = _digest("a0_digest", data["a0_digest"])
    if _digest("observed_a0_digest", observed_a0_digest) != a0_digest:
        raise TaskSpecError("observed A0 digest does not match the source binding")
    task_digest = _digest("task_digest", data["task_digest"])
    config_digest = _digest("config_digest", data["config_digest"])
    claim_rows = _sequence("claims", data["claims"])
    if not claim_rows:
        raise TaskSpecError("claims must not be empty")
    source_spec_digest = digest(data)
    bindings = ImmutableBindings(
        a0_digest=a0_digest,
        task_digest=task_digest,
        spec_digest=source_spec_digest,
        compiler_digest=COMPILER_DIGEST,
        config_digest=config_digest,
    )

    claims: list[ClaimBundle] = []
    seen_claim_keys: set[str] = set()
    seen_obligation_keys: set[str] = set()
    counts = {
        "compiled_count": 0,
        "empirical_count": 0,
        "semantic_count": 0,
        "undecidable_count": 0,
        "unknown_count": 0,
        "not_applicable_count": 0,
        "deterministic_obligation_count": 0,
        "residual_obligation_count": 0,
    }
    for row in claim_rows:
        claim_data = _mapping("claim", row)
        _strict_fields("claim", claim_data, _CLAIM_FIELDS)
        claim_key = _text("claim.claim_key", claim_data["claim_key"])
        if claim_key in seen_claim_keys:
            raise TaskSpecError("claim keys must be unique")
        seen_claim_keys.add(claim_key)
        statement_digest = _digest("claim.statement_digest", claim_data["statement_digest"])
        claim_kind = _enum(ClaimKind, "claim.claim_kind", claim_data["claim_kind"])
        decidability = _enum(Decidability, "claim.decidability", claim_data["decidability"])
        applicability = _enum(Applicability, "claim.applicability", claim_data["applicability"])
        _text("claim.reason", claim_data["reason"])
        obligation_rows = _sequence("claim.obligations", claim_data["obligations"])
        if not obligation_rows:
            raise TaskSpecError("claim.obligations must not be empty")
        claim_id = _stable_id(
            "claim",
            {
                "claim_key": claim_key,
                "statement_digest": statement_digest,
                "kind": claim_kind.value,
                "bindings": bindings,
            },
        )
        occupied_ranges: list[tuple[int, int]] = []
        bundles: list[ObligationBundle] = []
        required_verifiers: set[str] = set()
        for obligation_row in obligation_rows:
            obligation_data = _mapping("obligation", obligation_row)
            _strict_fields("obligation", obligation_data, _OBLIGATION_FIELDS)
            obligation_key = _text("obligation.obligation_key", obligation_data["obligation_key"])
            if obligation_key in seen_obligation_keys:
                raise TaskSpecError("obligation keys must be globally unique")
            seen_obligation_keys.add(obligation_key)
            description = _text("obligation.description", obligation_data["description"])
            start, end = _parse_range(obligation_data["weight_range"], claim_key, obligation_key)
            if any(
                start <= other_end and other_start <= end
                for other_start, other_end in occupied_ranges
            ):
                raise TaskSpecError("weight ranges must not overlap within a claim")
            occupied_ranges.append((start, end))
            predicate_kind = _text("obligation.predicate_kind", obligation_data["predicate_kind"])
            try:
                predicate = _PREDICATES[predicate_kind]
            except KeyError as exc:
                raise TaskSpecError(
                    "obligation.predicate_kind is not a closed builtin predicate"
                ) from exc
            verifier_id = _text("obligation.verifier_id", obligation_data["verifier_id"])
            try:
                verifier = DEFAULT_REGISTRY.resolve(verifier_id)
            except KeyError as exc:
                raise TaskSpecError("obligation verifier is not in the closed registry") from exc
            if verifier_id != predicate.verifier_id:
                raise TaskSpecError("predicate kind and verifier id must match exactly")
            if (
                _text("obligation.verifier_version", obligation_data["verifier_version"])
                != verifier.version
            ):
                raise TaskSpecError(
                    "obligation verifier version does not match the closed registry"
                )
            verifier_input = _mapping(
                "obligation.verifier_input", obligation_data["verifier_input"]
            )
            if set(verifier_input) != set(verifier.input_keys):
                raise TaskSpecError("verifier_input keys must exactly match the verifier contract")
            if contains_forbidden_metadata(verifier_input):
                raise TaskSpecError("verifier_input contains answer-bearing or label metadata")
            weight_units = end - start + 1
            obligation_id = _stable_id(
                "obligation",
                {
                    "claim_id": claim_id,
                    "obligation_key": obligation_key,
                    "description": description,
                    "weight_range": (start, end),
                    "predicate_kind": predicate_kind,
                    "verifier_id": verifier_id,
                    "verifier_version": verifier.version,
                    "input_digest": digest(verifier_input),
                    "bindings": bindings,
                },
            )
            obligation = PostSolveObligation(obligation_id, claim_id, description, weight_units)
            need = ResidualDiagnosticNeed(
                need_id=obligation_id,
                claim_id=claim_id,
                description=description,
                verifier_id=verifier_id,
                weight_units=weight_units,
                decidability=decidability,
                applicability=applicability,
                bindings=bindings,
            )
            executable = (
                decidability is Decidability.DETERMINISTIC
                and applicability is Applicability.APPLICABLE
            )
            if executable and claim_kind is not predicate.claim_kind:
                raise TaskSpecError(
                    "deterministic claim kind must match its builtin predicate kind"
                )
            case = DiagnosticCase(obligation_id, dict(verifier_input), {}) if executable else None
            bundles.append(
                ObligationBundle(obligation, need, predicate_kind, verifier.version, case)
            )
            required_verifiers.add(verifier_id)
            if executable:
                counts["deterministic_obligation_count"] += 1
            else:
                counts["residual_obligation_count"] += 1

        deterministic_claim = (
            decidability is Decidability.DETERMINISTIC and applicability is Applicability.APPLICABLE
        )
        claim = (
            PostSolveClaim(
                claim_id=claim_id,
                statement_digest=statement_digest,
                kind=claim_kind,
                decidability=decidability,
                applicability=applicability,
                bindings=bindings,
                required_verifiers=tuple(sorted(required_verifiers)),
            )
            if deterministic_claim
            else None
        )
        counts[_claim_count_key(decidability, applicability)] += 1
        claims.append(
            ClaimBundle(
                claim_id=claim_id,
                claim_key=claim_key,
                claim=claim,
                decidability=decidability,
                applicability=applicability,
                obligations=tuple(bundles),
            )
        )

    summary_payload = {
        "source_spec_digest": source_spec_digest,
        "compiler_version": COMPILER_VERSION,
        "compiler_digest": COMPILER_DIGEST,
        "counts": counts,
        "claim_ids": tuple(item.claim_id for item in claims),
        "obligation_ids": tuple(
            item.obligation.obligation_id for claim in claims for item in claim.obligations
        ),
    }
    summary = CompilationSummary(
        source_spec_digest=source_spec_digest,
        compiler_version=COMPILER_VERSION,
        compiler_digest=COMPILER_DIGEST,
        summary_digest=digest(summary_payload),
        **counts,
    )
    return CompiledTaskSpec(source_spec_digest, bindings, tuple(claims), summary)


def _load_json(path: str) -> object:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile a closed FOIL v5 task spec")
    parser.add_argument("spec", help="JSON task spec path, or - for stdin")
    parser.add_argument("--observed-a0-digest", required=True)
    args = parser.parse_args(argv)
    try:
        compiled = compile_task_spec(
            _load_json(args.spec), observed_a0_digest=args.observed_a0_digest
        )
    except (OSError, json.JSONDecodeError, TaskSpecError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "source_spec_digest": compiled.source_spec_digest,
                "compiler_version": compiled.summary.compiler_version,
                "compiler_digest": compiled.summary.compiler_digest,
                "summary_digest": compiled.summary.summary_digest,
                "compilation_digest": compiled.compilation_digest,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
