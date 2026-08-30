"""Offline Gate-1 runner for immutable FOIL v5 residual-scan atlas rows.

The scanner receives only ``scanner`` material.  Labels stay at the harness
boundary until the scanner result is sealed, so lock labels cannot influence the
closed deterministic scan.  This module performs no provider, network, tool,
or child-process activity.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_claims import Applicability, Decidability, ImmutableBindings  # noqa: E402
from foil_residual_scanner import DiagnosticCase, ResidualScanPlan, scan  # noqa: E402
from foil_v5_metrics import ResidualDiagnosticNeed, ScanStatus  # noqa: E402
from foil_v5_run_ledger import EFFECT_CATEGORIES, RunLedger  # noqa: E402
from foil_v5_score import (  # noqa: E402
    AdjudicatedObligation,
    CompilerScore,
    score_adjudicated_compiler,
)
from foil_v5_statistics import ClusterObservation, ResidualRates, residual_rates  # noqa: E402

SCHEMA = "egrt.foil-v5-shadow-atlas-item.v1"
OFFLINE_EFFECTS = frozenset({"local", "parser"})


class AtlasError(ValueError):
    """A Gate-1 atlas is malformed, contaminated, or outside the offline contract."""


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AtlasError(f"{name} must be non-empty text")
    return value


def _require_digest(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise AtlasError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AtlasError(f"{name} must be an object")
    return value


def _scanner_input(row: Mapping[str, Any]) -> Mapping[str, Any]:
    scanner = _mapping("scanner", row.get("scanner"))
    prohibited = {"labels", "gold", "gold_label", "base_correct", "residual_present"}
    if prohibited.intersection(scanner):
        raise AtlasError("scanner input must not contain outcome labels")
    return scanner


def load_atlas(path: Path, *, partition: str) -> tuple[dict[str, Any], ...]:
    """Load JSONL rows and require their declared partition before evaluation."""

    if partition not in {"development", "lock"}:
        raise AtlasError("partition must be development or lock")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AtlasError(f"invalid JSON at {path}:{line_number}") from exc
        if not isinstance(row, dict) or row.get("schema") != SCHEMA:
            raise AtlasError(f"invalid schema at {path}:{line_number}")
        if row.get("partition") != partition:
            raise AtlasError(f"partition mismatch at {path}:{line_number}")
        _require_text("item_id", row.get("item_id"))
        _require_text("base_item_id", row.get("base_item_id"))
        _require_text("domain", row.get("domain"))
        _scanner_input(row)
        labels = _mapping("labels", row.get("labels"))
        if not isinstance(labels.get("base_correct"), bool):
            raise AtlasError("labels.base_correct must be bool")
        rows.append(row)
    if not rows:
        raise AtlasError("atlas must contain at least one row")
    ids = [row["item_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise AtlasError("atlas item ids must be unique")
    return tuple(rows)


def assert_disjoint_partitions(
    development: Iterable[Mapping[str, Any]], lock: Iterable[Mapping[str, Any]]
) -> None:
    dev = {str(row.get("base_item_id")) for row in development}
    locked = {str(row.get("base_item_id")) for row in lock}
    overlap = dev.intersection(locked)
    if overlap:
        raise AtlasError(f"development and lock partitions overlap: {sorted(overlap)}")


def _plan_and_cases(
    scanner: Mapping[str, Any],
) -> tuple[ResidualScanPlan, tuple[DiagnosticCase, ...]]:
    bindings_raw = _mapping("scanner.bindings", scanner.get("bindings"))
    bindings = ImmutableBindings(
        *[
            _require_digest(f"scanner.bindings.{name}", bindings_raw.get(name))
            for name in (
                "a0_digest",
                "task_digest",
                "spec_digest",
                "compiler_digest",
                "config_digest",
            )
        ]
    )
    claim_id = _require_text("scanner.claim_id", scanner.get("claim_id"))
    a0_digest = _require_digest("scanner.a0_digest", scanner.get("a0_digest"))
    if a0_digest != bindings.a0_digest:
        raise AtlasError("scanner A0 digest must match immutable bindings")
    needs_raw = scanner.get("needs")
    if not isinstance(needs_raw, list) or not needs_raw:
        raise AtlasError("scanner.needs must be a non-empty list")
    needs: list[ResidualDiagnosticNeed] = []
    cases: list[DiagnosticCase] = []
    for raw in needs_raw:
        row = _mapping("scanner.need", raw)
        needs.append(
            ResidualDiagnosticNeed(
                need_id=_require_text("need_id", row.get("need_id")),
                claim_id=claim_id,
                description=_require_text("description", row.get("description")),
                verifier_id=_require_text("verifier_id", row.get("verifier_id")),
                weight_units=row.get("weight_units"),
                decidability=Decidability(row.get("decidability")),
                applicability=Applicability(row.get("applicability")),
                bindings=bindings,
            )
        )
        case = _mapping("need.case", row.get("case"))
        cases.append(
            DiagnosticCase(
                need_id=needs[-1].need_id,
                verifier_input=_mapping("need.case.verifier_input", case.get("verifier_input")),
                metadata=_mapping("need.case.metadata", case.get("metadata", {})),
            )
        )
    return ResidualScanPlan(claim_id, a0_digest, bindings, tuple(needs)), tuple(cases)


def _compiler_rows(row: Mapping[str, Any]) -> tuple[AdjudicatedObligation, ...]:
    labels = _mapping("labels", row["labels"])
    raw = labels.get("compiler_obligations")
    if not isinstance(raw, list) or not raw:
        raise AtlasError("labels.compiler_obligations must be a non-empty list")
    return tuple(
        AdjudicatedObligation(
            obligation_id=_require_text(
                "compiler obligation_id", _mapping("compiler row", item).get("obligation_id")
            ),
            weight_units=_mapping("compiler row", item).get("weight_units"),
            extracted=_mapping("compiler row", item).get("extracted"),
            correctly_extracted=_mapping("compiler row", item).get("correctly_extracted"),
            deterministically_decidable=_mapping("compiler row", item).get(
                "deterministically_decidable"
            ),
        )
        for item in raw
    )


@dataclass(frozen=True)
class ShadowRunRecord:
    item_id: str
    base_item_id: str
    domain: str
    a0_digest: str
    status: str
    no_answer_code: str | None
    base_correct: bool
    compiler_rows: tuple[AdjudicatedObligation, ...]
    scanner_input_digest: str
    a0_preserved: bool


@dataclass(frozen=True)
class DomainSummary:
    domain: str
    rates: ResidualRates
    compiler: CompilerScore


@dataclass(frozen=True)
class ShadowRunSummary:
    partition: str
    confidence: float
    records: tuple[ShadowRunRecord, ...]
    overall: DomainSummary
    domains: tuple[DomainSummary, ...]
    worst_domain: str | None
    ledger_receipt: Mapping[str, Any] | None
    validity_boundary: str = "Tiny structural smoke data only; not natural-prevalence, calibration, or efficacy evidence."


def _domain_summary(
    domain: str, records: tuple[ShadowRunRecord, ...], confidence: float
) -> DomainSummary:
    observations = tuple(
        ClusterObservation(
            item_id=row.item_id,
            base_item_id=row.base_item_id,
            domain=row.domain,
            base_correct=row.base_correct,
            flagged=row.status == ScanStatus.FAIL.value,
            status=row.status,
            no_answer_code=row.no_answer_code,
        )
        for row in records
    )

    # Obligation identifiers are item-scoped for atlas accounting, so re-key duplicates.
    scoped = tuple(
        AdjudicatedObligation(
            f"{record.item_id}:{item.obligation_id}",
            item.weight_units,
            item.extracted,
            item.correctly_extracted,
            item.deterministically_decidable,
        )
        for record in records
        for item in record.compiler_rows
    )
    return DomainSummary(
        domain,
        residual_rates(observations, confidence=confidence),
        score_adjudicated_compiler(scoped),
    )


def _offline_ledger(
    candidate_sha256: str, protocol_sha256: str, records: tuple[ShadowRunRecord, ...]
) -> Mapping[str, Any]:
    ledger = RunLedger(candidate_sha256=candidate_sha256, protocol_sha256=protocol_sha256)
    ledger.begin(0)
    for category in sorted(EFFECT_CATEGORIES - OFFLINE_EFFECTS):
        ledger.record_category(
            category, observation=None, reason="forbidden_offline_effect_not_observed"
        )
    for index, _ in enumerate(records, 1):
        start = index * 10
        ledger.start_span(f"parse-{index}", category="parser", started_ns=start)
        ledger.end_span(f"parse-{index}", ended_ns=start + 1)
        ledger.start_span(f"scan-{index}", category="local", started_ns=start + 2)
        ledger.end_span(f"scan-{index}", ended_ns=start + 3)
    ledger.close(len(records) * 10 + 4)
    return ledger.seal()


def run_shadow_atlas(
    rows: Iterable[Mapping[str, Any]],
    *,
    partition: str,
    confidence: float = 0.95,
    candidate_sha256: str | None = None,
    protocol_sha256: str | None = None,
    observed_effects: Iterable[str] = OFFLINE_EFFECTS,
) -> ShadowRunSummary:
    """Execute a frozen offline atlas with labels withheld from scanner calls."""

    if partition not in {"development", "lock"}:
        raise AtlasError("partition must be development or lock")
    effects = frozenset(observed_effects)
    unknown = effects - EFFECT_CATEGORIES
    forbidden = effects - OFFLINE_EFFECTS
    if unknown or forbidden:
        raise AtlasError("offline shadow runs reject unknown or forbidden effect categories")
    records: list[ShadowRunRecord] = []
    for raw in rows:
        row = _mapping("atlas row", raw)
        if row.get("schema") != SCHEMA or row.get("partition") != partition:
            raise AtlasError("atlas row schema or partition mismatch")
        scanner = _scanner_input(row)
        plan, cases = _plan_and_cases(scanner)
        report = scan(plan, plan.a0_digest, cases)
        labels = _mapping("labels", row.get("labels"))
        records.append(
            ShadowRunRecord(
                item_id=_require_text("item_id", row.get("item_id")),
                base_item_id=_require_text("base_item_id", row.get("base_item_id")),
                domain=_require_text("domain", row.get("domain")),
                a0_digest=plan.a0_digest,
                status=report.status.value,
                no_answer_code=report.no_answer.code.value
                if report.no_answer is not None
                else None,
                base_correct=labels.get("base_correct"),
                compiler_rows=_compiler_rows(row),
                scanner_input_digest=report.input_digest,
                a0_preserved=report.a0_digest == plan.a0_digest,
            )
        )
    frozen = tuple(records)
    if not frozen or not all(row.a0_preserved for row in frozen):
        raise AtlasError("A0 preservation is required for every scanner record")
    by_domain: dict[str, list[ShadowRunRecord]] = defaultdict(list)
    for record in frozen:
        by_domain[record.domain].append(record)
    domains = tuple(
        _domain_summary(domain, tuple(rows), confidence)
        for domain, rows in sorted(by_domain.items())
    )
    overall = _domain_summary("__overall__", frozen, confidence)
    recall_domains = [item for item in domains if item.rates.residual_recall.estimate is not None]
    worst_domain = (
        min(recall_domains, key=lambda item: item.rates.residual_recall.estimate).domain
        if recall_domains
        else None
    )
    receipt = None
    if candidate_sha256 is not None or protocol_sha256 is not None:
        receipt = _offline_ledger(
            _require_digest("candidate_sha256", candidate_sha256),
            _require_digest("protocol_sha256", protocol_sha256),
            frozen,
        )
    return ShadowRunSummary(partition, confidence, frozen, overall, domains, worst_domain, receipt)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local FOIL v5 shadow atlas")
    parser.add_argument("atlas", type=Path)
    parser.add_argument("--partition", choices=("development", "lock"), required=True)
    parser.add_argument("--confidence", type=float, default=0.95)
    args = parser.parse_args()
    rows = load_atlas(args.atlas, partition=args.partition)
    result = run_shadow_atlas(rows, partition=args.partition, confidence=args.confidence)
    print(json.dumps(asdict(result), sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
