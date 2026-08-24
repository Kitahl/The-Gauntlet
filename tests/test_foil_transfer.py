"""Tests for the isolated, fail-closed FOIL P2 controllers."""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_interventions as interventions  # noqa: E402
import foil_transfer as transfer  # noqa: E402


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def ledger(
    *,
    phase="transfer",
    result="pass",
    verified=True,
    assistance="A0_INDEPENDENT",
    owner="USER",
    changed=True,
    effect=None,
    when="2026-08-20T00:00:00+00:00",
):
    outcome = {
        "id": "o1",
        "intervention_id": "i1",
        "phase": phase,
        "result": result,
        "verified": verified,
        "assistance": assistance,
        "execution_owner": owner,
        "effect": effect,
        "observed_at": when,
        "verifier": "rubric",
    }
    if changed:
        outcome["changed_context"] = {
            "context_sha256": digest("new context"),
            "prior_context_sha256": digest("old context"),
        }
    return {
        "gaps": [{"id": "g1", "kind": "MISSING_PROCEDURE", "capability": "reasoning"}],
        "interventions": [{"id": "i1", "gap_id": "g1", "complement": "worked cue"}],
        "outcomes": [outcome],
    }


class TransferSelectionTests(unittest.TestCase):
    def test_positive_transfer_is_selected_and_receipt_has_no_raw_content(self):
        result = transfer.select_transfer(ledger(), capability="reasoning")
        self.assertEqual(result["selection"], "SELECTED")
        self.assertEqual(result["authority"], transfer.SignalAuthority.CONTROL_ONLY.value)
        self.assertTrue(result["raw_content_stored"] is False)
        self.assertNotIn("reasoning", json.dumps(result))
        self.assertNotIn("worked cue", json.dumps(result))

    def test_stale_one_off_assisted_and_non_user_do_not_select(self):
        for changes in (
            {"phase": "immediate"},
            {"changed": False},
            {"when": "2020-01-01T00:00:00+00:00"},
            {"assistance": "A1_MICRO_HINT"},
            {"owner": "TOOL"},
            {"owner": None},
            {"assistance": "bad"},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(
                    transfer.select_transfer(ledger(**changes))["selection"], "NOT_SELECTED"
                )

    def test_harm_takeover_and_redundancy_block(self):
        for effect in transfer.BLOCKING_EFFECTS:
            with self.subTest(effect=effect):
                result = transfer.select_transfer(ledger(effect=effect))
                self.assertEqual(result["selection"], "NOT_SELECTED")
                self.assertIn("BLOCKED", result["reason"])

    def test_later_verified_failure_supersedes_pass(self):
        item = ledger()
        item["outcomes"].append(
            {
                "id": "o2",
                "intervention_id": "i1",
                "phase": "transfer",
                "result": "fail",
                "verified": True,
                "assistance": "A0_INDEPENDENT",
                "execution_owner": "USER",
                "observed_at": "2026-08-21T00:00:00+00:00",
            }
        )
        self.assertEqual(
            transfer.select_transfer(item)["reason"], "SUPERSEDED_BY_LATER_VERIFIED_FAILURE"
        )

    def test_history_requires_digest_changed_context_and_carries_no_raw_values(self):
        item = ledger()
        history = transfer.structured_transfer_history(item)
        self.assertTrue(history[0]["changed_context_confirmed"])
        self.assertNotIn("reasoning", json.dumps(history))
        self.assertNotIn("worked cue", json.dumps(history))
        item["outcomes"][0]["changed_context"] = {
            "context_sha256": "new",
            "prior_context_sha256": "old",
        }
        self.assertEqual(transfer.select_transfer(item)["selection"], "NOT_SELECTED")

    def test_canonical_ledger_supports_digest_only_changed_context(self):
        item = interventions.new_ledger("profile")
        gap_id = interventions.add_gap(
            item,
            task_id="task",
            capability="communication",
            kind="PRESENTATION_GAP",
            confidence=0.8,
        )
        intervention_id = interventions.add_intervention(
            item,
            gap_id=gap_id,
            complement="presentation refinement",
            assistance_level="A1_MICRO_HINT",
        )
        interventions.add_outcome(
            item,
            intervention_id=intervention_id,
            phase="transfer",
            result="pass",
            verified=True,
            assistance="A0_INDEPENDENT",
            verifier="rubric",
            observed_at="2026-08-22T00:00:00+00:00",
            context_sha256=digest("new representation"),
            prior_context_sha256=digest("old representation"),
        )
        receipt = transfer.select_transfer(
            item,
            capability="communication",
            reference_time=transfer.datetime(2026, 8, 23, tzinfo=transfer.timezone.utc),
        )
        self.assertEqual(receipt["selection"], "SELECTED")
        self.assertNotIn("presentation refinement", json.dumps(receipt))
        with self.assertRaises(ValueError):
            interventions.add_outcome(
                item,
                intervention_id=intervention_id,
                phase="transfer",
                result="pass",
                verified=True,
                assistance="A0_INDEPENDENT",
                verifier="rubric",
                context_sha256=digest("only one digest"),
            )


class SelfRefineTests(unittest.TestCase):
    def setUp(self):
        self.draft = digest("draft")
        self.feedback = {"presentation_only": True}
        self.revision = {
            "revision_count": 1,
            "revision_sha256": digest("revision"),
            "factual_changed": False,
            "evidence_changed": False,
            "claim_changed": False,
            "content_changed": False,
        }
        self.recheck = {
            "verifier_sha256": digest("verifier"),
            "contract_pass": True,
            "style_pass": True,
            "content_unchanged": True,
            "evidence_unchanged": True,
        }

    def run_refine(self, **overrides):
        args = dict(
            enabled=True,
            gap_kind="PRESENTATION_GAP",
            draft_sha256=self.draft,
            feedback_categories=["clarity", "style"],
            feedback=self.feedback,
            revision=self.revision,
            recheck=self.recheck,
        )
        args.update(overrides)
        return transfer.run_self_refine(**args)

    def test_disabled_by_default_and_ablation_costs_are_independent(self):
        row = transfer.run_self_refine(gap_kind="PRESENTATION_GAP", draft_sha256=self.draft)
        self.assertEqual(row["reason"], "DISABLED")
        self.assertEqual(row["costs"]["model_calls"], 0)
        self.assertNotEqual(
            transfer.self_refine_ablation_trace(draft_sha256=self.draft, enabled=False)["arm"],
            transfer.self_refine_ablation_trace(draft_sha256=self.draft, enabled=True)["arm"],
        )

    def test_presentation_only_refinement_accepts_one_checked_revision(self):
        row = self.run_refine()
        self.assertEqual(row["status"], "ACCEPTED")
        self.assertEqual(
            row["costs"],
            {
                "model_calls": 0,
                "tool_calls": 0,
                "network_calls": 0,
                "feedback_rounds": 1,
                "revisions": 1,
            },
        )

    def test_refinement_rejects_nonpresentation_budget_content_and_evidence_upgrade(self):
        cases = (
            {"gap_kind": "MISSING_KNOWLEDGE"},
            {"revision": {**self.revision, "revision_count": 2}},
            {"revision": {**self.revision, "evidence_changed": True}},
            {"recheck": {**self.recheck, "verifier_sha256": None}},
            {"recheck": {**self.recheck, "evidence_unchanged": False}},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(self.run_refine(**changes)["status"], "REJECTED")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
