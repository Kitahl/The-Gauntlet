"""Independent row-level recomputation for the deterministic persona report."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import foil_persona_simulation  # noqa: E402

REPORT_FIELDS = {
    "schema", "classification", "personas", "sessions", "metrics",
    "kill_conditions", "persona_summaries", "raw_rows", "cost_and_authority",
    "non_claims", "report_sha256",
}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: actual={actual!r}, expected={expected!r}")


def audit(report: Mapping[str, object]) -> dict[str, object]:
    if set(report) != REPORT_FIELDS:
        raise ValueError("persona report fields mismatch")
    if report["schema"] != foil_persona_simulation.REPORT_SCHEMA:
        raise ValueError("unexpected persona report schema")
    unsigned = copy.deepcopy(dict(report))
    claimed_digest = unsigned.pop("report_sha256")
    _equal(claimed_digest, _digest(unsigned), "report_sha256")
    summaries = report["persona_summaries"]
    rows = report["raw_rows"]
    metrics = report["metrics"]
    kills = report["kill_conditions"]
    if not isinstance(summaries, list) or not isinstance(rows, list):
        raise TypeError("persona_summaries and raw_rows must be lists")
    if not isinstance(metrics, Mapping) or not isinstance(kills, Mapping):
        raise TypeError("metrics and kill_conditions must be objects")
    _equal(report["personas"], len(summaries), "persona count")
    _equal(report["sessions"], len(rows), "session count")
    ids = [str(item["persona_id"]) for item in summaries]
    if len(ids) != len(set(ids)):
        raise ValueError("persona summary ids must be unique")
    per_persona = Counter(str(row["persona_id"]) for row in rows)
    _equal(set(per_persona), set(ids), "raw/summary persona ids")
    for persona_id, count in per_persona.items():
        sessions = sorted(
            int(row["session"]) for row in rows if row["persona_id"] == persona_id
        )
        _equal(sessions, list(range(1, count + 1)), f"{persona_id} session conservation")
    adversarial = [item for item in summaries if item["adversarial_profile"]]
    fooled = sum(bool(item["fooled"]) for item in adversarial)
    persistent_over = sum(bool(row["over_assistance_after_strength"]) for row in rows)
    raw_under = sum(bool(row["under_assistance"]) for row in rows)
    planned_under = sum(bool(row["planned_ladder_trial_under_assistance"]) for row in rows)
    unplanned_under = sum(bool(row["unplanned_under_assistance"]) for row in rows)
    recomputed = {
        "profile_initial_mean_distance": mean(float(item["initial_distance"]) for item in summaries),
        "profile_final_mean_distance": mean(float(item["final_distance"]) for item in summaries),
        "persona_distance_nonincreasing_rate": mean(bool(item["distance_nonincreasing"]) for item in summaries),
        "brier_score": mean(float(row["brier"]) for row in rows),
        "over_assistance_rate": mean(bool(row["over_assistance"]) for row in rows),
        "over_assistance_after_strength_rate": persistent_over / len(rows),
        "under_assistance_rate_raw": raw_under / len(rows),
        "planned_ladder_trial_under_assistance_rate": planned_under / len(rows),
        "unplanned_under_assistance_rate": unplanned_under / len(rows),
        "fooled_rate": fooled / len(adversarial) if adversarial else 0.0,
        "fade_correct_rate": mean(bool(item["fade_correct"]) for item in summaries),
    }
    _equal(dict(metrics), recomputed, "metrics")
    recomputed_kills = {
        "fooled_rate_gt_zero": fooled > 0,
        "profile_distance_diverged": any(not item["distance_nonincreasing"] for item in summaries),
        "fade_contract_failed": any(not item["fade_correct"] for item in summaries),
        "over_assistance_persisted_after_strength": persistent_over > 0,
        "unplanned_under_assistance": unplanned_under > 0,
    }
    _equal(dict(kills), recomputed_kills, "kill conditions")
    if any(value != 0 for value in report["cost_and_authority"].values()):
        raise ValueError("persona conformance report must remain zero-cost and no-authority")
    return {
        "schema": "foil.simulated-persona-independent-audit.v1",
        "classification": "INDEPENDENT_STATIC_RECOMPUTATION_ONLY",
        "report_sha256": claimed_digest,
        "personas": len(summaries),
        "sessions": len(rows),
        "metrics_recomputed": True,
        "kill_conditions_recomputed": True,
        "row_conservation_passed": True,
        "cost_and_authority_zero": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    fixture = Path(argv[0]) if argv else ROOT / "benchmarks" / "fixtures" / "foil_personas_v1.json"
    report = foil_persona_simulation.load_and_run(fixture)
    print(json.dumps(audit(report), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
