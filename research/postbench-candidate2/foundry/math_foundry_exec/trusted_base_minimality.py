"""Bounded exhaustive trusted-base minimality evidence.

This module can establish global minimality only over an explicit finite,
content-bound trusted dependency universe.  It does not claim a globally
minimum proof basis outside that frozen universe.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Mapping

from .canonical import digest
from .formalization_evidence import ROLE_DEPENDENCY_CHECKER, VerificationAuthority
from .theory_graph import ComparatorManifest, TheoryGraph, TRUSTED_BASE

PROVES = "PROVES"
DOES_NOT_PROVE = "DOES_NOT_PROVE"
UNKNOWN = "UNKNOWN"
RESULTS = {PROVES, DOES_NOT_PROVE, UNKNOWN}

GLOBAL_MINIMUM_PASS = "GLOBAL_MINIMUM_PASS"
GLOBAL_MINIMUM_FAIL = "GLOBAL_MINIMUM_FAIL"
GLOBAL_MINIMUM_UNKNOWN = "GLOBAL_MINIMUM_UNKNOWN"


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _bound(instance: object, field: str) -> bool:
    try:
        rebound = instance.bound()  # type: ignore[attr-defined]
    except Exception:
        return False
    return bool(getattr(instance, field, "")) and rebound == instance


def _subsets(universe: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    rows: list[tuple[str, ...]] = []
    for size in range(len(universe) + 1):
        rows.extend(tuple(row) for row in combinations(universe, size))
    return tuple(rows)


@dataclass(frozen=True)
class TrustedBaseSearchSpace:
    graph_id: str
    comparator_manifest_id: str
    eligible_dependency_ids: tuple[str, ...]
    max_universe_size: int
    search_space_id: str = ""

    def bound(self) -> "TrustedBaseSearchSpace":
        if not _is_sha256(self.graph_id) or not _is_sha256(self.comparator_manifest_id):
            raise ValueError("TRUSTED_BASE_SEARCH_SPACE_BINDING_INVALID")
        eligible = tuple(sorted(set(self.eligible_dependency_ids)))
        if not all(_is_sha256(value) for value in eligible):
            raise ValueError("TRUSTED_BASE_SEARCH_SPACE_DEPENDENCY_INVALID")
        if not eligible:
            raise ValueError("TRUSTED_BASE_SEARCH_SPACE_EMPTY")
        if self.max_universe_size < 1 or len(eligible) > self.max_universe_size:
            raise ValueError("TRUSTED_BASE_SEARCH_SPACE_LIMIT_EXCEEDED")
        core = {
            "graph_id": self.graph_id,
            "comparator_manifest_id": self.comparator_manifest_id,
            "eligible_dependency_ids": eligible,
            "max_universe_size": int(self.max_universe_size),
        }
        return TrustedBaseSearchSpace(**core, search_space_id=digest(core))


@dataclass(frozen=True)
class ExhaustiveTrustedBaseReceipt:
    search_space_id: str
    authority_id: str
    checker_implementation_digest: str
    producer_implementation_digest: str
    subset_results: tuple[tuple[tuple[str, ...], str], ...]
    evidence_digests: tuple[str, ...]
    receipt_id: str = ""

    def bound(self) -> "ExhaustiveTrustedBaseReceipt":
        for value in (
            self.search_space_id,
            self.authority_id,
            self.checker_implementation_digest,
            self.producer_implementation_digest,
        ):
            if not _is_sha256(value):
                raise ValueError("TRUSTED_BASE_RECEIPT_BINDING_INVALID")
        normalized: list[tuple[tuple[str, ...], str]] = []
        seen: set[tuple[str, ...]] = set()
        for subset, result in self.subset_results:
            key = tuple(sorted(set(subset)))
            if key in seen:
                raise ValueError("TRUSTED_BASE_RECEIPT_DUPLICATE_SUBSET")
            if not all(_is_sha256(value) for value in key) or result not in RESULTS:
                raise ValueError("TRUSTED_BASE_RECEIPT_RESULT_INVALID")
            seen.add(key)
            normalized.append((key, result))
        evidence = tuple(sorted(set(self.evidence_digests)))
        if not evidence or not all(_is_sha256(value) for value in evidence):
            raise ValueError("TRUSTED_BASE_RECEIPT_EVIDENCE_INVALID")
        normalized_tuple = tuple(sorted(normalized, key=lambda row: (len(row[0]), row[0], row[1])))
        core = {
            "search_space_id": self.search_space_id,
            "authority_id": self.authority_id,
            "checker_implementation_digest": self.checker_implementation_digest,
            "producer_implementation_digest": self.producer_implementation_digest,
            "subset_results": normalized_tuple,
            "evidence_digests": evidence,
        }
        return ExhaustiveTrustedBaseReceipt(**core, receipt_id=digest(core))


@dataclass(frozen=True)
class BoundedGlobalMinimalityAssessment:
    search_space_id: str
    receipt_id: str
    status: str
    minimum_cardinality: int | None
    declared_dependency_ids: tuple[str, ...]
    minimum_dependency_sets: tuple[tuple[str, ...], ...]
    reasons: tuple[str, ...]
    assessment_id: str = ""

    def bound(self) -> "BoundedGlobalMinimalityAssessment":
        if not _is_sha256(self.search_space_id) or not _is_sha256(self.receipt_id):
            raise ValueError("GLOBAL_MINIMALITY_ASSESSMENT_BINDING_INVALID")
        if self.status not in {GLOBAL_MINIMUM_PASS, GLOBAL_MINIMUM_FAIL, GLOBAL_MINIMUM_UNKNOWN}:
            raise ValueError("GLOBAL_MINIMALITY_ASSESSMENT_STATUS_INVALID")
        declared = tuple(sorted(set(self.declared_dependency_ids)))
        minima = tuple(sorted({tuple(sorted(set(row))) for row in self.minimum_dependency_sets}))
        core = {
            "search_space_id": self.search_space_id,
            "receipt_id": self.receipt_id,
            "status": self.status,
            "minimum_cardinality": self.minimum_cardinality,
            "declared_dependency_ids": declared,
            "minimum_dependency_sets": minima,
            "reasons": tuple(sorted(set(self.reasons))),
        }
        return BoundedGlobalMinimalityAssessment(**core, assessment_id=digest(core))


def build_trusted_base_search_space(
    graph: TheoryGraph,
    manifest: ComparatorManifest,
    *,
    max_universe_size: int = 12,
) -> TrustedBaseSearchSpace:
    if graph.graph_id != manifest.graph_id:
        raise ValueError("TRUSTED_BASE_SEARCH_GRAPH_MANIFEST_MISMATCH")
    eligible = tuple(sorted(node.node_id for node in graph.nodes if node.trust_class == TRUSTED_BASE))
    if not set(manifest.trusted_dependency_ids).issubset(set(eligible)):
        raise ValueError("DECLARED_TRUSTED_BASE_OUTSIDE_SEARCH_UNIVERSE")
    return TrustedBaseSearchSpace(
        graph_id=graph.graph_id,
        comparator_manifest_id=manifest.manifest_id,
        eligible_dependency_ids=eligible,
        max_universe_size=max_universe_size,
    ).bound()


def assess_bounded_global_trusted_base_minimality(
    *,
    search_space: TrustedBaseSearchSpace,
    manifest: ComparatorManifest,
    receipt: ExhaustiveTrustedBaseReceipt,
    authority_registry: Mapping[str, VerificationAuthority],
    candidate_producer_implementation_digest: str,
) -> BoundedGlobalMinimalityAssessment:
    reasons: list[str] = []
    status = GLOBAL_MINIMUM_PASS
    if not _bound(search_space, "search_space_id"):
        reasons.append("TRUSTED_BASE_SEARCH_SPACE_NOT_CONTENT_BOUND")
        status = GLOBAL_MINIMUM_UNKNOWN
    if not _bound(receipt, "receipt_id"):
        reasons.append("TRUSTED_BASE_EXHAUSTIVE_RECEIPT_NOT_CONTENT_BOUND")
        status = GLOBAL_MINIMUM_UNKNOWN
    if search_space.comparator_manifest_id != manifest.manifest_id:
        reasons.append("TRUSTED_BASE_SEARCH_MANIFEST_MISMATCH")
        status = GLOBAL_MINIMUM_UNKNOWN
    if receipt.search_space_id != search_space.search_space_id:
        reasons.append("TRUSTED_BASE_RECEIPT_SEARCH_SPACE_MISMATCH")
        status = GLOBAL_MINIMUM_UNKNOWN
    if receipt.producer_implementation_digest != candidate_producer_implementation_digest:
        reasons.append("TRUSTED_BASE_PRODUCER_IMPLEMENTATION_MISMATCH")
        status = GLOBAL_MINIMUM_FAIL

    authority = authority_registry.get(receipt.authority_id)
    if authority is None:
        reasons.append("TRUSTED_BASE_AUTHORITY_NOT_REGISTERED")
        status = GLOBAL_MINIMUM_UNKNOWN
    else:
        if not _bound(authority, "authority_id") or authority.authority_id != receipt.authority_id:
            reasons.append("TRUSTED_BASE_AUTHORITY_NOT_CONTENT_BOUND")
            status = GLOBAL_MINIMUM_UNKNOWN
        if not authority.authorizes(ROLE_DEPENDENCY_CHECKER):
            reasons.append("TRUSTED_BASE_AUTHORITY_ROLE_NOT_GRANTED")
            status = GLOBAL_MINIMUM_UNKNOWN
        if authority.subject_implementation_digest != receipt.checker_implementation_digest:
            reasons.append("TRUSTED_BASE_CHECKER_IMPLEMENTATION_NOT_AUTHORIZED")
            status = GLOBAL_MINIMUM_UNKNOWN
        if authority.subject_implementation_digest == candidate_producer_implementation_digest:
            reasons.append("TRUSTED_BASE_CHECKER_NOT_IMPLEMENTATION_INDEPENDENT")
            status = GLOBAL_MINIMUM_FAIL

    universe = search_space.eligible_dependency_ids
    expected = set(_subsets(universe))
    observed_map = {tuple(subset): result for subset, result in receipt.subset_results}
    observed = set(observed_map)
    if observed != expected:
        missing = len(expected - observed)
        extra = len(observed - expected)
        reasons.append(f"TRUSTED_BASE_EXHAUSTIVE_COVERAGE_MISMATCH:missing={missing}:extra={extra}")
        status = GLOBAL_MINIMUM_UNKNOWN
    elif any(result == UNKNOWN for result in observed_map.values()):
        reasons.append("TRUSTED_BASE_EXHAUSTIVE_SEARCH_CONTAINS_UNKNOWN")
        status = GLOBAL_MINIMUM_UNKNOWN

    proving = tuple(sorted((subset for subset, result in observed_map.items() if result == PROVES), key=lambda x: (len(x), x)))
    minimum_cardinality: int | None = None
    minima: tuple[tuple[str, ...], ...] = ()
    if status != GLOBAL_MINIMUM_UNKNOWN:
        if not proving:
            reasons.append("TRUSTED_BASE_EXHAUSTIVE_SEARCH_FOUND_NO_PROVING_BASE")
            status = GLOBAL_MINIMUM_FAIL
        else:
            minimum_cardinality = len(proving[0])
            minima = tuple(row for row in proving if len(row) == minimum_cardinality)
            declared = tuple(sorted(set(manifest.trusted_dependency_ids)))
            if observed_map.get(declared) != PROVES:
                reasons.append("DECLARED_TRUSTED_BASE_NOT_PROVING_IN_EXHAUSTIVE_RECEIPT")
                status = GLOBAL_MINIMUM_FAIL
            elif len(declared) != minimum_cardinality:
                reasons.append("SMALLER_PROVING_TRUSTED_BASE_EXISTS")
                status = GLOBAL_MINIMUM_FAIL
            elif declared not in minima:
                reasons.append("DECLARED_TRUSTED_BASE_NOT_GLOBAL_MINIMUM")
                status = GLOBAL_MINIMUM_FAIL

    return BoundedGlobalMinimalityAssessment(
        search_space_id=search_space.search_space_id,
        receipt_id=receipt.receipt_id,
        status=status,
        minimum_cardinality=minimum_cardinality,
        declared_dependency_ids=manifest.trusted_dependency_ids,
        minimum_dependency_sets=minima,
        reasons=tuple(reasons),
    ).bound()
