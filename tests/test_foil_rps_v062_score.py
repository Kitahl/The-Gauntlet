"""Contract tests for the RPS v0.6.2 paired scorer."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))
sys.path.insert(0, str(ROOT / "tools"))

import foil_rps_v062_score as scorer  # noqa: E402
from foil_rps import CheckKind  # noqa: E402
from foil_rps_v062 import (  # noqa: E402
    HostVerifierOutcome,
    HostVerifierReceipt,
    PrecommittedHostCheck,
    RPSV062Policy,
    check_commitment_digest,
    evaluate_rps_v062_shadow,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def trace(outcome: HostVerifierOutcome) -> dict[str, object]:
    task = digest("task")
    spec = digest("spec")
    commitment = check_commitment_digest(
        task_digest=task,
        answer_form_digest=digest("single label"),
        check_id="check",
        kind=CheckKind.EXACT_RELATION,
        check_spec_digest=spec,
    )
    check = PrecommittedHostCheck(
        task_digest=task,
        answer_form_digest=digest("single label"),
        check_id="check",
        kind=CheckKind.EXACT_RELATION,
        check_spec_digest=spec,
        commitment_digest=commitment,
    )
    receipt = HostVerifierReceipt(
        task_digest=task,
        check_commitment_digest=commitment,
        candidate_digest=digest("answer"),
        outcome=outcome,
        observation_digest=(
            None if outcome is HostVerifierOutcome.NOT_APPLICABLE else digest("obs")
        ),
    )
    return evaluate_rps_v062_shadow(
        check, receipt, policy=RPSV062Policy(enabled=True)
    ).trace()


def row(
    condition: str,
    *,
    correct: bool,
    item_id: str,
    input_tokens: int = 100,
    output_tokens: int = 100,
    decision: dict[str, object] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "benchmark": "x",
        "item_id": item_id,
        "condition": condition,
        "correct": correct,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    if decision is not None:
        result["rps_v062"] = decision
    return result


class RPSV062ScorerTests(unittest.TestCase):
    def load(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            path.write_text(
                "\n".join(json.dumps(value) for value in rows) + "\n",
                encoding="utf-8",
            )
            return scorer.load_jsonl(path)

    def test_abstention_and_rival_request_are_primary_metrics(self):
        abstain = trace(HostVerifierOutcome.CONTRADICTED)
        request = trace(HostVerifierOutcome.NOT_APPLICABLE)
        rows = self.load(
            [
                row("DIRECT", correct=True, item_id="1"),
                row("RPS_062", correct=True, item_id="1", decision=abstain),
                row("DIRECT", correct=False, item_id="2"),
                row("RPS_062", correct=False, item_id="2", decision=request),
            ]
        )
        result = scorer.paired(rows)
        self.assertEqual(result["abstentions"], 1)
        self.assertEqual(result["abstention_rate"], 0.5)
        self.assertEqual(result["rival_requests"], 1)
        self.assertEqual(result["rival_request_rate"], 0.5)
        self.assertEqual(
            result["host_outcome_counts"],
            {"CONTRADICTED": 1, "NOT_APPLICABLE": 1},
        )

    def test_total_cost_includes_input_and_missing_input_fails_gate(self):
        confirmed = trace(HostVerifierOutcome.CONFIRMED)
        rows = self.load(
            [
                row("DIRECT", correct=True, item_id="1", input_tokens=100, output_tokens=100),
                row(
                    "RPS_062",
                    correct=True,
                    item_id="1",
                    input_tokens=200,
                    output_tokens=100,
                    decision=confirmed,
                ),
            ]
        )
        result = scorer.paired(rows)
        self.assertEqual(result["mean_output_token_multiplier"], 1.0)
        self.assertEqual(result["mean_total_token_multiplier"], 1.5)
        self.assertTrue(result["total_cost_gate_evaluable"])

        incomplete = [dict(value) for value in rows]
        del incomplete[1]["input_tokens"]
        result = scorer.paired(incomplete)
        self.assertFalse(result["total_cost_gate_evaluable"])

    def test_tampered_shadow_authority_and_abstention_fail_closed(self):
        tampered = trace(HostVerifierOutcome.CONTRADICTED)
        tampered["answer_mutated"] = True
        with self.assertRaisesRegex(ValueError, "authority invariant"):
            self.load(
                [row("RPS_062", correct=False, item_id="1", decision=tampered)]
            )
        tampered = trace(HostVerifierOutcome.CONTRADICTED)
        tampered["abstained"] = False
        with self.assertRaisesRegex(ValueError, "abstained"):
            self.load(
                [row("RPS_062", correct=False, item_id="1", decision=tampered)]
            )
        tampered = trace(HostVerifierOutcome.CONFIRMED)
        tampered["recommendation"] = "CORRELATED_AGREEMENT"
        tampered["rival_requested"] = True
        tampered["rival_used"] = True
        with self.assertRaisesRegex(ValueError, "correlated-agreement"):
            self.load(
                [row("RPS_062", correct=True, item_id="1", decision=tampered)]
            )

    def test_string_boolean_duplicate_identity_and_unknown_field_fail_closed(self):
        decision = trace(HostVerifierOutcome.CONFIRMED)
        bad = row("RPS_062", correct=True, item_id="1", decision=decision)
        bad["correct"] = "true"
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            self.load([bad])
        duplicate = row("RPS_062", correct=True, item_id="1", decision=decision)
        with self.assertRaisesRegex(ValueError, "duplicate unit identity"):
            self.load([duplicate, duplicate])
        bad = row("RPS_062", correct=True, item_id="1", decision=decision)
        bad["gold"] = "hidden"
        with self.assertRaisesRegex(ValueError, "closed-schema"):
            self.load([bad])


if __name__ == "__main__":
    unittest.main()
