"""D3, D4 - the complement/intervention ledger."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_interventions as iv  # noqa: E402
from foil_assistance import Assistance  # noqa: E402


class InterventionLedgerTests(unittest.TestCase):
    def _ledger(self):
        ledger = iv.new_ledger("p")
        gid = iv.add_gap(ledger, task_id="t1", capability="c", kind="MISSING_PROCEDURE",
                         confidence=0.5)
        iid = iv.add_intervention(ledger, gap_id=gid, complement="scaffold",
                                  assistance_level=Assistance.A2_SCAFFOLD)
        return ledger, iid

    def test_documented_ladder_label_is_recorded_not_discarded(self):
        """v1 returned NO_VERIFIED_OUTCOME for the documented A0 label."""
        ledger, iid = self._ledger()
        iv.add_outcome(ledger, intervention_id=iid, phase="independent", result="pass",
                       verified=True, assistance="A0_INDEPENDENT", verifier="rubric")
        self.assertEqual(iv.intervention_status(ledger, iid)["status"],
                         "INDEPENDENT_SUCCESS_OBSERVED")

    def test_later_verified_failure_supersedes_an_earlier_pass(self):
        """v1 returned TRANSFER_OBSERVED for one old pass and five later fails."""
        ledger, iid = self._ledger()
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        iv.add_outcome(ledger, intervention_id=iid, phase="transfer", result="pass", verified=True,
                       assistance="A0_INDEPENDENT", verifier="rubric",
                       observed_at=base.isoformat())
        for day in range(1, 6):
            iv.add_outcome(ledger, intervention_id=iid, phase="transfer", result="fail",
                           verified=True, assistance="A0_INDEPENDENT", verifier="rubric",
                           observed_at=(base + timedelta(days=day)).isoformat())
        status = iv.intervention_status(ledger, iid)
        self.assertEqual(status["status"], "VERIFIED_FAILURE_OBSERVED")
        self.assertIn("transfer", status["superseded_phases"])

    def test_assisted_outcome_cannot_support_transfer(self):
        ledger, iid = self._ledger()
        iv.add_outcome(ledger, intervention_id=iid, phase="transfer", result="pass", verified=True,
                       assistance="A3_PARTIAL_WORKED", verifier="rubric")
        self.assertEqual(iv.intervention_status(ledger, iid)["status"], "NO_VERIFIED_OUTCOME")

    def test_verified_outcome_must_name_a_verifier(self):
        ledger, iid = self._ledger()
        with self.assertRaises(ValueError):
            iv.add_outcome(ledger, intervention_id=iid, phase="immediate", result="pass",
                           verified=True, assistance="A0_INDEPENDENT")

    def test_unknown_assistance_level_is_rejected_at_write_time(self):
        ledger = iv.new_ledger("p")
        gid = iv.add_gap(ledger, task_id="t", capability="c", kind="UNKNOWN", confidence=0.5)
        with self.assertRaises(ValueError):
            iv.add_intervention(ledger, gap_id=gid, complement="c", assistance_level="banana")

    def test_ids_are_content_addressed_not_index_derived(self):
        ledger, _ = self._ledger()
        gid2 = iv.add_gap(ledger, task_id="t2", capability="d", kind="EVIDENCE_GAP",
                          confidence=0.2)
        ledger["gaps"] = [row for row in ledger["gaps"] if row["id"] == gid2]
        gid3 = iv.add_gap(ledger, task_id="t3", capability="e", kind="EVIDENCE_GAP",
                          confidence=0.2)
        self.assertNotEqual(gid2, gid3)
        self.assertEqual(len({row["id"] for row in ledger["gaps"]}), len(ledger["gaps"]))


class ExecutionOwnershipTests(unittest.TestCase):
    """A tool-executed pass is task evidence, never ownership evidence."""

    def _ledger(self):
        ledger = iv.new_ledger("p")
        gid = iv.add_gap(ledger, task_id="t1", capability="c", kind="TOOL_OR_ARTIFACT_GAP",
                         confidence=0.5)
        iid = iv.add_intervention(ledger, gap_id=gid, complement="tool",
                                  assistance_level=Assistance.A0_INDEPENDENT)
        return ledger, iid

    def test_owner_is_stored_on_the_row(self):
        ledger, iid = self._ledger()
        oid = iv.add_outcome(ledger, intervention_id=iid, phase="immediate", result="pass",
                             verified=True, assistance="A0_INDEPENDENT", verifier="rubric",
                             execution_owner="tool")
        row = next(r for r in ledger["outcomes"] if r["id"] == oid)
        self.assertEqual(row["execution_owner"], "TOOL")

    def test_default_owner_is_user(self):
        ledger, iid = self._ledger()
        oid = iv.add_outcome(ledger, intervention_id=iid, phase="immediate", result="pass",
                             verified=True, assistance="A0_INDEPENDENT", verifier="rubric")
        row = next(r for r in ledger["outcomes"] if r["id"] == oid)
        self.assertEqual(row["execution_owner"], "USER")

    def test_tool_and_shared_outcomes_cannot_support_the_upper_phases(self):
        for owner in ("TOOL", "SHARED"):
            for phase in ("independent", "transfer", "defense"):
                ledger, iid = self._ledger()
                iv.add_outcome(ledger, intervention_id=iid, phase=phase, result="pass",
                               verified=True, assistance="A0_INDEPENDENT", verifier="rubric",
                               execution_owner=owner)
                self.assertEqual(
                    iv.intervention_status(ledger, iid)["status"],
                    "NO_VERIFIED_OUTCOME",
                    f"{owner} execution supported {phase}",
                )

    def test_user_owned_outcome_still_supports_the_upper_phases(self):
        """Positive control: the same input minus the ownership mutation passes."""
        ledger, iid = self._ledger()
        iv.add_outcome(ledger, intervention_id=iid, phase="defense", result="pass",
                       verified=True, assistance="A0_INDEPENDENT", verifier="rubric",
                       execution_owner="USER")
        self.assertEqual(iv.intervention_status(ledger, iid)["status"],
                         "DEFENSIBLE_OBSERVED")

    def test_tool_execution_may_still_record_an_immediate_success(self):
        ledger, iid = self._ledger()
        iv.add_outcome(ledger, intervention_id=iid, phase="immediate", result="pass",
                       verified=True, assistance="A0_INDEPENDENT", verifier="rubric",
                       execution_owner="TOOL")
        self.assertEqual(iv.intervention_status(ledger, iid)["status"],
                         "IMMEDIATE_SUCCESS_ONLY")

    def test_unknown_owner_is_rejected_at_write_time(self):
        ledger, iid = self._ledger()
        with self.assertRaises(ValueError):
            iv.add_outcome(ledger, intervention_id=iid, phase="immediate", result="pass",
                           verified=True, assistance="A0_INDEPENDENT", verifier="rubric",
                           execution_owner="banana")

    def test_legacy_rows_without_the_field_read_as_user_owned(self):
        ledger, iid = self._ledger()
        iv.add_outcome(ledger, intervention_id=iid, phase="transfer", result="pass",
                       verified=True, assistance="A0_INDEPENDENT", verifier="rubric")
        for row in ledger["outcomes"]:
            row.pop("execution_owner", None)
        self.assertEqual(iv.intervention_status(ledger, iid)["status"],
                         "TRANSFER_OBSERVED")


if __name__ == "__main__":
    unittest.main()
