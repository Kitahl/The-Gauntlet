from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "benchmarks" / "harness"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HARNESS))

import foil_p05_independent_audit as independent_audit  # noqa: E402
import latex_eq  # noqa: E402
import p0_processbench as p05  # noqa: E402


class CertifiedArithmeticParserTests(unittest.TestCase):
    def test_exact_fraction_arithmetic(self) -> None:
        self.assertEqual(latex_eq.evaluate_exact(r"\frac{1}{3} + \frac{1}{6}"), Fraction(1, 2))
        self.assertEqual(latex_eq.evaluate_exact("0.125 * 8"), Fraction(1))

    def test_check_uses_final_certified_language(self) -> None:
        self.assertEqual(latex_eq.check(r"\[2 + 3 = 5\]"), (1, 0))
        self.assertEqual(latex_eq.check(r"\[2 + 3 = 6\]"), (1, 1))

    def test_unsupported_constructs_abstain(self) -> None:
        examples = (
            r"\[5(3) = 15\]",
            r"\[x = 5\]",
            r"\[2 \approx 2.01\]",
            r"\[194 \equiv 7 \pmod{11}\]",
            r"\[2 \text{ books} = 2\]",
            r"\[50\% = 0.5\]",
            r"\[2^3 = 8\]",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertEqual(latex_eq.check(example), (0, 0))

    def test_non_assertive_context_abstains_without_tolerance(self) -> None:
        rounded = "The quotient is approximately: \\(97 \\div 3 = 32.3333\\)"
        rejected_trial = "Let's try this. \\[1 = \\frac{1}{2} + \\frac{1}{3}\\] It is false."
        self.assertEqual(latex_eq.check(rounded), (0, 0))
        self.assertEqual(latex_eq.check(rejected_trial), (0, 0))

    def test_nonterminating_division_display_abstains(self) -> None:
        findings = latex_eq.extract_step(
            r"\(49 \div 9 = 5\)", step_index=0, language=latex_eq.CERTIFIED_LANGUAGE
        )
        self.assertEqual(findings, ())
        legacy_closed = latex_eq.extract_step(
            r"\(49 \div 9 = 5\)", step_index=0, language=latex_eq.CERTIFIED_V1_LANGUAGE
        )
        self.assertEqual(len(legacy_closed), 1)
        self.assertTrue(legacy_closed[0].violating)

    def test_math_span_boundary_is_not_crossed(self) -> None:
        self.assertEqual(latex_eq.check(r"\(2 + 3\) prose \(= 6\)"), (0, 0))

    def test_language_and_ast_bounds_fail_closed(self) -> None:
        with self.assertRaises(latex_eq.UnsupportedExpression):
            latex_eq.evaluate_exact("2**999")
        with self.assertRaises(ValueError):
            latex_eq.extract_step("x", step_index=-1)
        with self.assertRaises(ValueError):
            latex_eq.extract_step("x", step_index=0, language="unknown")

    def test_hash_seed_does_not_change_output(self) -> None:
        script = (
            "import json,sys;sys.path.insert(0,r'"
            + str(HARNESS)
            + "');import latex_eq;print(json.dumps([x.to_dict() for x in "
            "latex_eq.extract_step(r'\\[12/3 = 4\\]',step_index=0)],sort_keys=True))"
        )
        outputs = []
        for seed in ("1", "987654"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            outputs.append(
                subprocess.check_output([sys.executable, "-c", script], env=env, text=True)
            )
        self.assertEqual(outputs[0], outputs[1])


class ProcessBenchScorerTests(unittest.TestCase):
    def _row(self, *, clean: bool, step: str, row_id: str) -> p05.ProcessRow:
        return p05.ProcessRow(
            split="math",
            row_id=row_id,
            generator="Qwen2-7B-Instruct",
            problem="Compute.",
            steps=(step,),
            final_answer_correct=not clean,
            label=-1 if clean else 0,
        )

    def test_label_minus_one_is_the_only_clean_definition(self) -> None:
        clean = self._row(clean=True, step=r"\[2+2=4\]", row_id="clean")
        error = self._row(clean=False, step=r"\[2+2=5\]", row_id="error")
        self.assertTrue(clean.clean)
        self.assertFalse(error.clean)
        self.assertFalse(clean.final_answer_correct)
        self.assertTrue(error.final_answer_correct)

    def test_vacuous_is_distinct_from_admit(self) -> None:
        rows = [
            p05.ScoredRow(self._row(clean=True, step="none", row_id=f"c-{index}"), ())
            for index in range(299)
        ]
        self.assertEqual(p05.summarize(rows)["certificate"]["status"], "VACUOUS")

    def test_minimum_clean_boundary_and_wilson_are_separate(self) -> None:
        self.assertGreater(p05.zero_failure_upper_95(298), 0.01)
        self.assertLessEqual(p05.zero_failure_upper_95(299), 0.01)
        self.assertGreater(p05.wilson_95(0, 299)["upper"], 0.01)

    def test_false_fire_rejects_even_with_large_denominator(self) -> None:
        finding = latex_eq.extract_step(r"\[2+2=5\]", step_index=0)[0]
        rows = [
            p05.ScoredRow(
                self._row(clean=True, step=r"\[2+2=5\]", row_id=f"c-{index}"),
                (finding,) if index == 0 else (),
            )
            for index in range(500)
        ]
        self.assertEqual(p05.summarize(rows)["certificate"]["status"], "REJECT_FALSE_FIRES")

    def test_spearman_reports_constant_vector_as_not_identifiable(self) -> None:
        result = p05.spearman_with_p([1.0, 2.0, 3.0], [0.0, 0.0, 0.0])
        self.assertEqual(result["status"], "NOT_IDENTIFIABLE")

    def test_generator_map_is_closed_over_twelve_models(self) -> None:
        self.assertEqual(len(p05.MODEL_PARAMETERS_BILLIONS), 12)

    @unittest.skipUnless(
        all(
            (
                ROOT / "benchmark_runs" / "foil_p05_processbench" / "data" / f"{split}.parquet"
            ).is_file()
            for split in p05.SPLITS
        ),
        "local pinned ProcessBench parquet files are absent",
    )
    def test_full_corpus_report_is_deterministic_and_zero_fire(self) -> None:
        data_dir = ROOT / "benchmark_runs" / "foil_p05_processbench" / "data"
        rows, manifest = p05.load_rows(data_dir)
        first = p05.build_report(rows, manifest)
        second = p05.build_report(rows, manifest)
        self.assertEqual(first["report_sha256"], second["report_sha256"])
        self.assertEqual(len(first["raw_rows"]), 3400)
        self.assertTrue(
            all(first["subsets"][split]["alpha"]["successes"] == 0 for split in p05.SPLITS)
        )
        self.assertEqual(first["admission"]["decision"], "NOT_ADMITTED_PER_SUBSET_CERTIFICATE")
        json.dumps(first, allow_nan=False)

    @unittest.skipUnless(
        (ROOT / "benchmark_runs" / "foil_p05_processbench" / "p05_report.json").is_file(),
        "frozen local P0.5 report is absent",
    )
    def test_independent_audit_rederives_frozen_report(self) -> None:
        path = ROOT / "benchmark_runs" / "foil_p05_processbench" / "p05_report.json"
        result = independent_audit.verify(json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual(result["verified_rows"], 3400)
        self.assertEqual(result["verified_generators"], 12)


if __name__ == "__main__":
    unittest.main()
