from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_route_opportunity import (  # noqa: E402
    QUESTION_INPUT_SCHEMA,
    build_prediction_artifact,
    discover_route_opportunity,
    score_prediction_artifact,
    validate_prediction_artifact,
)


class ClosedQuestionInputTests(unittest.TestCase):
    def _task(self, question: str) -> dict[str, object]:
        return {
            "schema": QUESTION_INPUT_SCHEMA,
            "task_id": "task-1",
            "question": question,
        }

    def test_answer_and_gold_fields_are_rejected(self) -> None:
        for forbidden in ("a0", "gold", "is_correct", "expected_output"):
            raw = self._task("What is 2 + 2?") | {forbidden: "hidden"}
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(ValueError, "closed schema mismatch"):
                    discover_route_opportunity(raw)

    def test_positive_question_changes_prediction(self) -> None:
        first = discover_route_opportunity(
            self._task("What exact output does this Python program return?")
        ).trace()
        second = discover_route_opportunity(
            self._task("Who painted the Mona Lisa?")
        ).trace()
        self.assertNotEqual(first["question_digest"], second["question_digest"])
        self.assertNotEqual(first["status"], second["status"])

    def test_known_structural_routes(self) -> None:
        code = discover_route_opportunity(
            self._task("What exact output does this Python code return at runtime?")
        )
        legal = discover_route_opportunity(
            self._task(
                "Which section of the Employment Rights Act governs this statutory instrument?"
            )
        )
        plain = discover_route_opportunity(self._task("Who painted the Mona Lisa?"))
        self.assertIn("CODE_EXECUTION", [row.capability for row in code.candidates])
        self.assertIn("WEB_SEARCH", [row.capability for row in legal.candidates])
        self.assertEqual(plain.status.value, "UNSUPPORTED")


class FrozenArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        run_dir = ROOT / "benchmark_runs" / "2026-08-26" / "hle_active_20"
        cls.items = json.loads((run_dir / "items.json").read_text(encoding="utf-8"))
        cls.audit = json.loads(
            (run_dir / "independent_audit.json").read_text(encoding="utf-8")
        )

    def test_prediction_uses_only_id_and_question(self) -> None:
        original = build_prediction_artifact(self.items)
        changed = copy.deepcopy(self.items)
        for row in changed["items"]:
            row["arm"] = "HIDDEN-CHANGED"
            row["category"] = "HIDDEN-CHANGED"
            row["answer_type"] = "HIDDEN-CHANGED"
            row["source_id"] = "HIDDEN-CHANGED"
        self.assertEqual(original, build_prediction_artifact(changed))
        self.assertEqual(original["input_fields_used"], ["id", "question"])

    def test_current_manifest_is_zero_cost_and_conserved(self) -> None:
        artifact = build_prediction_artifact(self.items)
        self.assertEqual(len(artifact["predictions"]), 20)
        self.assertEqual(set(artifact["cost_and_authority"].values()), {0})
        self.assertEqual(
            len({row["task_id"] for row in artifact["predictions"]}),
            20,
        )
        validate_prediction_artifact(artifact)

    def test_tampering_fails_hash_validation(self) -> None:
        artifact = build_prediction_artifact(self.items)
        artifact["predictions"][0]["status"] = "UNSUPPORTED"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_prediction_artifact(artifact)

    def test_scoring_reproduces_the_sealed_denominators(self) -> None:
        artifact = build_prediction_artifact(self.items)
        report = score_prediction_artifact(artifact, self.audit)
        self.assertEqual((report["questions"], report["audit_rows"]), (20, 60))
        self.assertEqual(sum(report["status_counts"].values()), 20)
        self.assertTrue(
            report["repeated_configuration_rows_are_not_independent_questions"]
        )
        found = report["status_outcomes"]["FOUND"]
        unsupported = report["status_outcomes"]["UNSUPPORTED"]
        self.assertEqual(
            (found["questions"], found["base_wrong_rows"], found["historical_rescue_rows"]),
            (17, 40, 6),
        )
        self.assertEqual((unsupported["questions"], unsupported["base_wrong_rows"]), (3, 9))
        self.assertEqual(set(report["cost_and_authority"].values()), {0})

    def test_duplicate_or_missing_audit_units_fail_closed(self) -> None:
        artifact = build_prediction_artifact(self.items)
        duplicate = copy.deepcopy(self.audit)
        duplicate["rows"].append(copy.deepcopy(duplicate["rows"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate unit_id"):
            score_prediction_artifact(artifact, duplicate)

        missing = copy.deepcopy(self.audit)
        suffix = self.items["items"][0]["source_id"]
        missing["rows"] = [
            row for row in missing["rows"] if not row["unit_id"].endswith(suffix)
        ]
        with self.assertRaisesRegex(ValueError, "every frozen task"):
            score_prediction_artifact(artifact, missing)


if __name__ == "__main__":
    unittest.main()
