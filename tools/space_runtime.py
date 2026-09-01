"""Stateful Farfield research-discovery runtime with scoped retrieval and source assessment.

Retrieval is not factual verification. Search receipts remain UNKNOWN until selected
sources are actually inspected and recorded in a source-assessment receipt. A
negative search result is always scoped as NOT_FOUND_WITHIN_SCOPE, never nonexistence.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import ArtifactRef, EvidenceClass, EvidenceRef, Receipt, Verdict, digest

UA = "Evidence-Governed-Research-Toolkit/vnext (+https://github.com/Kitahl/The-Gauntlet)"


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

    def __post_init__(self) -> None:
        if not self.queries:
            raise ValueError("SearchPlan requires at least one frozen query")
        if not self.sources:
            raise ValueError("SearchPlan requires at least one source index")
        if self.max_results_per_query < 1 or self.max_queries < 1 or self.saturation_queries < 1:
            raise ValueError("search limits must be positive")


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
        relation = self.relation.upper()
        if relation not in {"SUPPORTS", "REFUTES", "CONTEXT_ONLY"}:
            raise ValueError("source relation must be SUPPORTS, REFUTES, or CONTEXT_ONLY")
        if not self.source.sha256:
            raise ValueError("assessed source requires a content SHA-256")
        if not self.verifier.strip() or not self.claim_scope.strip():
            raise ValueError("assessed source requires verifier and claim scope")


def _norm_doi(value: str | None) -> str | None:
    if not value:
        return None
    low = value.strip().lower()
    low = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", low)
    return low or None


def _norm_title(title: str | None) -> str:
    return re.sub(r"\W+", " ", (title or "").lower()).strip()


def _key(row: dict[str, Any]) -> str:
    return str(_norm_doi(row.get("doi")) or row.get("openalex") or row.get("url") or _norm_title(row.get("title")))


def search_openalex(query: str, limit: int, timeout: float = 20.0) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"search": query, "per-page": max(1, min(limit, 25))})
    response = requests.get(f"https://api.openalex.org/works?{params}", headers={"User-Agent": UA}, timeout=timeout)
    response.raise_for_status()
    out = []
    for work in response.json().get("results", [])[:limit]:
        primary = work.get("primary_location") or {}
        source = primary.get("source") or {}
        out.append({
            "title": work.get("display_name"),
            "year": work.get("publication_year"),
            "doi": _norm_doi(work.get("doi")),
            "openalex": work.get("id"),
            "url": work.get("id"),
            "venue": source.get("display_name"),
            "source_index": "openalex",
        })
    return out


def search_crossref(query: str, limit: int, timeout: float = 20.0) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"query.bibliographic": query, "rows": max(1, min(limit, 25))})
    response = requests.get(f"https://api.crossref.org/works?{params}", headers={"User-Agent": UA}, timeout=timeout)
    response.raise_for_status()
    out = []
    for item in response.json().get("message", {}).get("items", [])[:limit]:
        title = (item.get("title") or [None])[0]
        year_parts = ((item.get("published-print") or item.get("published-online") or {}).get("date-parts") or [[None]])[0]
        out.append({
            "title": title,
            "year": year_parts[0] if year_parts else None,
            "doi": _norm_doi(item.get("DOI")),
            "url": item.get("URL"),
            "venue": (item.get("container-title") or [None])[0],
            "source_index": "crossref",
        })
    return out


ADAPTERS = {"openalex": search_openalex, "crossref": search_crossref}


def _merge_seen(seen: dict[str, dict[str, Any]], row: dict[str, Any]) -> bool:
    key = _key(row)
    if not key:
        return False
    if key not in seen:
        copy = dict(row)
        copy["source_indexes"] = sorted({str(row.get("source_index") or "unknown")})
        seen[key] = copy
        return True
    source_indexes = set(seen[key].get("source_indexes") or [])
    source_indexes.add(str(row.get("source_index") or "unknown"))
    seen[key]["source_indexes"] = sorted(source_indexes)
    # Fill metadata gaps without replacing already observed values.
    for field_name in ("doi", "openalex", "url", "year", "venue", "title"):
        if not seen[key].get(field_name) and row.get(field_name):
            seen[key][field_name] = row[field_name]
    return False


def run_plan(root: Path, plan: SearchPlan) -> tuple[Receipt, dict[str, Any]]:
    store = RuntimeStore(root)
    seen: dict[str, dict[str, Any]] = {}
    rounds: list[dict[str, Any]] = []
    zero_novel_queries = 0
    errors: list[dict[str, str]] = []
    attempted_calls = 0
    successful_calls = 0
    started = time.monotonic()

    for query_index, query in enumerate(plan.queries[: plan.max_queries]):
        novel_before = len(seen)
        for source in plan.sources:
            attempted_calls += 1
            adapter = ADAPTERS.get(source)
            if adapter is None:
                errors.append({"source": source, "query_hash": digest(query), "error": "UNAVAILABLE_ADAPTER"})
                continue
            try:
                rows = adapter(query, plan.max_results_per_query)
                successful_calls += 1
            except requests.RequestException as exc:
                errors.append({"source": source, "query_hash": digest(query), "error": type(exc).__name__})
                continue
            for row in rows:
                _merge_seen(seen, row)
        novel = len(seen) - novel_before
        rounds.append({"query_index": query_index + 1, "query_hash": digest(query), "novel": novel, "total": len(seen)})
        zero_novel_queries = zero_novel_queries + 1 if novel == 0 else 0
        if zero_novel_queries >= plan.saturation_queries:
            break

    elapsed = time.monotonic() - started
    if attempted_calls and successful_calls == 0:
        verdict = Verdict.UNAVAILABLE
        scope_status = "SEARCH_UNAVAILABLE"
    elif seen:
        # Retrieval candidates alone do not establish that any source supports the
        # load-bearing claim. A source-assessment receipt is required to clear it.
        verdict = Verdict.UNKNOWN
        scope_status = "CANDIDATES_RETRIEVED_REVIEW_REQUIRED"
    else:
        verdict = Verdict.UNKNOWN
        scope_status = "NOT_FOUND_WITHIN_SCOPE"

    evidence_rows = []
    for key, value in seen.items():
        evidence_rows.append({
            "key_hash": digest(key),
            "title_hash": digest(value.get("title") or ""),
            "doi": value.get("doi"),
            "openalex": value.get("openalex"),
            "url": value.get("url"),
            "source_indexes": value.get("source_indexes", []),
            "year": value.get("year"),
            "venue_hash": digest(value.get("venue") or ""),
        })
    result = {
        "plan_id": plan.plan_id,
        "scope_status": scope_status,
        "rounds": rounds,
        "results": evidence_rows,
        "errors": errors,
        "successful_calls": successful_calls,
        "attempted_calls": attempted_calls,
        "elapsed_seconds": elapsed,
        "registered_inclusion": list(plan.inclusion),
        "registered_exclusion": list(plan.exclusion),
        "screening_status": "UNSCREENED",
        "absence_boundary": "NOT_FOUND_WITHIN_SCOPE is not proof of nonexistence",
    }
    receipt = Receipt(
        receipt_id=new_id("rcpt"), module="space", obligation_id=plan.obligation_id,
        verdict=verdict, action="multi-index-retrieval", input_hash=digest(plan), output_hash=digest(result),
        evidence=(EvidenceRef(
            evidence_class=EvidenceClass.OBSERVED,
            verifier="space_runtime",
            metadata={"scope_status": scope_status, "source_indexes": list(plan.sources), "candidate_count": len(seen), "screening_status": "UNSCREENED"},
        ),),
        verifier="space_runtime", started_at=utcnow(), finished_at=utcnow(),
        unresolved=(
            "candidate sources require claim-scoped inspection"
            if seen else (
                "registered search returned no result; absence is only scoped"
                if scope_status == "NOT_FOUND_WITHIN_SCOPE" else "all configured search adapters/calls were unavailable"
            )
        ,),
        notes=json.dumps({"rounds": rounds, "errors": errors, "absence_boundary": result["absence_boundary"]}, sort_keys=True),
    )
    store.write_named_state("space", plan.plan_id, result)
    store.write_receipt(receipt)
    return receipt, result


def assess_sources(root: Path, obligation_id: str, search_receipt_id: str, assessments: list[SourceAssessment]) -> Receipt:
    store = RuntimeStore(root)
    search_receipt = store.read_receipt(search_receipt_id)
    if not search_receipt or search_receipt.get("module") != "space" or search_receipt.get("action") != "multi-index-retrieval":
        raise ValueError("source assessment requires a valid Space retrieval receipt")
    if not assessments:
        verdict = Verdict.UNKNOWN
        outcome = "NO_SOURCE_ASSESSMENT"
    else:
        relations = {a.relation.upper() for a in assessments}
        if "SUPPORTS" in relations and "REFUTES" in relations:
            verdict = Verdict.UNKNOWN
            outcome = "CONFLICTED"
        elif "SUPPORTS" in relations:
            verdict = Verdict.CLEARED
            outcome = "SUPPORTED"
        elif "REFUTES" in relations:
            verdict = Verdict.CLEARED
            outcome = "REFUTED"
        else:
            verdict = Verdict.UNKNOWN
            outcome = "CONTEXT_ONLY"

    evidence = tuple(
        EvidenceRef(
            evidence_class=EvidenceClass.CITED,
            artifact=a.source,
            verifier=a.verifier,
            provenance_group=a.provenance_group,
            metadata={"relation": a.relation.upper(), "claim_scope": a.claim_scope, "assessment_id": a.assessment_id, "notes_hash": a.notes_hash},
        )
        for a in assessments
    )
    receipt = Receipt(
        receipt_id=new_id("rcpt"), module="space", obligation_id=obligation_id,
        verdict=verdict, action="source-assessment",
        input_hash=digest({"search_receipt": search_receipt.get("content_hash"), "assessments": assessments}),
        output_hash=digest({"outcome": outcome, "assessment_ids": [a.assessment_id for a in assessments]}),
        evidence=evidence,
        verifier="space_runtime:source-assessment", started_at=utcnow(), finished_at=utcnow(),
        unresolved=() if verdict == Verdict.CLEARED else (f"source assessment outcome={outcome}",),
        notes=json.dumps({
            "claim_outcome": outcome,
            "search_receipt_id": search_receipt_id,
            "boundary": "CLEARED means inspected cited evidence supports or refutes the scoped claim; it does not convert a scoped negative search into proof of nonexistence.",
        }, sort_keys=True),
    )
    store.write_receipt(receipt)
    return receipt
