"""Automatic Research Discovery with typed retrieval diagnosis and scoped evidence.

Retrieval is not factual verification. Search receipts remain ``UNKNOWN`` until selected
sources are inspected and recorded in a claim-scoped source-assessment receipt. A
negative search result is always ``NOT_FOUND_WITHIN_SCOPE``, never nonexistence.

A load-bearing plan may freeze query hypotheses before execution. After zero novel yield,
Space automatically executes at most one non-redundant mechanism-level reframe while
recording task, obligation, plan, parent-query, challenge, query-class, outcome, and
registered-scope lineage. The challenge layer can be disabled to recover baseline search
behavior; it never creates factual warrant.
"""
from __future__ import annotations

import copy
import json
import re
import time
import unicodedata
import urllib.parse
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

import requests
from egrt_challenge import ChallengeError, ChallengePolicy, propose_challenge
from egrt_challenge_types import ChallengeKind, ChallengeOrigin, ChallengeRequest
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import (
    ArtifactRef,
    EvidenceClass,
    EvidenceRef,
    ObligationKind,
    Receipt,
    Verdict,
    digest,
)

UA = "Evidence-Governed-Research-Toolkit/vnext (+https://github.com/Kitahl/The-Gauntlet)"
SPACE_SCHEMA = "egrt.space.v2"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class QueryClass(str, Enum):
    TERMINOLOGY_MISMATCH = "TERMINOLOGY_MISMATCH"
    REPRESENTATION_MISMATCH = "REPRESENTATION_MISMATCH"
    SOURCE_ADAPTER_GAP = "SOURCE_ADAPTER_GAP"
    QUERY_TOO_NARROW = "QUERY_TOO_NARROW"
    QUERY_TOO_BROAD = "QUERY_TOO_BROAD"
    NEIGHBOR_FIELD_MISSED = "NEIGHBOR_FIELD_MISSED"
    CITATION_CHAIN_NOT_TRAVERSED = "CITATION_CHAIN_NOT_TRAVERSED"
    DERIVATIVE_SOURCE_COLLISION = "DERIVATIVE_SOURCE_COLLISION"
    STALE_SOURCE = "STALE_SOURCE"
    TRUE_NOT_FOUND_WITHIN_REGISTERED_SCOPE = (
        "TRUE_NOT_FOUND_WITHIN_REGISTERED_SCOPE"
    )


class ReframeOutcome(str, Enum):
    BASE_EXECUTED = "BASE_EXECUTED"
    NOVEL_YIELD = "NOVEL_YIELD"
    NO_NOVEL_YIELD = "NO_NOVEL_YIELD"
    UNAVAILABLE = "UNAVAILABLE"
    REJECTED_REDUNDANT = "REJECTED_REDUNDANT"
    SKIPPED_CHALLENGE_OFF = "SKIPPED_CHALLENGE_OFF"
    SKIPPED_UNBOUND = "SKIPPED_UNBOUND"
    CHALLENGE_UNAVAILABLE = "CHALLENGE_UNAVAILABLE"


class SpaceAuthorityError(ValueError):
    """Raised when a SearchPlan cannot be bound to its current DISCOVERY authority."""


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_optional_text(name: str, value: object) -> None:
    if value is not None:
        _require_text(name, value)


