"""Deterministic trace replay for FOIL assistance and execution ownership."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import foil_evidence  # noqa: E402
import foil_profile  # noqa: E402
from foil_assistance_policy import select_assistance  # noqa: E402

FIXTURE_SCHEMA = "foil.assistance-replay-fixture.v1"
REPORT_SCHEMA = "foil.assistance-replay-report.v1"
CASE_FIELDS = {
    "id", "intent", "demand", "deadline", "deliverable", "ownership_probe_due",
    "events", "expected_classification", "expected_assistance", "expected_load_bearing_n",
}
EVENT_FIELDS = {"correct", "verified", "assistance", "execution_owner", "source"}


def _closed(row: Mapping[str, object], fields: set[str], label: str) -> None:
    if set(row) != fields:
        raise ValueError(f"{label} fields mismatch: expected {sorted(fields)}, got {sorted(row)}")


def _observations(events: object) -> list[foil_evidence.Observation]:
    if not isinstance(events, list):
        raise TypeError("events must be a list")
    observations: list[foil_evidence.Observation] = []
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            raise TypeError(f"event {index} must be an object")
        _closed(event, EVENT_FIELDS, f"event {index}")
        if not isinstance(event["correct"], bool) or not isinstance(event["verified"], bool):
            raise TypeError("event correct/verified values must be booleans")
        tier = foil_profile.derive_tier(
            source=str(event["source"]),
            verified=event["verified"],
            assistance=event["assistance"],
            execution_owner=event["execution_owner"],
        )
        observations.append(
            foil_evidence.Observation(
                correct=event["correct"],
                tier=foil_evidence.EvidenceTier(tier),
            )
        )
    return observations


def replay(document: Mapping[str, object]) -> dict[str, object]:
    if set(document) != {"schema", "cases"} or document.get("schema") != FIXTURE_SCHEMA:
        raise ValueError("unexpected assistance replay fixture")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("fixture cases must be a non-empty list")
    rows: list[dict[str, object]] = []
    identifiers: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise TypeError("fixture case must be an object")
        _closed(case, CASE_FIELDS, "case")
        case_id = str(case["id"])
        if not case_id or case_id in identifiers:
            raise ValueError("case ids must be non-empty and unique")
        identifiers.add(case_id)
        summary = foil_evidence.summarize(_observations(case["events"]))
        decision = select_assistance(
            classification=summary,
            intent=str(case["intent"]),
            demand=str(case["demand"]),
            deadline=case["deadline"],
            deliverable=case["deliverable"],
            ownership_probe_due=case["ownership_probe_due"],
        )
        observed = {
            "classification": summary.classification.value,
            "assistance": decision.assistance.value,
            "load_bearing_n": summary.load_bearing_n,
        }
        expected = {
            "classification": case["expected_classification"],
            "assistance": case["expected_assistance"],
            "load_bearing_n": case["expected_load_bearing_n"],
        }
        rows.append(
            {
                "id": case_id,
                "passed": observed == expected,
                "observed": observed,
                "expected": expected,
                "decision": decision.trace(),
            }
        )
    passed = sum(bool(row["passed"]) for row in rows)
    return {
        "schema": REPORT_SCHEMA,
        "classification": "DETERMINISTIC_SPEC_CONFORMANCE_ONLY",
        "cases": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "rows": rows,
        "cost_and_authority": {
            "provider_calls": 0,
            "tokens": 0,
            "profile_writes": 0,
            "answer_mutations": 0,
        },
        "non_claims": [
            "not evidence that assistance improves learning",
            "not production personalization evidence",
        ],
    }


def load_and_replay(path: Path) -> dict[str, object]:
    return replay(json.loads(path.read_text(encoding="utf-8")))


def main(argv: Sequence[str] | None = None) -> int:
    path = Path(argv[0]) if argv else ROOT / "benchmarks" / "fixtures" / "foil_assistance_replay_v1.json"
    report = load_and_replay(path)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
