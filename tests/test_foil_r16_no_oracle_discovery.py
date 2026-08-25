from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from egrt_host_finalizer import answer_digest  # noqa: E402
from egrt_verifiers import DEFAULT_REGISTRY, VerificationStatus, canonical_rational  # noqa: E402
from foil_obligation_discovery import (  # noqa: E402
    MAX_TASK_CHARS,
    DiscoveryPolicy,
    DiscoveryRequestError,
    DiscoveryStatus,
    discover_obligations,
)
from foil_obligation_discovery_admission import compile_admitted_discovery  # noqa: E402

import foil_r16_no_oracle_discovery_pilot as protocol  # noqa: E402
import foil_r16_no_oracle_discovery_runner as runner  # noqa: E402
import foil_r16_no_oracle_operators as operators  # noqa: E402


QUESTION = "A store has 2 boxes with 3 jars each, adds 4 jars, and keeps 1 group."
CLEAR = (
    "Boxes give <<2*3=6>>6 jars. Adding gives <<6+4=10>>10 jars. "
    "One group gives <<10*1=10>>10 jars.\nA: 10"
)
DEFECT = (
    "Boxes give <<2*3=5>>5 jars. Adding gives <<5+4=9>>9 jars. "
    "One group gives <<9*1=9>>9 jars.\nA: 9"
)


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def request(answer: str = CLEAR) -> dict[str, str]:
    return {
        "task_text": QUESTION,
        "a0_text": answer,
        "task_digest": d(QUESTION),
        "a0_digest": answer_digest(answer),
    }


class DiscoveryBoundaryTests(unittest.TestCase):
    def test_default_off_and_enabled_found_preserve_exact_a0(self) -> None:
        base = CLEAR
        disabled = discover_obligations(request(base))
        enabled = discover_obligations(
            request(base), policy=DiscoveryPolicy(enabled=True)
        )
        self.assertIs(disabled.status, DiscoveryStatus.ABSTAIN)
        self.assertIs(enabled.status, DiscoveryStatus.FOUND)
        self.assertIs(enabled.base_answer, base)
        self.assertEqual(enabled.a0_digest, answer_digest(base))
        self.assertEqual(enabled.origin, "GENERATED_UNADMITTED")
        self.assertTrue(enabled.admission_required)
        self.assertFalse(enabled.execution_authorized)
        self.assertFalse(enabled.answer_mutated)
        self.assertEqual(enabled.provider_calls, 0)
        self.assertEqual(enabled.profile_writes, 0)
        self.assertEqual(enabled.action_count, 0)

    def test_request_is_closed_and_gold_cannot_affect_output(self) -> None:
        first_hidden = {"gold": "10", "is_correct": True}
        second_hidden = {"gold": "999", "is_correct": False}
        first = discover_obligations(request(), policy=DiscoveryPolicy(enabled=True))
        second = discover_obligations(request(), policy=DiscoveryPolicy(enabled=True))
        self.assertNotEqual(first_hidden, second_hidden)
        self.assertEqual(first.to_dict(), second.to_dict())
        for forbidden in ("gold", "ground_truth", "is_correct", "expected"):
            bad = request()
            bad[forbidden] = "hidden"
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(DiscoveryRequestError):
                    discover_obligations(bad, policy=DiscoveryPolicy(enabled=True))

    def test_a0_change_is_positive_control_and_digest_binding_is_enforced(self) -> None:
        first = discover_obligations(request(CLEAR), policy=DiscoveryPolicy(enabled=True))
        second = discover_obligations(request(DEFECT), policy=DiscoveryPolicy(enabled=True))
        self.assertNotEqual(first.envelope_digest, second.envelope_digest)
        bad = request(CLEAR)
        bad["a0_digest"] = d("other")
        with self.assertRaises(DiscoveryRequestError):
            discover_obligations(bad, policy=DiscoveryPolicy(enabled=True))

    def test_partial_abstain_and_bounds_fail_closed(self) -> None:
        no_final = CLEAR.rsplit("\n", 1)[0]
        malformed = "Work <<2+3=nope>>.\nA: 5"
        plain = "The answer appears to be five."
        oversized_question = "x" * (MAX_TASK_CHARS + 1)
        cases = (
            (no_final, DiscoveryStatus.PARTIAL),
            (malformed, DiscoveryStatus.PARTIAL),
            (plain, DiscoveryStatus.ABSTAIN),
        )
        for answer, expected in cases:
            with self.subTest(expected=expected):
                self.assertIs(
                    discover_obligations(
                        request(answer), policy=DiscoveryPolicy(enabled=True)
                    ).status,
                    expected,
                )
        oversized = {
            "task_text": oversized_question,
            "a0_text": CLEAR,
            "task_digest": d(oversized_question),
            "a0_digest": d(CLEAR),
        }
        self.assertIs(
            discover_obligations(
                oversized, policy=DiscoveryPolicy(enabled=True)
            ).status,
            DiscoveryStatus.UNSUPPORTED,
        )

    def test_unadmitted_envelope_cannot_use_production_admission_bridge(self) -> None:
        envelope = discover_obligations(request(), policy=DiscoveryPolicy(enabled=True))
        with self.assertRaisesRegex(TypeError, "FormalizationAdmissionReceipt"):
            compile_admitted_discovery(envelope, admission=object())


