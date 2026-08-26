#!/usr/bin/env python3
"""Zero-provider structural pilot for RPS v0.6.2 transitions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from foil_rps import CheckKind  # noqa: E402
from foil_rps_v062 import (  # noqa: E402
    BlindRivalReceipt,
    HostVerifierOutcome,
    HostVerifierReceipt,
    PrecommittedHostCheck,
    RPSV062Policy,
    check_commitment_digest,
    evaluate_rps_v062_shadow,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def frozen_check() -> PrecommittedHostCheck:
    task_digest = digest("rps-v062-structural-task")
    specification = digest("exact host relation")
    return PrecommittedHostCheck(
        task_digest=task_digest,
        answer_form_digest=digest("single label"),
        check_id="structural-1",
        kind=CheckKind.EXACT_RELATION,
        check_spec_digest=specification,
        commitment_digest=check_commitment_digest(
            task_digest=task_digest,
            answer_form_digest=digest("single label"),
            check_id="structural-1",
            kind=CheckKind.EXACT_RELATION,
            check_spec_digest=specification,
        ),
    )


def host(outcome: HostVerifierOutcome) -> HostVerifierReceipt:
    check = frozen_check()
    return HostVerifierReceipt(
        task_digest=check.task_digest,
        check_commitment_digest=check.commitment_digest,
        candidate_digest=digest("candidate-a"),
        outcome=outcome,
        observation_digest=(
            None
            if outcome is HostVerifierOutcome.NOT_APPLICABLE
            else digest(f"observed:{outcome.value}")
        ),
    )


def rival(answer: str) -> BlindRivalReceipt:
    return BlindRivalReceipt(
        task_digest=frozen_check().task_digest,
        answer_form_digest=digest("single label"),
        rival_digest=digest(answer),
        request_digest=digest("blind task-only request"),
        model_route_digest=digest("frozen synthetic route"),
        incumbent_withheld=True,
        input_tokens=0,
        output_tokens=0,
    )


def run() -> dict[str, object]:
    enabled = RPSV062Policy(enabled=True)
    cases = [
        (
            "disabled",
            evaluate_rps_v062_shadow(
                frozen_check(), host(HostVerifierOutcome.NOT_APPLICABLE)
            ),
            "STAND_DOWN",
        ),
        (
            "host-confirmed",
            evaluate_rps_v062_shadow(
                frozen_check(), host(HostVerifierOutcome.CONFIRMED), policy=enabled
            ),
            "STAND_DOWN",
        ),
        (
            "host-contradicted",
            evaluate_rps_v062_shadow(
                frozen_check(),
                host(HostVerifierOutcome.CONTRADICTED),
                policy=enabled,
            ),
            "ABSTAIN",
        ),
        (
            "not-applicable-needs-rival",
            evaluate_rps_v062_shadow(
                frozen_check(),
                host(HostVerifierOutcome.NOT_APPLICABLE),
                policy=enabled,
            ),
            "REQUEST_BLIND_RIVAL",
        ),
        (
            "blind-agreement",
            evaluate_rps_v062_shadow(
                frozen_check(),
                host(HostVerifierOutcome.UNCERTAIN),
                policy=enabled,
                rival=rival("candidate-a"),
            ),
            "CORRELATED_AGREEMENT",
        ),
        (
            "blind-disagreement",
            evaluate_rps_v062_shadow(
                frozen_check(),
                host(HostVerifierOutcome.UNCERTAIN),
                policy=enabled,
                rival=rival("candidate-b"),
            ),
            "ABSTAIN",
        ),
    ]
    rows = []
    for case_id, decision, expected in cases:
        trace = decision.trace()
        rows.append(
            {
                "case_id": case_id,
                "expected": expected,
                "observed": trace["recommendation"],
                "passed": trace["recommendation"] == expected,
                "trace": trace,
            }
        )
    report: dict[str, object] = {
        "schema": "foil.rps-v062-structural-pilot.v1",
        "classification": "DETERMINISTIC_STRUCTURAL_ONLY",
        "rows": rows,
        "summary": {
            "passed": sum(row["passed"] is True for row in rows),
            "total": len(rows),
            "abstentions": sum(row["observed"] == "ABSTAIN" for row in rows),
            "rival_requests": sum(
                row["trace"]["rival_requested"] is True for row in rows
            ),
            "provider_calls": 0,
            "model_tokens": 0,
            "answer_mutations": 0,
            "execution_authorizations": 0,
            "promotion_authorizations": 0,
        },
        "non_claims": [
            "not behavioral efficacy evidence",
            "not calibration or promotion evidence",
            "not a measurement of model independence or answer quality",
        ],
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["content_sha256"] = digest(canonical)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = report["summary"]
    assert isinstance(summary, dict)
    print(
        f"RPS v0.6.2 structural pilot: {summary['passed']}/{summary['total']} "
        f"sha256={report['content_sha256']}"
    )


if __name__ == "__main__":
    main()