def _require_hash(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def normalize_query(query: str) -> str:
    """Return the exact-repeat comparison form; this is not semantic equivalence."""

    _require_text("query", query)
    normalized = unicodedata.normalize("NFKC", query)
    return re.sub(r"\s+", " ", normalized.strip()).casefold()


def canonical_query_hash(query: str) -> str:
    return digest(normalize_query(query))


@dataclass(frozen=True)
class QueryHypothesis:
    """One frozen, task-local explanation and discriminator for retrieval failure."""

    hypothesis_id: str
    search_plan_id: str
    obligation_id: str
    parent_query_hash: str
    query_class: QueryClass
    reframe_query: str
    task_id: str | None = None
    sources: tuple[str, ...] = ()
    registered_scope_hash: str | None = None
    trigger: str = "ZERO_YIELD_OR_SCOPED_ABSENCE"
    expected_discriminator: str = "MEASURE_NOVEL_YIELD"
    load_bearing: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = SPACE_SCHEMA

    def __post_init__(self) -> None:
        for name in (
            "hypothesis_id",
            "search_plan_id",
            "obligation_id",
            "reframe_query",
            "trigger",
            "expected_discriminator",
        ):
            _require_text(name, getattr(self, name))
        _require_optional_text("task_id", self.task_id)
        _require_hash("parent_query_hash", self.parent_query_hash)
        if self.registered_scope_hash is not None:
            _require_hash("registered_scope_hash", self.registered_scope_hash)
        if not isinstance(self.query_class, QueryClass):
            raise TypeError("query_class must be QueryClass")
        if not isinstance(self.sources, tuple):
            raise TypeError("sources must be tuple")
        if any(not isinstance(source, str) or not source.strip() for source in self.sources):
            raise ValueError("hypothesis sources must be non-empty strings")
        if len(self.sources) != len(set(self.sources)):
            raise ValueError("hypothesis sources must be unique")
        if not isinstance(self.load_bearing, bool):
            raise TypeError("load_bearing must be bool")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be dict")
        if self.schema != SPACE_SCHEMA:
            raise ValueError(f"schema must be {SPACE_SCHEMA}")
        normalize_query(self.reframe_query)


@dataclass(frozen=True)
class QueryRoundState:
    """Persisted hash-only lineage for one executed or rejected query round."""

    round_id: str
    task_id: str | None
    obligation_id: str
    search_plan_id: str
    query_hash: str
    parent_query_hash: str | None
    challenge_id: str | None
    query_class: QueryClass | None
    reframe_outcome: ReframeOutcome
    registered_scope_hash: str
    hypothesis_id: str | None
    sources: tuple[str, ...]
    novel_yield: int
    total_results: int
    attempted_calls: int
    successful_calls: int
    counted_as_round: bool
    error_types: tuple[str, ...] = ()
    schema: str = SPACE_SCHEMA

    def __post_init__(self) -> None:
        for name in ("round_id", "obligation_id", "search_plan_id"):
            _require_text(name, getattr(self, name))
        _require_optional_text("task_id", self.task_id)
        _require_optional_text("challenge_id", self.challenge_id)
        _require_optional_text("hypothesis_id", self.hypothesis_id)
        _require_hash("query_hash", self.query_hash)
        if self.parent_query_hash is not None:
            _require_hash("parent_query_hash", self.parent_query_hash)
        _require_hash("registered_scope_hash", self.registered_scope_hash)
        if self.query_class is not None and not isinstance(self.query_class, QueryClass):
            raise TypeError("query_class must be QueryClass or None")
        if not isinstance(self.reframe_outcome, ReframeOutcome):
            raise TypeError("reframe_outcome must be ReframeOutcome")
        for name in (
            "novel_yield",
            "total_results",
            "attempted_calls",
            "successful_calls",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if self.successful_calls > self.attempted_calls:
            raise ValueError("successful_calls cannot exceed attempted_calls")
        if self.novel_yield > self.total_results:
            raise ValueError("novel_yield cannot exceed total_results")
        if not isinstance(self.sources, tuple) or any(
            not isinstance(source, str) or not source.strip() for source in self.sources
        ):
            raise ValueError("round sources must be a tuple of non-empty strings")
        if len(self.sources) != len(set(self.sources)):
            raise ValueError("round sources must be unique")
        if not isinstance(self.error_types, tuple) or any(
            not isinstance(error_type, str) or not error_type.strip()
            for error_type in self.error_types
        ):
            raise ValueError("error_types must be a tuple of non-empty strings")
        if not isinstance(self.counted_as_round, bool):
            raise TypeError("counted_as_round must be bool")
        if self.schema != SPACE_SCHEMA:
            raise ValueError(f"schema must be {SPACE_SCHEMA}")


@dataclass(frozen=True)
class SearchPlan:
    plan_id: str
    obligation_id: str
    question: str
    queries: tuple[str, ...]
    sources: tuple[str, ...] = ("openalex", "crossref")
    inclusion: tuple[str, ...] = ()
    exclusion: tuple[str, ...] = ()
    max_results_per_query: int = 10
    max_queries: int = 12
    saturation_queries: int = 2
    metadata: dict[str, Any] = field(default_factory=dict)
    query_hypotheses: tuple[QueryHypothesis, ...] = ()
    task_id: str | None = None
    candidate_hash: str | None = None
    scope_hash: str | None = None
    automatic_reframe: bool = True
    schema: str = SPACE_SCHEMA

    def __post_init__(self) -> None:
        for name in ("plan_id", "obligation_id", "question"):
            _require_text(name, getattr(self, name))
        _require_optional_text("task_id", self.task_id)
        if not isinstance(self.queries, tuple) or not self.queries:
            raise ValueError("SearchPlan requires at least one frozen query tuple")
        normalized = [normalize_query(query) for query in self.queries]
        if len(normalized) != len(set(normalized)):
            raise ValueError("SearchPlan queries must be unique after exact normalization")
        if not isinstance(self.sources, tuple) or not self.sources:
            raise ValueError("SearchPlan requires at least one source index tuple")
        if any(not isinstance(source, str) or not source.strip() for source in self.sources):
            raise ValueError("SearchPlan sources must be non-empty strings")
        if len(self.sources) != len(set(self.sources)):
            raise ValueError("SearchPlan source indexes must be unique")
        if self.max_results_per_query < 1 or self.max_queries < 1:
            raise ValueError("search limits must be positive")
        if self.saturation_queries < 1:
            raise ValueError("saturation_queries must be positive")
        if not isinstance(self.query_hypotheses, tuple):
            raise TypeError("query_hypotheses must be tuple")
        if any(not isinstance(item, QueryHypothesis) for item in self.query_hypotheses):
            raise TypeError("query_hypotheses must contain QueryHypothesis values")
        hypothesis_ids = [item.hypothesis_id for item in self.query_hypotheses]
        if len(hypothesis_ids) != len(set(hypothesis_ids)):
            raise ValueError("query hypothesis identifiers must be unique")
        load_bearing_parents = [
            item.parent_query_hash for item in self.query_hypotheses if item.load_bearing
        ]
        if len(load_bearing_parents) != len(set(load_bearing_parents)):
            raise ValueError(
                "at most one load-bearing query hypothesis may bind each base query"
            )
        base_hashes = {canonical_query_hash(query) for query in self.queries}
        for hypothesis in self.query_hypotheses:
            if hypothesis.search_plan_id != self.plan_id:
                raise ValueError("query hypothesis search_plan_id mismatch")
            if hypothesis.obligation_id != self.obligation_id:
                raise ValueError("query hypothesis obligation_id mismatch")
            if hypothesis.parent_query_hash not in base_hashes:
                raise ValueError("query hypothesis parent is outside the frozen base queries")
            if self.task_id and hypothesis.task_id and hypothesis.task_id != self.task_id:
                raise ValueError("query hypothesis task_id mismatch")
        for name in ("candidate_hash", "scope_hash"):
            value = getattr(self, name)
            if value is not None:
                _require_hash(name, value)
        if not isinstance(self.automatic_reframe, bool):
            raise TypeError("automatic_reframe must be bool")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be dict")
        if self.schema != SPACE_SCHEMA:
            raise ValueError(f"schema must be {SPACE_SCHEMA}")


@dataclass(frozen=True)
class SourceAssessment:
    assessment_id: str
    source: ArtifactRef
    relation: str  # SUPPORTS | REFUTES | CONTEXT_ONLY
    verifier: str
    claim_scope: str
    provenance_group: str | None = None
    notes_hash: str | None = None

    def __post_init__(self) -> None:
        for name in ("assessment_id", "verifier", "claim_scope"):
            _require_text(name, getattr(self, name))
        if not isinstance(self.source, ArtifactRef):
            raise TypeError("source must be ArtifactRef")
        if not self.source.sha256:
            raise ValueError("assessed source requires a content SHA-256")
        relation = self.relation.upper()
        if relation not in {"SUPPORTS", "REFUTES", "CONTEXT_ONLY"}:
            raise ValueError("source relation must be SUPPORTS, REFUTES, or CONTEXT_ONLY")
        _require_optional_text("provenance_group", self.provenance_group)
        _require_optional_text("notes_hash", self.notes_hash)


@dataclass(frozen=True)
class _TaskBinding:
    task_id: str
    task_content_hash: str
    obligation_binding_hash: str
    obligation_set_hash: str
    load_bearing: bool
    lineage: tuple[str, ...]


def _norm_doi(value: str | None) -> str | None:
    if not value:
        return None
    low = value.strip().lower()
    low = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", low)
    return low or None


def _norm_title(title: str | None) -> str:
    return re.sub(r"\W+", " ", (title or "").lower()).strip()


def _key(row: Mapping[str, Any]) -> str:
    return str(
        _norm_doi(row.get("doi"))
        or row.get("openalex")
        or row.get("url")
        or _norm_title(row.get("title"))
    )


def search_openalex(
    query: str,
    limit: int,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"search": query, "per-page": max(1, min(limit, 25))})
    response = requests.get(
        f"https://api.openalex.org/works?{params}",
        headers={"User-Agent": UA},
        timeout=timeout,
    )
    response.raise_for_status()
    out = []
    for work in response.json().get("results", [])[:limit]:
        primary = work.get("primary_location") or {}
        source = primary.get("source") or {}
        out.append(
            {
                "title": work.get("display_name"),
                "year": work.get("publication_year"),
                "doi": _norm_doi(work.get("doi")),
                "openalex": work.get("id"),
                "url": work.get("id"),
                "venue": source.get("display_name"),
                "source_index": "openalex",
            }
        )
    return out


def search_crossref(
    query: str,
    limit: int,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {"query.bibliographic": query, "rows": max(1, min(limit, 25))}
    )
    response = requests.get(
        f"https://api.crossref.org/works?{params}",
        headers={"User-Agent": UA},
        timeout=timeout,
    )
    response.raise_for_status()
    out = []
    for item in response.json().get("message", {}).get("items", [])[:limit]:
        title = (item.get("title") or [None])[0]
        year_parts = (
            (
                (item.get("published-print") or item.get("published-online") or {}).get(
                    "date-parts"
                )
                or [[None]]
            )[0]
        )
        out.append(
            {
                "title": title,
                "year": year_parts[0] if year_parts else None,
                "doi": _norm_doi(item.get("DOI")),
                "url": item.get("URL"),
                "venue": (item.get("container-title") or [None])[0],
                "source_index": "crossref",
            }
        )
    return out


ADAPTERS = {"openalex": search_openalex, "crossref": search_crossref}


def _merge_seen(seen: dict[str, dict[str, Any]], row: Mapping[str, Any]) -> bool:
    key = _key(row)
    if not key:
        return False
    if key not in seen:
        copied = dict(row)
        copied["source_indexes"] = sorted({str(row.get("source_index") or "unknown")})
        seen[key] = copied
        return True
    source_indexes = set(seen[key].get("source_indexes") or [])
    source_indexes.add(str(row.get("source_index") or "unknown"))
    seen[key]["source_indexes"] = sorted(source_indexes)
    for field_name in ("doi", "openalex", "url", "year", "venue", "title"):
        if not seen[key].get(field_name) and row.get(field_name):
            seen[key][field_name] = row[field_name]
    return False


def _obligation_row(
    task: Mapping[str, Any],
    obligation_id: str,
) -> Mapping[str, Any] | None:
    return next(
        (
            row
            for row in task.get("obligations", [])
            if isinstance(row, Mapping) and row.get("obligation_id") == obligation_id
        ),
        None,
    )


def _follow_current_task(
    store: RuntimeStore,
    task_id: str,
) -> tuple[str, dict[str, Any], tuple[str, ...]]:
    current_id = task_id
    lineage = [task_id]
    seen = {task_id}
    while True:
        task = store.read_task(current_id)
        if task is None:
            raise SpaceAuthorityError("bound task is missing or integrity-invalid")
        metadata = task.get("metadata") if isinstance(task.get("metadata"), Mapping) else {}
        successor = metadata.get("soul_superseded_by")
        if not isinstance(successor, str) or not successor:
            return current_id, task, tuple(lineage)
        if successor in seen:
            raise SpaceAuthorityError("task supersession lineage contains a cycle")
        if task.get("active", True) is True or task.get("released", False) is True:
            raise SpaceAuthorityError("invalid superseded task state")
        next_task = store.read_task(successor)
        if next_task is None:
            raise SpaceAuthorityError("task supersession successor is missing or corrupt")
        next_metadata = (
            next_task.get("metadata")
            if isinstance(next_task.get("metadata"), Mapping)
            else {}
        )
        if next_metadata.get("soul_supersedes") != current_id:
            raise SpaceAuthorityError("task supersession reverse binding mismatch")
        current_id = successor
        lineage.append(successor)
        seen.add(successor)


def _resolve_task_binding(
    store: RuntimeStore,
    task_id: str | None,
    obligation_id: str,
) -> _TaskBinding | None:
    if task_id is not None:
        current_id, task, lineage = _follow_current_task(store, task_id)
    else:
        active: list[tuple[str, dict[str, Any]]] = []
        for path in sorted(store.tasks.glob("*.json")):
            candidate_id = path.stem
            candidate = store.read_task(candidate_id)
            if candidate is None or _obligation_row(candidate, obligation_id) is None:
                continue
            if candidate.get("active", True) is True and candidate.get("released", False) is False:
                active.append((candidate_id, candidate))
        if not active:
            return None
        if len(active) > 1:
            raise SpaceAuthorityError(
                "discovery obligation is ambiguously bound to multiple active tasks"
            )
        current_id, task = active[0]
        lineage = (current_id,)

    if task.get("active", True) is not True or task.get("released", False) is True:
        raise SpaceAuthorityError("Space requires the current active unreleased task revision")
    row = _obligation_row(task, obligation_id)
    if row is None:
        raise SpaceAuthorityError("discovery obligation is outside the current task revision")
    if row.get("kind") != ObligationKind.DISCOVERY.value:
        raise SpaceAuthorityError("Space may clear only a DISCOVERY obligation")
    if row.get("required_module") not in (None, "space"):
        raise SpaceAuthorityError("discovery obligation is assigned to another module")
    metadata = task.get("metadata") if isinstance(task.get("metadata"), Mapping) else {}
    obligation_set_hash = metadata.get("soul_obligation_set_hash")
    if not isinstance(obligation_set_hash, str) or not _SHA256.fullmatch(obligation_set_hash):
        obligation_set_hash = digest(task.get("obligations", []))
    return _TaskBinding(
        task_id=current_id,
        task_content_hash=str(task.get("content_hash") or digest(task)),
        obligation_binding_hash=digest(row),
        obligation_set_hash=obligation_set_hash,
        load_bearing=bool(row.get("load_bearing", True)),
        lineage=lineage,
    )


def _registered_scope_hash(plan: SearchPlan) -> str:
    return plan.scope_hash or digest(
        {
            "queries": [canonical_query_hash(query) for query in plan.queries[: plan.max_queries]],
            "sources": plan.sources,
            "inclusion": plan.inclusion,
            "exclusion": plan.exclusion,
            "limits": {
                "max_results_per_query": plan.max_results_per_query,
                "max_queries": plan.max_queries,
                "saturation_queries": plan.saturation_queries,
                "max_automatic_reframes": 1,
            },
            "hypotheses": [
                {
                    "hypothesis_id": item.hypothesis_id,
                    "query_class": item.query_class.value,
                    "parent_query_hash": item.parent_query_hash,
                    "reframe_query_hash": canonical_query_hash(item.reframe_query),
                    "sources": item.sources,
                    "load_bearing": item.load_bearing,
                    "metadata_hash": digest(item.metadata),
                }
                for item in plan.query_hypotheses
            ],
        }
    )


def _candidate_hash(plan: SearchPlan) -> str:
    return plan.candidate_hash or digest(
        {
            "plan_id": plan.plan_id,
            "obligation_id": plan.obligation_id,
            "question_hash": digest(plan.question),
        }
    )


def _round_record(state: QueryRoundState) -> dict[str, Any]:
    row = asdict(state)
    row["query_class"] = state.query_class.value if state.query_class else None
    row["reframe_outcome"] = state.reframe_outcome.value
    row["novel"] = state.novel_yield  # compatibility with the v1 runtime result shape
    return row


def _execute_query(
    query: str,
    sources: tuple[str, ...],
    limit: int,
    seen: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    query_digest = canonical_query_hash(query)
    attempted_calls = 0
    successful_calls = 0
    errors: list[dict[str, str]] = []
    novel_before = len(seen)
    for source in sources:
        attempted_calls += 1
        adapter = ADAPTERS.get(source)
        if adapter is None:
            errors.append(
                {
                    "source": source,
                    "query_hash": query_digest,
                    "error": "UNAVAILABLE_ADAPTER",
                }
            )
            continue
        try:
            rows = adapter(query, limit)
            successful_calls += 1
        except requests.RequestException as exc:
            errors.append(
                {
                    "source": source,
                    "query_hash": query_digest,
                    "error": type(exc).__name__,
                }
            )
            continue
        if not isinstance(rows, list):
            raise TypeError("Space adapters must return list[dict]")
        for raw_row in rows:
            if not isinstance(raw_row, Mapping):
                raise TypeError("Space adapter rows must be mappings")
            row = dict(raw_row)
            row.setdefault("source_index", source)
            _merge_seen(seen, row)
    return {
        "query_hash": query_digest,
        "novel_yield": len(seen) - novel_before,
        "total_results": len(seen),
        "attempted_calls": attempted_calls,
        "successful_calls": successful_calls,
        "errors": errors,
    }


def _propose_native_challenge(
    root: Path,
    binding: _TaskBinding | None,
    *,
    obligation_id: str,
    candidate_hash: str,
    scope_hash: str,
    kind: ChallengeKind,
    hypothesis: str,
    alternative: str,
    refuter: str,
    consequence: str,
    required_capability: str,
    load_bearing: bool,
    metadata: dict[str, Any],
) -> tuple[str | None, str]:
    if binding is None:
        return None, "UNBOUND"
    policy = ChallengePolicy.from_root(root)
    if policy.mode == "off":
        return None, "OFF"
    request = ChallengeRequest(
        challenge_id=new_id("chal"),
        task_id=binding.task_id,
        obligation_id=obligation_id,
        target_module="space",
        origin=ChallengeOrigin.MODULE_NATIVE,
        kind=kind,
        hypothesis=hypothesis,
        alternative=alternative,
        refuter=refuter,
        consequence_if_true=consequence,
        load_bearing=load_bearing,
        required_capability=required_capability,
        candidate_hash=candidate_hash,
        scope_hash=scope_hash,
        obligation_set_hash=binding.obligation_set_hash,
        proposer="space_runtime:auto-challenge",
        proposer_provenance="space_runtime:v2",
        information_rank=5 if load_bearing else 3,
        risk_rank=5 if load_bearing else 3,
        cost_rank=2,
        metadata=metadata,
    )
    try:
        propose_challenge(root, request)
    except ChallengeError:
        return None, "REJECTED"
    return request.challenge_id, "PROPOSED"


def _start_reframe_challenge(
    root: Path,
    challenge_id: str,
    hypothesis: QueryHypothesis,
) -> None:
    store = RuntimeStore(root)
    store.update_challenge_state(
        challenge_id,
        "SELECTED",
        selected_plan={
            "plan_id": f"space-reframe-{hypothesis.hypothesis_id}",
            "challenge_id": challenge_id,
            "mode": "AUTOMATIC_BOUNDED_REFRAME",
            "action": "execute frozen non-redundant retrieval reframe",
            "verifier_module": "space",
            "required_capability": "SCHOLARLY_SEARCH",
        },
        reason="minimum frozen task-local retrieval discriminator",
        component="space",
    )
    store.update_challenge_state(
        challenge_id,
        "RUNNING",
        reason="executing one bounded registered reframe",
        component="space",
    )


def _finish_reframe_challenge(
    root: Path,
    challenge_id: str,
    *,
    successful_calls: int,
    novel_yield: int,
) -> None:
    store = RuntimeStore(root)
    if successful_calls == 0:
        store.update_challenge_state(
            challenge_id,
            "UNAVAILABLE",
            reason="all registered adapters for the reframe were unavailable",
            component="space",
        )
    elif novel_yield:
        store.update_challenge_state(
            challenge_id,
            "UNRESOLVED",
            reason="novel candidates require claim-scoped source assessment",
            component="space",
        )
    else:
        store.update_challenge_state(
            challenge_id,
            "UNRESOLVED",
            reason="no novel yield; scoped absence remains unknown",
            component="space",
        )


def run_plan(root: Path, plan: SearchPlan) -> tuple[Receipt, dict[str, Any]]:
    """Execute a frozen plan and at most one automatic task-bound reframe."""

    if not isinstance(plan, SearchPlan):
        raise TypeError("plan must be SearchPlan")
    plan = copy.deepcopy(plan)
    store = RuntimeStore(root)
    binding = _resolve_task_binding(store, plan.task_id, plan.obligation_id)
    registered_scope_hash = _registered_scope_hash(plan)
    candidate_hash = _candidate_hash(plan)
    accepted_task_ids = set(binding.lineage) if binding else set()
    for hypothesis in plan.query_hypotheses:
        if hypothesis.task_id is not None and hypothesis.task_id not in accepted_task_ids:
            raise SpaceAuthorityError("query hypothesis task binding is stale or mismatched")
        if (
            hypothesis.registered_scope_hash is not None
            and hypothesis.registered_scope_hash != registered_scope_hash
        ):
            raise SpaceAuthorityError("query hypothesis registered scope binding mismatch")

    seen: dict[str, dict[str, Any]] = {}
    rounds: list[dict[str, Any]] = []
    reframe_diagnostics: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    attempted_calls = 0
    successful_calls = 0
    zero_novel_queries = 0
    reframe_considered = False
    reframe_executed = False
    reframe_successful_calls = 0
    selected_hypothesis: QueryHypothesis | None = None
    selected_challenge_id: str | None = None
    started = time.monotonic()
    frozen_queries = plan.queries[: plan.max_queries]
    frozen_base_hashes = {canonical_query_hash(query) for query in frozen_queries}
    executed_hashes: set[str] = set()
    load_bearing = binding.load_bearing if binding else bool(
        plan.metadata.get("load_bearing", True)
    )

    for query in frozen_queries:
        execution = _execute_query(query, plan.sources, plan.max_results_per_query, seen)
        executed_hashes.add(str(execution["query_hash"]))
        attempted_calls += int(execution["attempted_calls"])
        successful_calls += int(execution["successful_calls"])
        errors.extend(execution["errors"])
        base_round = QueryRoundState(
            round_id=f"{plan.plan_id}:round-{len(rounds) + 1}",
            task_id=binding.task_id if binding else None,
            obligation_id=plan.obligation_id,
            search_plan_id=plan.plan_id,
            query_hash=str(execution["query_hash"]),
            parent_query_hash=None,
            challenge_id=None,
            query_class=None,
            reframe_outcome=ReframeOutcome.BASE_EXECUTED,
            registered_scope_hash=registered_scope_hash,
            hypothesis_id=None,
            sources=plan.sources,
            novel_yield=int(execution["novel_yield"]),
            total_results=int(execution["total_results"]),
            attempted_calls=int(execution["attempted_calls"]),
            successful_calls=int(execution["successful_calls"]),
            counted_as_round=True,
            error_types=tuple(sorted({row["error"] for row in execution["errors"]})),
        )
        rounds.append(_round_record(base_round))
        zero_novel_queries = (
            zero_novel_queries + 1 if int(execution["novel_yield"]) == 0 else 0
        )

        matching = next(
            (
                hypothesis
                for hypothesis in plan.query_hypotheses
                if hypothesis.parent_query_hash == execution["query_hash"]
                and hypothesis.load_bearing
            ),
            None,
        )
        if (
            int(execution["novel_yield"]) == 0
            and not reframe_considered
            and plan.automatic_reframe
            and load_bearing
            and matching is not None
        ):
            reframe_considered = True
            selected_hypothesis = matching
            reframe_hash = canonical_query_hash(matching.reframe_query)
            reframe_sources = matching.sources or plan.sources
            common = {
                "task_id": binding.task_id if binding else None,
                "obligation_id": plan.obligation_id,
                "search_plan_id": plan.plan_id,
                "hypothesis_id": matching.hypothesis_id,
                "parent_query_hash": matching.parent_query_hash,
                "query_hash": reframe_hash,
                "query_class": matching.query_class.value,
                "registered_scope_hash": registered_scope_hash,
                "sources": list(reframe_sources),
                "counted_as_round": False,
            }
            if reframe_hash in frozen_base_hashes or reframe_hash in executed_hashes:
                reframe_diagnostics.append(
                    {
                        **common,
                        "challenge_id": None,
                        "reframe_outcome": ReframeOutcome.REJECTED_REDUNDANT.value,
                        "novel_yield": 0,
                        "reason": "exact normalized query already belongs to the frozen base plan",
                    }
                )
            else:
                challenge_id, proposal_status = _propose_native_challenge(
                    root,
                    binding,
                    obligation_id=plan.obligation_id,
                    candidate_hash=candidate_hash,
                    scope_hash=registered_scope_hash,
                    kind=ChallengeKind.RETRIEVAL_REFRAME,
                    hypothesis=(
                        "The registered retrieval frame may miss relevant work due to "
                        f"{matching.query_class.value}."
                    ),
                    alternative=(
                        "The registered scope is adequate for the current bounded "
                        "discovery decision."
                    ),
                    refuter=(
                        f"Run registered Space reframe {matching.hypothesis_id} from "
                        f"parent {matching.parent_query_hash[:16]} and measure novel yield."
                    ),
                    consequence=(
                        "A load-bearing novelty or scoped-absence inference would be "
                        "under-supported without the registered discriminator."
                    ),
                    required_capability="SCHOLARLY_SEARCH",
                    load_bearing=True,
                    metadata={
                        "automatic": True,
                        "search_plan_id": plan.plan_id,
                        "hypothesis_id": matching.hypothesis_id,
                        "query_class": matching.query_class.value,
                        "parent_query_hash": matching.parent_query_hash,
                        "reframe_query_hash": reframe_hash,
                        "registered_scope_hash": registered_scope_hash,
                        "metadata_hash": digest(matching.metadata),
                    },
                )
                if challenge_id is None:
                    if proposal_status == "OFF":
                        outcome = ReframeOutcome.SKIPPED_CHALLENGE_OFF
                    elif proposal_status == "UNBOUND":
                        outcome = ReframeOutcome.SKIPPED_UNBOUND
                    else:
                        outcome = ReframeOutcome.CHALLENGE_UNAVAILABLE
                    reframe_diagnostics.append(
                        {
                            **common,
                            "challenge_id": None,
                            "reframe_outcome": outcome.value,
                            "novel_yield": 0,
                            "reason": proposal_status,
                        }
                    )
                else:
                    selected_challenge_id = challenge_id
                    _start_reframe_challenge(root, challenge_id, matching)
                    reframe_execution = _execute_query(
                        matching.reframe_query,
                        reframe_sources,
                        plan.max_results_per_query,
                        seen,
                    )
                    reframe_executed = True
                    reframe_successful_calls = int(reframe_execution["successful_calls"])
                    executed_hashes.add(str(reframe_execution["query_hash"]))
                    attempted_calls += int(reframe_execution["attempted_calls"])
                    successful_calls += int(reframe_execution["successful_calls"])
                    errors.extend(reframe_execution["errors"])
                    if int(reframe_execution["successful_calls"]) == 0:
                        outcome = ReframeOutcome.UNAVAILABLE
                    elif int(reframe_execution["novel_yield"]) > 0:
                        outcome = ReframeOutcome.NOVEL_YIELD
                    else:
                        outcome = ReframeOutcome.NO_NOVEL_YIELD
                    reframe_round = QueryRoundState(
                        round_id=f"{plan.plan_id}:round-{len(rounds) + 1}",
                        task_id=binding.task_id if binding else None,
                        obligation_id=plan.obligation_id,
                        search_plan_id=plan.plan_id,
                        query_hash=str(reframe_execution["query_hash"]),
                        parent_query_hash=matching.parent_query_hash,
                        challenge_id=challenge_id,
                        query_class=matching.query_class,
                        reframe_outcome=outcome,
                        registered_scope_hash=registered_scope_hash,
                        hypothesis_id=matching.hypothesis_id,
                        sources=reframe_sources,
                        novel_yield=int(reframe_execution["novel_yield"]),
                        total_results=int(reframe_execution["total_results"]),
                        attempted_calls=int(reframe_execution["attempted_calls"]),
                        successful_calls=int(reframe_execution["successful_calls"]),
                        counted_as_round=True,
                        error_types=tuple(
                            sorted({row["error"] for row in reframe_execution["errors"]})
                        ),
                    )
                    rounds.append(_round_record(reframe_round))
                    _finish_reframe_challenge(
                        root,
                        challenge_id,
                        successful_calls=int(reframe_execution["successful_calls"]),
                        novel_yield=int(reframe_execution["novel_yield"]),
                    )
                    zero_novel_queries = (
                        zero_novel_queries + 1
                        if int(reframe_execution["novel_yield"]) == 0
                        else 0
                    )

        if zero_novel_queries >= plan.saturation_queries:
            break

    elapsed = time.monotonic() - started
    if attempted_calls and successful_calls == 0:
        verdict = Verdict.UNAVAILABLE
        scope_status = "SEARCH_UNAVAILABLE"
        final_query_class = QueryClass.SOURCE_ADAPTER_GAP.value
    elif seen:
        verdict = Verdict.UNKNOWN
        scope_status = "CANDIDATES_RETRIEVED_REVIEW_REQUIRED"
        final_query_class = (
            selected_hypothesis.query_class.value if reframe_executed and selected_hypothesis else None
        )
    else:
        verdict = Verdict.UNKNOWN
        scope_status = "NOT_FOUND_WITHIN_SCOPE"
        if reframe_executed and reframe_successful_calls > 0:
            final_query_class = QueryClass.TRUE_NOT_FOUND_WITHIN_REGISTERED_SCOPE.value
        elif reframe_executed:
            final_query_class = QueryClass.SOURCE_ADAPTER_GAP.value
        else:
            final_query_class = None

    evidence_rows = []
    for key, value in seen.items():
        evidence_rows.append(
            {
                "key_hash": digest(key),
                "title_hash": digest(value.get("title") or ""),
                "doi": value.get("doi"),
                "openalex": value.get("openalex"),
                "url": value.get("url"),
                "source_indexes": value.get("source_indexes", []),
                "year": value.get("year"),
                "venue_hash": digest(value.get("venue") or ""),
            }
        )
    result = {
        "schema": SPACE_SCHEMA,
        "plan_id": plan.plan_id,
        "task_id": binding.task_id if binding else None,
        "task_lineage": list(binding.lineage) if binding else [],
        "obligation_id": plan.obligation_id,
        "scope_status": scope_status,
        "final_query_class": final_query_class,
        "rounds": rounds,
        "reframe_diagnostics": reframe_diagnostics,
        "reframe_considered": reframe_considered,
        "reframe_executed": reframe_executed,
        "reframe_successful_calls": reframe_successful_calls,
        "queries_frozen": len(frozen_queries),
        "queries_executed": len(rounds),
        "challenge_rounds": sum(
            1 for row in rounds if row.get("challenge_id") and row.get("counted_as_round")
        ),
        "results": evidence_rows,
        "errors": errors,
        "successful_calls": successful_calls,
        "attempted_calls": attempted_calls,
        "elapsed_seconds": elapsed,
        "registered_inclusion": list(plan.inclusion),
        "registered_exclusion": list(plan.exclusion),
        "registered_search_scope_hash": registered_scope_hash,
        "candidate_hash": candidate_hash,
        "native_challenge_id": selected_challenge_id,
        "task_content_hash": binding.task_content_hash if binding else None,
        "obligation_binding_hash": binding.obligation_binding_hash if binding else None,
        "screening_status": "UNSCREENED",
        "raw_queries_persisted": False,
        "absence_boundary": "NOT_FOUND_WITHIN_SCOPE is not proof of nonexistence",
    }
    if seen:
        unresolved = ("candidate sources require claim-scoped inspection",)
    elif scope_status == "NOT_FOUND_WITHIN_SCOPE":
        unresolved = ("registered search returned no result; absence is only scoped",)
    else:
        unresolved = ("all executed registered search adapters/calls were unavailable",)
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="space",
        obligation_id=plan.obligation_id,
        verdict=verdict,
        action="multi-index-retrieval",
        input_hash=digest(plan),
        output_hash=digest(result),
        evidence=(
            EvidenceRef(
                evidence_class=EvidenceClass.OBSERVED,
                verifier="space_runtime:v2",
                provenance_group="space-retrieval-runtime",
                metadata={
                    "schema": SPACE_SCHEMA,
                    "plan_id": plan.plan_id,
                    "scope_status": scope_status,
                    "final_query_class": final_query_class,
                    "source_indexes": list(plan.sources),
                    "candidate_count": len(seen),
                    "screening_status": "UNSCREENED",
                    "registered_search_scope_hash": registered_scope_hash,
                    "candidate_hash": candidate_hash,
                    "native_challenge_id": selected_challenge_id,
                    "reframe_executed": reframe_executed,
                    "raw_queries_persisted": False,
                    "task_content_hash": binding.task_content_hash if binding else None,
                    "obligation_binding_hash": (
                        binding.obligation_binding_hash if binding else None
                    ),
                },
            ),
        ),
        verifier="space_runtime:v2",
        tool_version=SPACE_SCHEMA,
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=unresolved,
        notes=json.dumps(
            {
                "rounds": rounds,
                "reframe_diagnostics": reframe_diagnostics,
                "errors": errors,
                "absence_boundary": result["absence_boundary"],
                "authority": "DISCOVERY_ONLY",
                "target_domain_clearance_authorized": False,
            },
            sort_keys=True,
        ),
        task_id=binding.task_id if binding else None,
    )
    store.write_named_state("space", plan.plan_id, result)
    store.write_receipt(receipt)
    return receipt, result


def run_automatic_discovery(
    root: Path,
    plan: SearchPlan,
) -> tuple[Receipt, dict[str, Any]]:
    """Explicit compatibility alias for Soul-routed automatic discovery."""

    return run_plan(root, plan)


def _assessment_components(
    assessments: list[SourceAssessment],
) -> tuple[list[list[int]], dict[int, str]]:
    """Union artifacts sharing content or declared provenance into independence groups."""

    parent = list(range(len(assessments)))

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    by_content: dict[str, int] = {}
    by_provenance: dict[str, int] = {}
    for index, assessment in enumerate(assessments):
        content = str(assessment.source.sha256).strip().casefold()
        if content in by_content:
            union(index, by_content[content])
        else:
            by_content[content] = index
        if assessment.provenance_group:
            provenance = normalize_query(assessment.provenance_group)
            if provenance in by_provenance:
                union(index, by_provenance[provenance])
            else:
                by_provenance[provenance] = index

    grouped: dict[int, list[int]] = {}
    for index in range(len(assessments)):
        grouped.setdefault(find(index), []).append(index)
    components = sorted(grouped.values(), key=lambda indexes: indexes[0])
    group_hashes: dict[int, str] = {}
    for component in components:
        identity = {
            "content_hashes": sorted(
                {str(assessments[index].source.sha256).casefold() for index in component}
            ),
            "provenance_groups": sorted(
                {
                    normalize_query(str(assessments[index].provenance_group))
                    for index in component
                    if assessments[index].provenance_group
                }
            ),
        }
        group_hash = digest(identity)
        for index in component:
            group_hashes[index] = group_hash
    return components, group_hashes


def _search_receipt_metadata(search_receipt: Mapping[str, Any]) -> dict[str, Any]:
    for evidence in search_receipt.get("evidence", []):
        if isinstance(evidence, Mapping) and isinstance(evidence.get("metadata"), Mapping):
            return dict(evidence["metadata"])
    return {}


def assess_sources(
    root: Path,
    obligation_id: str,
    search_receipt_id: str,
    assessments: list[SourceAssessment],
) -> Receipt:
    """Assess cited artifacts without treating derivative copies as independent support."""

    _require_text("obligation_id", obligation_id)
    if not isinstance(assessments, list):
        raise TypeError("assessments must be list")
    if any(not isinstance(item, SourceAssessment) for item in assessments):
        raise TypeError("assessments must contain SourceAssessment values")
    assessment_ids = [item.assessment_id for item in assessments]
    if len(assessment_ids) != len(set(assessment_ids)):
        raise ValueError("assessment identifiers must be unique")

    store = RuntimeStore(root)
    search_receipt = store.read_receipt(search_receipt_id)
    if (
        not search_receipt
        or search_receipt.get("module") != "space"
        or search_receipt.get("action") != "multi-index-retrieval"
    ):
        raise ValueError("source assessment requires a valid Space retrieval receipt")
    if search_receipt.get("obligation_id") != obligation_id:
        raise ValueError("source assessment obligation must match the retrieval receipt")
    search_task_id = search_receipt.get("task_id")
    binding = _resolve_task_binding(
        store,
        str(search_task_id) if isinstance(search_task_id, str) and search_task_id else None,
        obligation_id,
    )
    search_metadata = _search_receipt_metadata(search_receipt)
    registered_scope_hash = search_metadata.get("registered_search_scope_hash")
    if not isinstance(registered_scope_hash, str) or not _SHA256.fullmatch(
        registered_scope_hash
    ):
        registered_scope_hash = digest(search_receipt.get("content_hash"))
    candidate_hash = search_metadata.get("candidate_hash")
    if not isinstance(candidate_hash, str) or not _SHA256.fullmatch(candidate_hash):
        candidate_hash = digest(
            {
                "search_receipt": search_receipt.get("content_hash"),
                "obligation_id": obligation_id,
            }
        )

    components, group_hashes = _assessment_components(assessments)
    component_relations: list[set[str]] = []
    for component in components:
        component_relations.append(
            {assessments[index].relation.upper() for index in component}
        )
    independent_support_count = sum(
        1 for relations in component_relations if "SUPPORTS" in relations
    )
    independent_refutation_count = sum(
        1 for relations in component_relations if "REFUTES" in relations
    )
    derivative_components = [component for component in components if len(component) > 1]
    content_counts: dict[str, int] = {}
    provenance_counts: dict[str, int] = {}
    for assessment in assessments:
        content_key = str(assessment.source.sha256).strip().casefold()
        content_counts[content_key] = content_counts.get(content_key, 0) + 1
        if assessment.provenance_group:
            provenance_key = normalize_query(assessment.provenance_group)
            provenance_counts[provenance_key] = provenance_counts.get(provenance_key, 0) + 1
    duplicate_content_group_count = sum(
        1 for count in content_counts.values() if count > 1
    )
    provenance_collision_group_count = sum(
        1 for count in provenance_counts.values() if count > 1
    )
    relation_conflict = bool(
        independent_support_count and independent_refutation_count
    )
    scopes = {normalize_query(item.claim_scope) for item in assessments}
    scope_split = len(scopes) > 1

    if not assessments:
        verdict = Verdict.UNKNOWN
        outcome = "NO_SOURCE_ASSESSMENT"
    elif scope_split:
        verdict = Verdict.UNKNOWN
        outcome = "SCOPE_SPLIT"
    elif relation_conflict:
        verdict = Verdict.UNKNOWN
        outcome = "CONFLICTED"
    elif independent_support_count:
        verdict = Verdict.CLEARED
        outcome = (
            "SUPPORTED_WITH_DERIVATIVE_COLLISION"
            if derivative_components
            else "SUPPORTED"
        )
    elif independent_refutation_count:
        verdict = Verdict.CLEARED
        outcome = (
            "REFUTED_WITH_DERIVATIVE_COLLISION"
            if derivative_components
            else "REFUTED"
        )
    else:
        verdict = Verdict.UNKNOWN
        outcome = "CONTEXT_ONLY"

    challenge_id: str | None = None
    conflict_types: list[str] = []
    if relation_conflict:
        conflict_types.append("ASSESSED_RELATION_CONFLICT")
    if provenance_collision_group_count:
        conflict_types.append("PROVENANCE_COLLISION")
    if derivative_components:
        conflict_types.append(QueryClass.DERIVATIVE_SOURCE_COLLISION.value)
    if scope_split:
        conflict_types.append("CLAIM_SCOPE_SPLIT")
    if conflict_types:
        challenge_scope_hash = digest(
            {
                "registered_search_scope_hash": registered_scope_hash,
                "claim_scope_hashes": sorted(digest(scope) for scope in scopes),
            }
        )
        challenge_id, _ = _propose_native_challenge(
            root,
            binding,
            obligation_id=obligation_id,
            candidate_hash=candidate_hash,
            scope_hash=challenge_scope_hash,
            kind=ChallengeKind.SOURCE_CONFLICT,
            hypothesis=(
                "The assessed source bundle contains a relation, provenance, derivative, "
                "or claim-scope conflict."
            ),
            alternative=(
                "The apparent conflict disappears after first-party lineage, version, "
                "definition, population, or scope separation."
            ),
            refuter=(
                "Resolve the bound conflict using claim-scoped source comparison without "
                "counting derivative copies as independent support."
            ),
            consequence=(
                "The discovery obligation cannot be settled by source count or duplicated "
                "provenance."
            ),
            required_capability="SOURCE_CONFLICT_RESOLUTION",
            load_bearing=binding.load_bearing if binding else True,
            metadata={
                "automatic": True,
                "conflict_types": conflict_types,
                "independent_group_count": len(components),
                "derivative_component_count": len(derivative_components),
                "duplicate_content_group_count": duplicate_content_group_count,
                "provenance_collision_group_count": provenance_collision_group_count,
                "independent_support_count": independent_support_count,
                "independent_refutation_count": independent_refutation_count,
                "registered_search_scope_hash": registered_scope_hash,
                "assessment_bundle_hash": digest(assessments),
            },
        )

    component_size_by_index: dict[int, int] = {}
    component_representative_by_index: dict[int, int] = {}
    for component in components:
        representative = component[0]
        for index in component:
            component_size_by_index[index] = len(component)
            component_representative_by_index[index] = representative
    evidence = tuple(
        EvidenceRef(
            evidence_class=EvidenceClass.CITED,
            artifact=assessment.source,
            verifier=assessment.verifier,
            provenance_group=assessment.provenance_group,
            metadata={
                "relation": assessment.relation.upper(),
                "claim_scope": assessment.claim_scope,
                "assessment_id": assessment.assessment_id,
                "notes_hash": assessment.notes_hash,
                "independence_group_hash": group_hashes[index],
                "independence_group_size": component_size_by_index[index],
                "counts_as_independence_group_representative": (
                    component_representative_by_index[index] == index
                ),
            },
        )
        for index, assessment in enumerate(assessments)
    )
    summary = {
        "outcome": outcome,
        "assessment_ids": assessment_ids,
        "independent_group_count": len(components),
        "independent_support_count": independent_support_count,
        "independent_refutation_count": independent_refutation_count,
        "derivative_component_count": len(derivative_components),
        "duplicate_content_group_count": duplicate_content_group_count,
        "provenance_collision_group_count": provenance_collision_group_count,
        "conflict_types": conflict_types,
        "native_challenge_id": challenge_id,
        "registered_search_scope_hash": registered_scope_hash,
    }
    unresolved: list[str] = []
    if verdict != Verdict.CLEARED:
        unresolved.append(f"source assessment outcome={outcome}")
    if derivative_components:
        unresolved.append("derivative sources count as one independent provenance group")
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="space",
        obligation_id=obligation_id,
        verdict=verdict,
        action="source-assessment",
        input_hash=digest(
            {
                "search_receipt": search_receipt.get("content_hash"),
                "assessments": assessments,
            }
        ),
        output_hash=digest(summary),
        evidence=evidence,
        verifier="space_runtime:source-assessment:v2",
        tool_version=SPACE_SCHEMA,
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=tuple(unresolved),
        notes=json.dumps(
            {
                "claim_outcome": outcome,
                "search_receipt_id": search_receipt_id,
                "independent_group_count": len(components),
                "independent_support_count": independent_support_count,
                "independent_refutation_count": independent_refutation_count,
                "derivative_component_count": len(derivative_components),
                "duplicate_content_group_count": duplicate_content_group_count,
                "provenance_collision_group_count": provenance_collision_group_count,
                "conflict_types": conflict_types,
                "native_challenge_id": challenge_id,
                "boundary": (
                    "CLEARED means inspected cited evidence supports or refutes one scoped "
                    "claim; it does not convert scoped search failure into nonexistence, "
                    "and derivative copies do not add independent support."
                ),
            },
            sort_keys=True,
        ),
        task_id=binding.task_id if binding else None,
    )
    store.write_receipt(receipt)
    return receipt


__all__ = [
    "ADAPTERS",
    "QueryClass",
    "QueryHypothesis",
    "QueryRoundState",
    "ReframeOutcome",
    "SPACE_SCHEMA",
    "SearchPlan",
    "SourceAssessment",
    "SpaceAuthorityError",
    "assess_sources",
    "canonical_query_hash",
    "normalize_query",
    "run_automatic_discovery",
    "run_plan",
]
