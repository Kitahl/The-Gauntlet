from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_claims import Applicability, Decidability  # noqa: E402
from foil_obligation_compiler import (  # noqa: E402
    COMPILER_DIGEST,
    COMPILER_VERSION,
    TASK_SPEC_SCHEMA,
    TaskSpecError,
    compile_task_spec,
    main,
)
from foil_residual_scanner import scan  # noqa: E402
from foil_v5_metrics import summarize_metrics  # noqa: E402


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def deterministic_obligation(key: str = "sum", start: int = 1, end: int = 2) -> dict[str, object]:
    return {
        "obligation_key": key,
        "description": f"Declared exact arithmetic check {key}",
        "weight_range": {"start": start, "end": end},
        "predicate_kind": "EXACT_ARITHMETIC",
        "verifier_id": "builtin.exact_arithmetic",
        "verifier_version": "1",
        "verifier_input": {"expression": "2 + 3", "expected": "5"},
    }


def semantic_obligation() -> dict[str, object]:
    return {
        "obligation_key": "semantic-residual",
        "description": "Explicit semantic residual",
        "weight_range": {"start": 3, "end": 3},
        "predicate_kind": "EXACT_MATCH",
        "verifier_id": "builtin.exact_match",
        "verifier_version": "1",
        "verifier_input": {"actual": "declared", "expected": "declared"},
    }


def spec() -> dict[str, object]:
    return {
        "schema": TASK_SPEC_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "task_digest": d("task"),
        "a0_digest": d("a0"),
        "config_digest": d("config"),
        "claims": [
            {
                "claim_key": "deterministic-claim",
                "statement_digest": d("exact statement"),
                "claim_kind": "EXACT_ARITHMETIC",
                "decidability": "DETERMINISTIC",
                "applicability": "APPLICABLE",
                "reason": "An exact builtin predicate is declared.",
                "obligations": [deterministic_obligation()],
            },
            {
                "claim_key": "semantic-claim",
                "statement_digest": d("semantic statement"),
                "claim_kind": "OTHER",
                "decidability": "SEMANTIC",
                "applicability": "APPLICABLE",
                "reason": "A semantic residual is not a deterministic claim.",
                "obligations": [semantic_obligation()],
            },
        ],
    }


