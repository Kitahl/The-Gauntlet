"""Build the target-derived FOIL calibration report from frozen artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_smart_tool_calibration import (  # noqa: E402
    BenchmarkTarget,
    HistoricalRouteEvidence,
    assess_historical_route,
    calibrate_target,
)


REPORT_SCHEMA = "foil.smart-tool-target-calibration-report.v1"


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def build_report(
    independent_audit: Mapping[str, object],
    trace_audit: Mapping[str, object],
    mechanical_replay: Mapping[str, object],
    *,
    target: BenchmarkTarget,
) -> dict[str, object]:
    summaries = _mapping(independent_audit.get("summaries"), "summaries")
    no_tools = _mapping(summaries.get("FOIL"), "FOIL summary")
    tools = _mapping(summaries.get("FOIL_TOOLS"), "FOIL_TOOLS summary")
    if trace_audit.get("calibration_gate") != "FAIL":
        raise ValueError("trace audit is not the expected failed calibration gate")
    if trace_audit.get("admissible_rescue_rows") != 0:
        raise ValueError("retrieval rescue rows unexpectedly became admissible")
    calibration = calibrate_target(target)
    no_tool_decision = assess_historical_route(
        HistoricalRouteEvidence(
            route_id="RPS_NO_TOOLS_SECOND_PASS",
            attempts=int(no_tools["n"]),
            rescues=int(no_tools["rescues"]),
            damages=int(no_tools["published_damages"]),
            invalid_outcomes=int(no_tools["n"]) - int(no_tools["final_valid"]),
            total_extra_tokens=int(no_tools["route_tokens"]),
            auditable=True,
            evidence_reason="frozen_posthoc_independent_raw_row_audit",
        ),
        calibration,
    )
    retrieval_decision = assess_historical_route(
        HistoricalRouteEvidence(
            route_id="UNRESTRICTED_RETRIEVAL_SECOND_PASS",
            attempts=int(tools["n"]),
            rescues=int(tools["rescues"]),
            damages=int(tools["published_damages"]),
            invalid_outcomes=int(tools["n"]) - int(tools["final_valid"]),
            total_extra_tokens=int(tools["route_tokens"]),
            auditable=False,
            evidence_reason="rescues_not_attributable_to_clean_saved_tool_evidence",
        ),
        calibration,
    )
    mechanical_decision = assess_historical_route(
        HistoricalRouteEvidence(
            route_id="DETERMINISTIC_HLE_ACTIVE_VERIFY",
            attempts=int(mechanical_replay["active_verify_calls"]),
            rescues=int(mechanical_replay["rescues"]),
            damages=int(mechanical_replay["damages"]),
            invalid_outcomes=0,
            total_extra_tokens=int(mechanical_replay["token_spend"]),
            auditable=True,
            evidence_reason="frozen_zero_token_mechanical_replay",
        ),
        calibration,
    )
    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "classification": "HISTORICAL_DEVELOPMENT_CALIBRATION",
        "target": calibration.trace(),
        "route_decisions": [
            no_tool_decision.trace(),
            retrieval_decision.trace(),
            mechanical_decision.trace(),
        ],
        "runtime_policy": {
            "no_tools_interjection_answer_change": "DISABLED",
            "retrieval_answer_change": "DISABLED",
            "retrieval_supporting_only": True,
            "deterministic_active_verify_benchmark": "ENABLED",
            "deterministic_active_verify_production": "UNADMITTED",
            "a0_fallback_on_decline_or_failure": True,
        },
        "ability_boundary": {
            "no_tools_can_generate_blind_rival": True,
            "no_tools_can_select_rival_without_discriminator": False,
            "rps_v062_rival_can_replace_a0": False,
            "factual_retrieval_without_tools": False,
            "deterministic_interjection_can_reject_contradiction": True,
        },
        "provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "new_token_spend": 0,
        "promotion_authorized": False,
        "non_claims": [
            "not a new HLE score",
            "not a forecast of 22 correct",
            "not retrieval calibration",
            "not evidence that textual entailment is mechanically solved",
        ],
    }
    report["report_sha256"] = digest(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("independent_audit", type=Path)
    parser.add_argument("trace_audit", type=Path)
    parser.add_argument("mechanical_replay", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows", type=int, default=60)
    parser.add_argument("--baseline-correct", type=int, default=11)
    parser.add_argument("--target-correct", type=int, default=22)
    parser.add_argument("--maximum-total-tokens", type=int, default=250_000)
    args = parser.parse_args()
    report = build_report(
        _object(args.independent_audit),
        _object(args.trace_audit),
        _object(args.mechanical_replay),
        target=BenchmarkTarget(
            benchmark_rows=args.rows,
            baseline_correct=args.baseline_correct,
            target_correct=args.target_correct,
            maximum_total_tokens=args.maximum_total_tokens,
        ),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(report["report_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
