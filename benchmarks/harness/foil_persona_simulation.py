"""Deterministic longitudinal persona simulation for FOIL's PERSON surface."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import foil_evidence  # noqa: E402
import foil_profile  # noqa: E402
from foil_assistance import Assistance, parse_assistance  # noqa: E402
from foil_assistance_policy import (  # noqa: E402
    advance_assistance_floor,
    select_assistance,
)

FIXTURE_SCHEMA = "foil.simulated-personas.v1"
REPORT_SCHEMA = "foil.simulated-persona-report.v1"
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
TOP_FIELDS = {"schema", "probe_every", "intent", "demand", "personas"}
PERSONA_FIELDS = {
    "id", "capability", "claimed_strength", "adversarial_profile",
    "true_skill_start", "true_skill_end", "execution_owner", "verifier_available",
    "expected_final_assistance", "initial_events", "independent_outcomes",
    "minimum_effective_assistance",
}
INITIAL_FIELDS = {"correct", "tier", "age_days"}


def _closed(row: Mapping[str, object], fields: set[str], label: str) -> None:
    if set(row) != fields:
        raise ValueError(f"{label} fields mismatch: expected {sorted(fields)}, got {sorted(row)}")


def _probability(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be numeric")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return result


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _initial_observations(value: object) -> list[foil_evidence.Observation]:
    if not isinstance(value, list):
        raise TypeError("initial_events must be a list")
    observations: list[foil_evidence.Observation] = []
    for index, event in enumerate(value):
        if not isinstance(event, Mapping):
            raise TypeError(f"initial event {index} must be an object")
        _closed(event, INITIAL_FIELDS, f"initial event {index}")
        if not isinstance(event["correct"], bool):
            raise TypeError("initial event correct must be bool")
        age = event["age_days"]
        if isinstance(age, bool) or not isinstance(age, int) or age < 0:
            raise TypeError("initial event age_days must be a non-negative int")
        observations.append(
            foil_evidence.Observation(
                correct=event["correct"],
                tier=foil_evidence.EvidenceTier(str(event["tier"])),
                time=NOW - timedelta(days=age),
            )
        )
    return observations


def _outcomes(value: object, label: str) -> list[bool]:
    if not isinstance(value, list) or not value or not all(isinstance(item, bool) for item in value):
        raise TypeError(f"{label} must be a non-empty boolean list")
    return list(value)


def _assistance_series(value: object) -> list[Assistance]:
    if not isinstance(value, list) or not value:
        raise TypeError("minimum_effective_assistance must be a non-empty list")
    return [parse_assistance(item) for item in value]


def _simulate_persona(
    persona: Mapping[str, object], *, probe_every: int, intent: str, demand: str
) -> tuple[dict[str, object], list[dict[str, object]]]:
    _closed(persona, PERSONA_FIELDS, "persona")
    for label in ("claimed_strength", "adversarial_profile", "verifier_available"):
        if not isinstance(persona[label], bool):
            raise TypeError(f"{label} must be bool")
    independent = _outcomes(persona["independent_outcomes"], "independent_outcomes")
    required = _assistance_series(persona["minimum_effective_assistance"])
    if len(independent) != len(required):
        raise ValueError("independent and minimum-assistance lengths must match")
    for index, (outcome, needed) in enumerate(zip(independent, required, strict=True)):
        if outcome is not (needed is Assistance.A0_INDEPENDENT):
            raise ValueError(f"session {index + 1} independent outcome conflicts with minimum assistance")
    expected_final = parse_assistance(persona["expected_final_assistance"])
    start = _probability(persona["true_skill_start"], "true_skill_start")
    end = _probability(persona["true_skill_end"], "true_skill_end")
    observations = _initial_observations(persona["initial_events"])
    initial_summary = foil_evidence.summarize(observations, now=NOW)
    minimum_floor = Assistance.A0_INDEPENDENT
    rows: list[dict[str, object]] = []

    for index, (independent_outcome, needed) in enumerate(
        zip(independent, required, strict=True), start=1
    ):
        before = foil_evidence.summarize(observations, now=NOW)
        probe_due = index % probe_every == 0 and (
            before.classification is not foil_evidence.Classification.PROMISING_STRENGTH
        )
        floor_before = minimum_floor
        decision = select_assistance(
            classification=before,
            intent=intent,
            demand=demand,
            ownership_probe_due=probe_due,
            minimum_assistance=floor_before,
        )
        observed_outcome = decision.assistance.rung >= needed.rung
        tier = foil_profile.derive_tier(
            source="usage",
            verified=persona["verifier_available"],
            assistance=decision.assistance,
            execution_owner=persona["execution_owner"],
        )
        observations.append(
            foil_evidence.Observation(
                correct=observed_outcome,
                tier=foil_evidence.EvidenceTier(tier),
                time=NOW,
                capability=str(persona["capability"]),
                verifier="simulated-ground-truth" if persona["verifier_available"] else None,
            )
        )
        minimum_floor = advance_assistance_floor(
            current=minimum_floor,
            decision=decision,
            observed_outcome=observed_outcome,
        )
        after = foil_evidence.summarize(observations, now=NOW)
        progress = index / len(independent)
        truth = start + (end - start) * progress
        selected_rung, needed_rung = decision.assistance.rung, needed.rung
        under = selected_rung < needed_rung
        over = selected_rung > needed_rung
        planned_ladder_trial = under and (
            probe_due or selected_rung >= floor_before.rung
        )
        rows.append(
            {
                "persona_id": persona["id"],
                "capability": persona["capability"],
                "session": index,
                "truth_probability": truth,
                "predicted_probability": before.posterior_mean,
                "independent_outcome": independent_outcome,
                "observed_outcome": observed_outcome,
                "evidence_tier": tier,
                "classification_before": before.classification.value,
                "classification_after": after.classification.value,
                "selected_assistance": decision.assistance.value,
                "needed_assistance": needed.value,
                "minimum_floor_before": floor_before.value,
                "minimum_floor_after": minimum_floor.value,
                "probe_due": probe_due,
                "over_assistance": over,
                "under_assistance": under,
                "planned_ladder_trial_under_assistance": planned_ladder_trial,
                "unplanned_under_assistance": under and not planned_ladder_trial,
                "over_assistance_after_strength": (
                    before.classification is foil_evidence.Classification.PROMISING_STRENGTH and over
                ),
                "brier": (before.posterior_mean - float(independent_outcome)) ** 2,
                "profile_distance": abs(after.posterior_mean - truth),
            }
        )

    final_summary = foil_evidence.summarize(observations, now=NOW)
    steady = select_assistance(
        classification=final_summary,
        intent=intent,
        demand=demand,
        ownership_probe_due=False,
        minimum_assistance=minimum_floor,
    )
    initial_distance = abs(initial_summary.posterior_mean - start)
    final_distance = abs(final_summary.posterior_mean - end)
    fooled = bool(persona["adversarial_profile"]) and (
        final_summary.classification is foil_evidence.Classification.PROMISING_STRENGTH
    )
    return (
        {
            "persona_id": persona["id"],
            "capability": persona["capability"],
            "claimed_strength": persona["claimed_strength"],
            "adversarial_profile": persona["adversarial_profile"],
            "initial_classification": initial_summary.classification.value,
            "final_classification": final_summary.classification.value,
            "initial_distance": initial_distance,
            "final_distance": final_distance,
            "distance_nonincreasing": final_distance <= initial_distance + 1e-12,
            "load_bearing_n": final_summary.load_bearing_n,
            "final_floor": minimum_floor.value,
            "final_assistance": steady.assistance.value,
            "expected_final_assistance": expected_final.value,
            "fade_correct": steady.assistance is expected_final,
            "fooled": fooled,
        },
        rows,
    )


def run(document: Mapping[str, object]) -> dict[str, object]:
    _closed(document, TOP_FIELDS, "fixture")
    if document.get("schema") != FIXTURE_SCHEMA:
        raise ValueError("unexpected persona fixture schema")
    probe_every = document["probe_every"]
    if isinstance(probe_every, bool) or not isinstance(probe_every, int) or probe_every <= 0:
        raise TypeError("probe_every must be a positive int")
    personas = document["personas"]
    if not isinstance(personas, list) or not 6 <= len(personas) <= 10:
        raise ValueError("persona fixture requires 6-10 personas")
    summaries: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    identifiers: set[str] = set()
    for persona in personas:
        if not isinstance(persona, Mapping):
            raise TypeError("persona must be an object")
        identifier = str(persona.get("id") or "")
        if not identifier or identifier in identifiers:
            raise ValueError("persona ids must be non-empty and unique")
        identifiers.add(identifier)
        summary, persona_rows = _simulate_persona(
            persona,
            probe_every=probe_every,
            intent=str(document["intent"]),
            demand=str(document["demand"]),
        )
        summaries.append(summary)
        rows.extend(persona_rows)
    adversarial = [item for item in summaries if item["adversarial_profile"]]
    fooled = sum(bool(item["fooled"]) for item in adversarial)
    raw_under = sum(bool(row["under_assistance"]) for row in rows)
    planned_under = sum(bool(row["planned_ladder_trial_under_assistance"]) for row in rows)
    persistent_over = sum(bool(row["over_assistance_after_strength"]) for row in rows)
    unplanned_under = sum(bool(row["unplanned_under_assistance"]) for row in rows)
    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "classification": "DETERMINISTIC_SIMULATED_PERSONA_CONFORMANCE_ONLY",
        "personas": len(summaries),
        "sessions": len(rows),
        "metrics": {
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
        },
        "kill_conditions": {
            "fooled_rate_gt_zero": fooled > 0,
            "profile_distance_diverged": any(not item["distance_nonincreasing"] for item in summaries),
            "fade_contract_failed": any(not item["fade_correct"] for item in summaries),
            "over_assistance_persisted_after_strength": persistent_over > 0,
            "unplanned_under_assistance": unplanned_under > 0,
        },
        "persona_summaries": summaries,
        "raw_rows": rows,
        "cost_and_authority": {
            "provider_calls": 0,
            "external_bot_calls": 0,
            "tokens": 0,
            "profile_writes": 0,
            "answer_mutations": 0,
        },
        "non_claims": [
            "not evidence that FOIL improves human learning",
            "not calibration on real people",
            "not production personalization authority",
            "scripted outcomes are known test oracles, not empirical behavior",
        ],
    }
    report["report_sha256"] = _digest(report)
    return report


def load_and_run(path: Path) -> dict[str, object]:
    return run(json.loads(path.read_text(encoding="utf-8")))


def main(argv: Sequence[str] | None = None) -> int:
    path = Path(argv[0]) if argv else ROOT / "benchmarks" / "fixtures" / "foil_personas_v1.json"
    report = load_and_run(path)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if any(report["kill_conditions"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