class ObligationCompilerTests(unittest.TestCase):
    def compile(self, value: dict[str, object] | None = None):
        value = spec() if value is None else value
        return compile_task_spec(value, observed_a0_digest=value["a0_digest"])

    def test_stable_multi_claim_compilation_and_deterministic_plan_conversion(self):
        left = self.compile()
        right = self.compile(copy.deepcopy(spec()))
        self.assertEqual(left.source_spec_digest, right.source_spec_digest)
        self.assertEqual(left.compilation_digest, right.compilation_digest)
        self.assertEqual(left.summary.compiler_digest, COMPILER_DIGEST)
        self.assertEqual(left.summary.compiled_count, 1)
        self.assertEqual(left.summary.semantic_count, 1)
        self.assertEqual(
            (left.summary.deterministic_obligation_count, left.summary.residual_obligation_count),
            (1, 1),
        )
        plans = left.deterministic_scanner_plans()
        self.assertEqual(len(plans), 1)
        self.assertEqual(len(left.deterministic_cases(plans[0].claim_id)), 1)
        report = scan(
            plans[0], left.bindings.a0_digest, left.deterministic_cases(plans[0].claim_id)
        )
        self.assertEqual(report.status.value, "PASS")

    def test_semantic_claim_cannot_become_green_or_decidable_coverage(self):
        compiled = self.compile()
        semantic = next(item for item in compiled.claims if item.claim_key == "semantic-claim")
        self.assertIsNone(semantic.claim)
        self.assertEqual(semantic.decidability, Decidability.SEMANTIC)
        self.assertTrue(all(item.case is None for item in semantic.obligations))
        metrics = summarize_metrics(tuple(item.need for item in semantic.obligations))
        self.assertFalse(semantic.obligations[0].need.coverage_requirement().is_decidable)
        self.assertEqual(metrics.weighted.decidable_mass, 0)
        self.assertEqual(metrics.weighted.undecidable_mass, 1)
        self.assertEqual(
            compiled.deterministic_scanner_plans()[0].needs[0].applicability,
            Applicability.APPLICABLE,
        )

    def test_closed_schema_rejects_unknown_fields_omissions_and_unknown_predicates(self):
        cases: list[tuple[str, dict[str, object]]] = []
        extra_root = spec()
        extra_root["guessed_threshold"] = 0.9
        cases.append(("root unknown", extra_root))
        missing_applicability = spec()
        del missing_applicability["claims"][0]["applicability"]  # type: ignore[index]
        cases.append(("claim omission", missing_applicability))
        missing_weight = spec()
        del missing_weight["claims"][0]["obligations"][0]["weight_range"]  # type: ignore[index]
        cases.append(("weight omission", missing_weight))
        unknown_kind = spec()
        unknown_kind["claims"][0]["obligations"][0]["predicate_kind"] = "PROSE_MAGIC"  # type: ignore[index]
        cases.append(("unknown predicate", unknown_kind))
        missing_tolerance = spec()
        row = missing_tolerance["claims"][0]["obligations"][0]  # type: ignore[index]
        row.update(
            {
                "predicate_kind": "NUMERIC_TOLERANCE",
                "verifier_id": "builtin.numeric_tolerance",
                "verifier_input": {"actual": "1", "expected": "1"},
            }
        )
        cases.append(("input omission", missing_tolerance))
        for name, value in cases:
            with self.subTest(name=name):
                with self.assertRaises(TaskSpecError):
                    self.compile(value)

    def test_registry_version_input_binding_and_label_leakage_fail_closed(self):
        unknown_verifier = spec()
        unknown_verifier["claims"][0]["obligations"][0]["verifier_id"] = "builtin.unknown"  # type: ignore[index]
        wrong_version = spec()
        wrong_version["claims"][0]["obligations"][0]["verifier_version"] = "999"  # type: ignore[index]
        extra_input = spec()
        extra_input["claims"][0]["obligations"][0]["verifier_input"]["gold_label"] = "5"  # type: ignore[index]
        nested_leak = spec()
        nested_leak["claims"][1]["obligations"][0]["verifier_input"]["actual"] = {"gold": "x"}  # type: ignore[index]
        for name, value in (
            ("unknown verifier", unknown_verifier),
            ("wrong registry version", wrong_version),
            ("extra label input", extra_input),
            ("nested label leak", nested_leak),
        ):
            with self.subTest(name=name):
                with self.assertRaises(TaskSpecError):
                    self.compile(value)

    def test_cli_unknown_verifier_fails_without_traceback(self):
        bad = spec()
        bad["claims"][0]["obligations"][0]["verifier_id"] = "builtin.unknown"  # type: ignore[index]
        stderr = io.StringIO()
        with (
            patch("foil_obligation_compiler._load_json", return_value=bad),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as stopped,
        ):
            main(["ignored.json", "--observed-a0-digest", bad["a0_digest"]])
        self.assertEqual(stopped.exception.code, 2)
        self.assertIn("closed registry", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_binding_digests_duplicate_ids_and_weight_overlap_fail_closed(self):
        uppercase = spec()
        uppercase["a0_digest"] = uppercase["a0_digest"].upper()  # type: ignore[index]
        malformed = spec()
        malformed["task_digest"] = "not-a-digest"
        duplicate_claim = spec()
        duplicate_claim["claims"].append(copy.deepcopy(duplicate_claim["claims"][0]))  # type: ignore[index]
        duplicate_obligation = spec()
        duplicate_obligation["claims"][1]["obligations"][0]["obligation_key"] = "sum"  # type: ignore[index]
        overlap = spec()
        overlap["claims"][0]["obligations"].append(deterministic_obligation("second", 2, 4))  # type: ignore[index]
        for name, value in (
            ("uppercase digest", uppercase),
            ("malformed digest", malformed),
            ("duplicate claim", duplicate_claim),
            ("duplicate obligation", duplicate_obligation),
            ("overlap", overlap),
        ):
            with self.subTest(name=name):
                with self.assertRaises(TaskSpecError):
                    self.compile(value)
        with self.assertRaises(TaskSpecError):
            compile_task_spec(spec(), observed_a0_digest=d("other-a0"))

    def test_example_is_closed_json_and_cli_summary_is_digest_only(self):
        example = json.loads(
            (ROOT / "validation" / "foil_v5_task_spec.example.json").read_text("utf-8")
        )
        compiled = compile_task_spec(example, observed_a0_digest=example["a0_digest"])
        self.assertEqual(compiled.summary.compiler_version, COMPILER_VERSION)
        source = (ROOT / "tools" / "foil_obligation_compiler.py").read_text("utf-8")
        for forbidden in ("requests", "urllib", "socket", "subprocess", "importlib"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