class NumericVerifierAndScannerTests(unittest.TestCase):
    def test_canonical_rational_and_numeric_provenance(self) -> None:
        self.assertEqual(canonical_rational("-3/2"), "-3/2")
        with self.assertRaises(ValueError):
            canonical_rational("2/4")
        passed = DEFAULT_REGISTRY.run(
            "builtin.numeric_provenance",
            {"operands": ["2/1", "3/1"], "sources": ["2/1", "3/1", "5/1"]},
        )
        failed = DEFAULT_REGISTRY.run(
            "builtin.numeric_provenance",
            {"operands": ["9/1"], "sources": ["2/1", "3/1"]},
        )
        unknown = DEFAULT_REGISTRY.run(
            "builtin.numeric_provenance",
            {"operands": ["2/4"], "sources": ["1/2"]},
        )
        self.assertIs(passed.status, VerificationStatus.PASS)
        self.assertIs(failed.status, VerificationStatus.FAIL)
        self.assertIs(unknown.status, VerificationStatus.UNKNOWN)

    def test_exact_arithmetic_provenance_and_final_consistency_signals(self) -> None:
        clear = runner.evaluate_answer(QUESTION, CLEAR)
        result_error = runner.evaluate_answer(QUESTION, DEFECT)
        provenance_error = runner.evaluate_answer(
            QUESTION,
            "Bad root <<2*99=198>>198. Then <<198+4=202>>202. "
            "End <<202*1=202>>202.\nA: 202",
        )
        final_error = runner.evaluate_answer(QUESTION, CLEAR[:-2] + "11")
        self.assertFalse(clear.detected)
        self.assertTrue(result_error.detected)
        self.assertTrue(provenance_error.detected)
        self.assertTrue(final_error.detected)
        self.assertTrue(clear.a0_preserved)


class MutationContractTests(unittest.TestCase):
    def test_all_seven_operators_execute_and_conserve_denominators(self) -> None:
        attempts = operators.attempt_all(d(QUESTION), QUESTION, CLEAR)
        self.assertEqual(tuple(item.operator_id for item in attempts), protocol.OPERATORS)
        self.assertTrue(all(item.status == "EXECUTED" for item in attempts))
        self.assertTrue(all(item.mutant != CLEAR for item in attempts))
        conserved = operators.conservation(attempts)
        self.assertEqual(conserved["attempted"], 7)
        self.assertTrue(conserved["conserved"])
        self.assertTrue(
            all(item["conserved"] for item in conserved["by_operator"].values())
        )

    def test_equivalent_and_unsupported_attempts_are_not_executed(self) -> None:
        equivalent = operators._attempt(d(QUESTION), "M1_RESULT", CLEAR, lambda: CLEAR)
        unsupported = operators.mutate(d(QUESTION), QUESTION, "No annotations.\nA: 1", "M1_RESULT")
        self.assertEqual(equivalent.status, "EQUIVALENT")
        self.assertIsNone(equivalent.mutant)
        self.assertEqual(unsupported.status, "UNSUPPORTED")
        self.assertIsNone(unsupported.mutant)

    def test_mutation_base_selection_is_deterministic_and_complete(self) -> None:
        records = tuple(
            protocol.SourceResponse(
                d(f"question-{index}"),
                d(CLEAR),
                QUESTION + f" Case {index}.",
                CLEAR,
                protocol.MODEL_VARIANTS[index % 4],
                CLEAR,
                True,
            )
            for index in range(12)
        )
        first_bases, first_attempts = runner.select_mutation_bases(records)
        second_bases, second_attempts = runner.select_mutation_bases(tuple(reversed(records)))
        self.assertEqual(
            tuple(item.question_sha256 for item in first_bases),
            tuple(item.question_sha256 for item in second_bases),
        )
        self.assertEqual(first_attempts, second_attempts)
        self.assertEqual(len(first_bases), 8)
        self.assertEqual(len(first_attempts), 56)


