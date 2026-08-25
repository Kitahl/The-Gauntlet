from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import foil_r17_independent_audit as independent_audit  # noqa: E402
import foil_r17_provenance_repair_pilot as protocol  # noqa: E402
import foil_r17_provenance_repair_runner as runner  # noqa: E402


CLEAR = "First <<2*3=6>>6. Then <<6+4=10>>10. Finally <<10*1=10>>10.\nA: 10"
DEFECT = "First <<2*3=5>>5. Then <<5+4=9>>9. Finally <<9*1=9>>9.\nA: 9"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _records() -> list[protocol.SourceResponse]:
    rows: list[protocol.SourceResponse] = []
    for index in range(12):
        question = f"A box test {index} has 2 rows, 3 jars, and adds 4."
        answer = DEFECT + f"\nWrong note {index}."
        rows.append(
            protocol.SourceResponse(
                _digest(question), _digest(answer), question, CLEAR,
                protocol.MODEL_VARIANTS[index % 4], answer, False,
            )
        )
    for index in range(40):
        question = f"A control test {index} has 2 rows, 3 jars, and adds 4."
        answer = CLEAR + f"\nClear note {index}."
        rows.append(
            protocol.SourceResponse(
                _digest(question), _digest(answer), question, CLEAR,
                protocol.MODEL_VARIANTS[index % 4], answer, True,
            )
        )
    return rows


class R17ProtocolTests(unittest.TestCase):
    def test_r16_exclusions_are_digest_bound_and_nontrivial(self) -> None:
        labels = (ROOT / "benchmarks" / "data" / "foil_r16_natural_labels.json").read_bytes()
        report = (ROOT / "benchmarks" / "results" / "foil_r16_no_oracle_discovery_report.json").read_bytes()
        excluded = protocol.load_r16_exclusions(labels, report)
        self.assertGreaterEqual(len(excluded), 60)
        with self.assertRaisesRegex(RuntimeError, "label exclusion digest"):
            protocol.load_r16_exclusions(labels + b" ", report)

    def test_fresh_selection_is_deterministic_and_disjoint(self) -> None:
        records = _records()
        exclusions = {_digest("old-question")}
        first_bases, first_attempts, first_candidates = runner.frozen_candidate_rows(records, exclusions)
        second_bases, second_attempts, second_candidates = runner.frozen_candidate_rows(tuple(reversed(records)), exclusions)
        self.assertEqual([row.question_sha256 for row in first_bases], [row.question_sha256 for row in second_bases])
        self.assertEqual(first_attempts, second_attempts)
        self.assertEqual([row.identity for row in first_candidates], [row.identity for row in second_candidates])
        self.assertEqual(len(first_bases), 4)
        self.assertEqual(len(first_attempts), 28)
        self.assertFalse({row.question_sha256 for row in first_bases} & {row.question_sha256 for row in first_candidates})

    def test_decision_rule_boundaries_are_frozen(self) -> None:
        self.assertEqual(runner._decision(4, 7, 7), "FAIL_NOISY")
        self.assertEqual(runner._decision(0, 2, 5), "FAIL_RECALL")
        self.assertEqual(runner._decision(1, 6, 7), "SMOKE_PROMISING")
        self.assertEqual(runner._decision(2, 6, 7), "INCONCLUSIVE")

    def test_report_rederives_and_rejects_tampering(self) -> None:
        records = _records()
        exclusions = {_digest("old-question")}
        _, _, candidates = runner.frozen_candidate_rows(records, exclusions)
        labels = {
            row.identity: protocol.NATURAL_LABELS[index % len(protocol.NATURAL_LABELS)]
            for index, row in enumerate(candidates)
        }
        with self.assertRaisesRegex(RuntimeError, "frozen implementation"):
            runner.build_report(records, labels, exclusions, protocol_commit="1" * 40)
        report = runner.build_report(
            records, labels, exclusions, protocol_commit=protocol.FROZEN_PROTOCOL_COMMIT
        )
        runner.independently_verify_report(report)
        self.assertEqual(report["selection"]["correct_controls"], 20)
        self.assertEqual(report["mutation_conservation"]["attempted"], 28)
        self.assertEqual(report["cost_and_authority"]["token_spend"], 0)
        tampered = copy.deepcopy(report)
        tampered["raw_rows"][0]["detected"] = not tampered["raw_rows"][0]["detected"]
        with self.assertRaisesRegex(RuntimeError, "digest mismatch"):
            runner.independently_verify_report(tampered)

    def test_frozen_report_rederives_in_independent_implementation(self) -> None:
        report = json.loads(
            (ROOT / "benchmarks" / "results" / "foil_r17_provenance_repair_report.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(independent_audit.audit(report)["verified"])


if __name__ == "__main__":
    unittest.main()
