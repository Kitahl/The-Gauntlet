"""Deterministic synthetic integration pilot for the arithmetic rule bank."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_host_finalizer import answer_digest  # noqa: E402
from egrt_types import digest, text_digest  # noqa: E402
from foil_arithmetic_rule_bank import (  # noqa: E402
    RULE_BANK_ROUTE_ID,
    discover_arithmetic_rule_bank,
)
from foil_obligation_compiler import compile_task_spec  # noqa: E402
from foil_obligation_discovery import DiscoveryPolicy, DiscoveryStatus  # noqa: E402
from foil_residual_scanner import scan  # noqa: E402
from foil_v5_metrics import ScanStatus  # noqa: E402

PROTOCOL_ID = "foil-certified-arithmetic-rule-bank-small-pilot.v1"
TASK_TEXT = "Check the arithmetic trace mechanically."
IMPLEMENTATION_FILES = (
    "tools/foil_certified_arithmetic.py",
    "tools/foil_arithmetic_rule_bank.py",
    "tools/egrt_verifiers.py",
    "tools/foil_obligation_compiler.py",
    "tools/foil_obligation_discovery_admission.py",
    "benchmarks/FOIL_CERTIFIED_ARITHMETIC_RULE_BANK_SMALL_PILOT.md",
    "benchmarks/harness/foil_certified_rule_bank_pilot.py",
    "benchmarks/harness/foil_certified_rule_bank_audit.py",
)
CASES: tuple[dict[str, str], ...] = (
    {
        "case_id": "v2-correct",
        "class": "CORRECT",
        "rule": "certified-v2",
        "answer": r"\[\frac{1}{3}+\frac{1}{6}=\frac{1}{2}\]",
        "expected": "PASS",
    },
    {
        "case_id": "v2-defect",
        "class": "DEFECT",
        "rule": "certified-v2",
        "answer": r"\[\frac{1}{3}+\frac{1}{6}=\frac{2}{3}\]",
        "expected": "FAIL",
    },
    {
        "case_id": "power-correct",
        "class": "CORRECT",
        "rule": "numeric-power-equality-v1",
        "answer": r"\[3^4=81\]",
        "expected": "PASS",
    },
    {
        "case_id": "power-defect",
        "class": "DEFECT",
        "rule": "numeric-power-equality-v1",
        "answer": r"\[3^4=82\]",
        "expected": "FAIL",
    },
    {
        "case_id": "raw-correct",
        "class": "CORRECT",
        "rule": "raw-numeric-equality-v1",
        "answer": "1. 12 / 3 = 4",
        "expected": "PASS",
    },
    {
        "case_id": "raw-defect",
        "class": "DEFECT",
        "rule": "raw-numeric-equality-v1",
        "answer": "1. 12 / 3 = 5",
        "expected": "FAIL",
    },
    {
        "case_id": "trace-correct",
        "class": "CORRECT",
        "rule": "trace-constraint-consistency-v1",
        "answer": "6B = 30; B = 5",
        "expected": "PASS",
    },
    {
        "case_id": "trace-defect",
        "class": "DEFECT",
        "rule": "trace-constraint-consistency-v1",
        "answer": "6B = 30; B = 4",
        "expected": "FAIL",
    },
    {
        "case_id": "prose-unsupported",
        "class": "UNSUPPORTED",
        "rule": "NONE",
        "answer": "Therefore x = 4.",
        "expected": "PARTIAL",
    },
    {
        "case_id": "unit-unsupported",
        "class": "UNSUPPORTED",
        "rule": "NONE",
        "answer": "12 kg = 12.",
        "expected": "PARTIAL",
    },
    {
        "case_id": "percent-unsupported",
        "class": "UNSUPPORTED",
        "rule": "NONE",
        "answer": "50% = 0.5",
        "expected": "PARTIAL",
    },
    {
        "case_id": "rounded-unsupported",
        "class": "UNSUPPORTED",
        "rule": "NONE",
        "answer": r"The quotient is approximately \(97 \div 3 = 32.3333\).",
        "expected": "PARTIAL",
    },
)


def _request(answer: str) -> dict[str, str]:
    return {
        "task_text": TASK_TEXT,
        "a0_text": answer,
        "task_digest": text_digest(TASK_TEXT),
        "a0_digest": answer_digest(answer),
    }


def _file_sha256(relative_path: str) -> str:
    text = (ROOT / relative_path).read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _observed(envelope: object) -> str:
    if envelope.status is not DiscoveryStatus.FOUND or envelope.task_spec is None:
        return envelope.status.value
    compiled = compile_task_spec(
        envelope.task_spec,
        observed_a0_digest=envelope.a0_digest,
    )
    statuses = tuple(
        scan(plan, envelope.a0_digest, compiled.deterministic_cases(plan.claim_id)).status
        for plan in compiled.deterministic_scanner_plans()
    )
    return "FAIL" if ScanStatus.FAIL in statuses else "PASS"


def build_report() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case in CASES:
        request = _request(case["answer"])
        disabled = discover_arithmetic_rule_bank(request)
        envelope = discover_arithmetic_rule_bank(
            request,
            policy=DiscoveryPolicy(enabled=True),
        )
        observed = _observed(envelope)
        rows.append(
            {
                **case,
                "answer_sha256": request["a0_digest"],
                "default_off_status": disabled.status.value,
                "discovery_status": envelope.status.value,
                "observed": observed,
                "matched": observed == case["expected"],
                "origin": envelope.origin,
                "a0_preserved": envelope.base_answer == case["answer"],
                "rule_counts": dict(envelope.rule_counts),
                "provider_calls": envelope.provider_calls,
                "token_count": envelope.token_count,
                "profile_writes": envelope.profile_writes,
                "action_count": envelope.action_count,
                "execution_authorized": envelope.execution_authorized,
                "answer_mutated": envelope.answer_mutated,
            }
        )
    controls = [row for row in rows if row["class"] == "CORRECT"]
    defects = [row for row in rows if row["class"] == "DEFECT"]
    unsupported = [row for row in rows if row["class"] == "UNSUPPORTED"]
    report: dict[str, Any] = {
        "schema": "foil.certified-arithmetic-rule-bank-pilot.report.v1",
        "protocol_id": PROTOCOL_ID,
        "route": RULE_BANK_ROUTE_ID,
        "classification": "SYNTHETIC_INTEGRATION_ONLY",
        "implementation_sha256": {
            path: _file_sha256(path) for path in IMPLEMENTATION_FILES
        },
        "decision": (
            "PASS_SYNTHETIC_INTEGRATION"
            if all(row["matched"] for row in rows)
            else "FAIL_SYNTHETIC_INTEGRATION"
        ),
        "counts": {
            "attempted": len(rows),
            "executed": sum(row["discovery_status"] == "FOUND" for row in rows),
            "unsupported_or_partial": sum(
                row["discovery_status"] in {"PARTIAL", "ABSTAIN", "UNSUPPORTED"}
                for row in rows
            ),
            "matched": sum(row["matched"] for row in rows),
            "controls": len(controls),
            "control_false_fires": sum(row["observed"] == "FAIL" for row in controls),
            "defects": len(defects),
            "defects_detected": sum(row["observed"] == "FAIL" for row in defects),
            "unsupported_cases": len(unsupported),
            "unsupported_stood_down": sum(
                row["observed"] in {"PARTIAL", "ABSTAIN", "UNSUPPORTED"}
                for row in unsupported
            ),
        },
        "cost_and_authority": {
            "provider_calls": sum(row["provider_calls"] for row in rows),
            "token_count": sum(row["token_count"] for row in rows),
            "profile_writes": sum(row["profile_writes"] for row in rows),
            "action_count": sum(row["action_count"] for row in rows),
            "execution_authority_count": sum(
                bool(row["execution_authorized"]) for row in rows
            ),
            "answer_mutation_count": sum(bool(row["answer_mutated"]) for row in rows),
            "promotion_count": 0,
        },
        "conservation": {
            "attempted_equals_executed_plus_stand_down": (
                len(rows)
                == sum(row["discovery_status"] == "FOUND" for row in rows)
                + sum(
                    row["discovery_status"] in {"PARTIAL", "ABSTAIN", "UNSUPPORTED"}
                    for row in rows
                )
            )
        },
        "raw_rows": rows,
        "non_claims": (
            "not a false-fire probability estimate",
            "not natural-error recall or extraction-recall evidence",
            "not calibration, admission, promotion, or frontier-model evidence",
        ),
    }
    report["report_sha256"] = digest(report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = build_report()
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "report_sha256": report["report_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["decision"] == "PASS_SYNTHETIC_INTEGRATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