class StatisticsAndReportTests(unittest.TestCase):
    def test_wilson_interval_and_typed_non_identifiability(self) -> None:
        interval = runner.wilson_95(0, 14)
        self.assertEqual(interval["interval_name"], "Wilson two-sided 95%")
        self.assertEqual(interval["lower"], 0.0)
        self.assertGreater(float(interval["upper"]), 0.0)
        mutation = {
            label: runner.wilson_95(8 if index < 2 else 4, 8)
            for index, label in enumerate(protocol.NATURAL_LABELS)
        }
        natural = {
            label: runner.wilson_95(2, 2)
            for label in protocol.NATURAL_LABELS
        }
        result = runner.association(mutation, natural)
        self.assertEqual(result["status"], "NOT_IDENTIFIABLE")
        self.assertIn("NATURAL_RATE_VECTOR_ZERO_VARIANCE", result["reason_codes"])

    def test_exact_permutation_spearman_is_computed_when_estimable(self) -> None:
        mutation = {
            label: runner.wilson_95(index + 1, 8)
            for index, label in enumerate(protocol.NATURAL_LABELS)
        }
        natural = {
            label: runner.wilson_95(1 if index < 3 else 2, 2)
            for index, label in enumerate(protocol.NATURAL_LABELS)
        }
        result = runner.association(mutation, natural)
        self.assertEqual(result["status"], "ESTIMABLE_SMOKE_ONLY")
        self.assertEqual(result["exact_permutation_count"], 5040)
        self.assertIsNotNone(result["spearman"])
        self.assertIsNotNone(result["pearson_descriptive"])

    def test_report_rederives_from_hash_only_rows_and_rejects_tampering(self) -> None:
        records: list[protocol.SourceResponse] = []
        for index in range(14):
            question = QUESTION + f" Natural {index}."
            records.append(
                protocol.SourceResponse(
                    d(question),
                    d(DEFECT + str(index)),
                    question,
                    CLEAR,
                    protocol.MODEL_VARIANTS[index % 4],
                    DEFECT + f"\nNote {index}.",
                    False,
                )
            )
        for index in range(14):
            question = QUESTION + f" Control {index}."
            records.append(
                protocol.SourceResponse(
                    d(question),
                    d(CLEAR + str(index)),
                    question,
                    CLEAR,
                    protocol.MODEL_VARIANTS[index % 4],
                    CLEAR + f"\nNote {index}.",
                    True,
                )
            )
        candidates = protocol.candidate_rows(records)
        labels = {
            row.identity: protocol.NATURAL_LABELS[index // 2]
            for index, row in enumerate(candidates)
        }
        report = runner.build_report(records, labels, protocol_commit="1" * 40)
        runner.independently_verify_report(report)
        self.assertEqual(report["selection"]["mapped_natural_misses"], 14)
        self.assertEqual(report["selection"]["correct_controls"], 14)
        self.assertEqual(report["mutation_conservation"]["attempted"], 56)
        self.assertEqual(report["cost_and_authority"]["provider_calls"], 0)
        self.assertEqual(report["cost_and_authority"]["token_spend"], 0)
        self.assertEqual(report["cost_and_authority"]["answer_mutations_by_foil"], 0)
        tampered = copy.deepcopy(report)
        tampered["raw_rows"][0]["detected"] = not tampered["raw_rows"][0]["detected"]
        with self.assertRaisesRegex(RuntimeError, "digest mismatch"):
            runner.independently_verify_report(tampered)


if __name__ == "__main__":
    unittest.main()
