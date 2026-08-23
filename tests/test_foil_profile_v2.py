"""Profile schema v2: verification, execution ownership, and the v1 migration.

v1 promoted ordinary unverified usage straight into competence verdicts. These
tests pin the three conditions v2 requires (verified, independent, user-executed)
and the conservative migration that refuses to inherit v1's counters.

Profiles live outside the repository, so every test redirects
EGR_FOIL_PROFILE_DIR at a temporary directory.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_evidence as ev  # noqa: E402
import foil_profile as fp  # noqa: E402

V1_SCHEMA = "egrt.foil-profile.v1"


def v1_event(outcome: str, *, source: str = "usage", assistance: str = "none",
             time: str = "2026-01-01T00:00:00+00:00") -> dict:
    """An observation exactly as v1 wrote it: no verified/verifier/owner/tier."""
    return {
        "time": time,
        "domain": "formal_reasoning",
        "kind": "performance",
        "outcome": outcome,
        "assistance": assistance,
        "source": source,
        "representation": None,
        "confidence": None,
    }


def v1_profile(events: list[dict], **counters) -> dict:
    row = {
        "state": "ACTIVE",
        "declared": True,
        "relevance_mentions": 1,
        "observations": events,
        "independent_correct": counters.get("independent_correct", 0),
        "independent_incorrect": counters.get("independent_incorrect", 0),
        "assisted_correct": counters.get("assisted_correct", 0),
        "last_seen": None,
        "last_relevant": None,
        "classification": counters.get("classification", "UNCERTAIN"),
    }
    return {
        "schema": V1_SCHEMA,
        "id": "legacy",
        "display_name": "legacy",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "profile_status": "PROVISIONAL",
        "goals": [],
        "preferences": {},
        "domains": {"formal_reasoning": row},
        "calibration": {"observations": 0, "brier_terms": []},
        "events": [],
        "privacy": {"raw_prompts_stored": False},
    }


class ProfileTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EGR_FOIL_PROFILE_DIR": self.temp.name},
                              clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def write_v1(self, profile: dict) -> Path:
        path = fp.path_for(profile["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
        return path


class SchemaTests(ProfileTestCase):
    def test_schema_is_v2(self):
        self.assertEqual(fp.SCHEMA, "egrt.foil-profile.v2")
        self.assertIn(V1_SCHEMA, fp.LEGACY_SCHEMAS)
        self.assertEqual(fp.new_profile("x")["schema"], fp.SCHEMA)


class ObservationRecordingTests(ProfileTestCase):
    def test_every_event_carries_the_three_conditions_and_the_derived_tier(self):
        profile = fp.new_profile("p")
        fp.observe(profile, "d", "correct", "none", verified=True, verifier="rubric")
        event = profile["domains"]["d"]["observations"][0]
        for field in ("verified", "verifier", "execution_owner", "tier"):
            self.assertIn(field, event)
        self.assertTrue(event["verified"])
        self.assertEqual(event["execution_owner"], "USER")
        self.assertEqual(event["tier"], "REAL_WORK")

    def test_verification_defaults_to_false(self):
        profile = fp.new_profile("p")
        fp.observe(profile, "d", "correct", "none")
        event = profile["domains"]["d"]["observations"][0]
        self.assertFalse(event["verified"])
        self.assertEqual(event["tier"], "UNVERIFIED")

    def test_tier_derivation_covers_every_branch(self):
        cases = [
            (dict(source="assessment", verified=False, assistance="none",
                  execution_owner="USER"), "SCREEN"),
            (dict(source="layer2_screen", verified=True, assistance="full",
                  execution_owner="TOOL"), "SCREEN"),
            (dict(source="usage", verified=False, assistance="none",
                  execution_owner="USER"), "UNVERIFIED"),
            (dict(source="usage", verified=True, assistance="A3_PARTIAL_WORKED",
                  execution_owner="USER"), "ASSISTED"),
            (dict(source="usage", verified=True, assistance="none",
                  execution_owner="TOOL"), "ASSISTED"),
            (dict(source="usage", verified=True, assistance="none",
                  execution_owner="SHARED"), "ASSISTED"),
            (dict(source="usage", verified=True, assistance="none",
                  execution_owner="USER"), "REAL_WORK"),
        ]
        for kwargs, expected in cases:
            self.assertEqual(fp.derive_tier(**kwargs), expected, kwargs)

    def test_an_unparseable_assistance_label_is_treated_as_assisted(self):
        """Fail closed: withhold the claim rather than invent independence."""
        self.assertEqual(
            fp.derive_tier(source="usage", verified=True, assistance="banana",
                           execution_owner="USER"),
            "ASSISTED",
        )

    def test_counters_only_move_when_all_three_conditions_hold(self):
        profile = fp.new_profile("p")
        fp.observe(profile, "d", "correct", "none")                      # unverified
        fp.observe(profile, "d", "correct", "full", verified=True, verifier="r")
        fp.observe(profile, "d", "correct", "none", verified=True, verifier="r",
                   execution_owner="TOOL")
        fp.observe(profile, "d", "incorrect", "none", verified=True, verifier="r",
                   execution_owner="SHARED")
        row = profile["domains"]["d"]
        self.assertEqual(row["independent_correct"], 0)
        self.assertEqual(row["independent_incorrect"], 0)
        self.assertEqual(row["assisted_correct"], 3)
        self.assertEqual(row["assisted_incorrect"], 1)
        self.assertEqual(row["classification"], "INSUFFICIENT_EVIDENCE")

    def test_screen_source_names_its_verifier_without_being_told(self):
        profile = fp.new_profile("p")
        fp.observe(profile, "d", "correct", "none", source="assessment")
        self.assertEqual(
            profile["domains"]["d"]["observations"][0]["verifier"],
            "mechanical_assessment_key",
        )


class UnverifiedEvidenceTests(ProfileTestCase):
    def test_one_hundred_unverified_successes_cannot_create_a_strength(self):
        """The exact defect patch-001 closes, at 50x the volume it needed."""
        profile = fp.new_profile("p")
        for _ in range(100):
            fp.observe(profile, "d", "correct", "none")
        row = profile["domains"]["d"]
        self.assertEqual(row["classification"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(row["independent_correct"], 0)
        self.assertEqual(fp.classify(row), "INSUFFICIENT_EVIDENCE")

    def test_one_hundred_unverified_failures_cannot_create_a_gap(self):
        profile = fp.new_profile("p")
        for _ in range(100):
            fp.observe(profile, "d", "incorrect", "none")
        self.assertEqual(profile["domains"]["d"]["classification"], "INSUFFICIENT_EVIDENCE")

    def test_verified_evidence_still_decides(self):
        """Positive control: the same volume minus the verification mutation."""
        profile = fp.new_profile("p")
        for _ in range(5):
            fp.observe(profile, "d", "correct", "none", verified=True, verifier="rubric")
        self.assertEqual(profile["domains"]["d"]["classification"], "PROMISING_STRENGTH")


class D1AcceptanceTests(ProfileTestCase):
    def test_twenty_verified_correct_and_one_incorrect_is_a_strength(self):
        """v1 returned UNCERTAIN here: one miss permanently blocked a strength."""
        profile = fp.new_profile("p")
        for _ in range(20):
            fp.observe(profile, "formal_reasoning", "correct", "none",
                       verified=True, verifier="rubric")
        fp.observe(profile, "formal_reasoning", "incorrect", "none",
                   verified=True, verifier="rubric")
        row = profile["domains"]["formal_reasoning"]
        self.assertEqual(row["independent_correct"], 20)
        self.assertEqual(row["independent_incorrect"], 1)
        self.assertEqual(row["classification"], "PROMISING_STRENGTH")
        self.assertTrue(
            all(e["tier"] == "REAL_WORK" for e in row["observations"])
        )


class MigrationTests(ProfileTestCase):
    def test_three_unverified_passes_do_not_migrate_into_a_strength(self):
        """The v1 counters claimed a strength; the migration refuses to inherit it."""
        legacy = v1_profile(
            [v1_event("correct") for _ in range(3)],
            independent_correct=3,
            classification="PROMISING_STRENGTH",
        )
        self.write_v1(legacy)
        migrated = fp.load("legacy")
        row = migrated["domains"]["formal_reasoning"]
        self.assertEqual(migrated["schema"], fp.SCHEMA)
        self.assertEqual(row["classification"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(row["independent_correct"], 0)
        self.assertEqual(row["assisted_correct"], 3)

    def test_legacy_rows_default_to_unverified(self):
        self.write_v1(v1_profile([v1_event("correct"), v1_event("incorrect")]))
        row = fp.load("legacy")["domains"]["formal_reasoning"]
        for event in row["observations"]:
            self.assertFalse(event["verified"])
            self.assertIsNone(event["verifier"])
            self.assertEqual(event["tier"], "UNVERIFIED")
            self.assertEqual(event["execution_owner"], "USER")

    def test_assessment_source_migrates_to_verified_screen_evidence(self):
        self.write_v1(v1_profile([v1_event("correct", source="assessment") for _ in range(6)]))
        row = fp.load("legacy")["domains"]["formal_reasoning"]
        for event in row["observations"]:
            self.assertTrue(event["verified"])
            self.assertEqual(event["verifier"], "mechanical_assessment_key")
            self.assertEqual(event["tier"], "SCREEN")
        # The counter and the verdict are deliberately different things. The
        # counter records "verified, independent, user-executed", which a
        # mechanically key-scored screen genuinely is. The verdict is computed
        # from evidence *tiers*, where SCREEN weight never reaches the
        # real-work sufficiency gate - so six perfect screen items still decide
        # nothing. Reading the counter as a competence claim is the mistake.
        self.assertEqual(row["independent_correct"], 6)
        self.assertEqual(row["classification"], "INSUFFICIENT_EVIDENCE")

    def test_layer2_source_migrates_to_its_own_screen_key(self):
        self.write_v1(v1_profile([v1_event("correct", source="layer2_screen")]))
        event = fp.load("legacy")["domains"]["formal_reasoning"]["observations"][0]
        self.assertEqual(event["verifier"], "layer2_key")
        self.assertEqual(event["tier"], "SCREEN")

    def test_an_explicit_verified_flag_is_respected(self):
        # Recent timestamps: the fixture default is 2026-01-01, and recency
        # decay alone would sink five real-work observations below the
        # sufficiency gate, which would make this test pass or fail depending
        # on the date it is run.
        recent = datetime.now(timezone.utc).isoformat()
        legacy = v1_profile([v1_event("correct", time=recent) for _ in range(5)])
        for event in legacy["domains"]["formal_reasoning"]["observations"]:
            event["verified"] = True
            event["verifier"] = "rubric"
        self.write_v1(legacy)
        row = fp.load("legacy")["domains"]["formal_reasoning"]
        self.assertEqual(row["independent_correct"], 5)
        self.assertEqual(row["classification"], "PROMISING_STRENGTH")

    def test_original_rows_are_kept_and_provenance_is_recorded(self):
        self.write_v1(v1_profile([v1_event("correct") for _ in range(3)]))
        migrated = fp.load("legacy")
        self.assertEqual(len(migrated["domains"]["formal_reasoning"]["observations"]), 3)
        self.assertEqual(migrated["migrated_from"], V1_SCHEMA)
        self.assertEqual(len(migrated["migrations"]), 1)
        self.assertEqual(migrated["migrations"][0]["migrated_from"], V1_SCHEMA)

    def test_migration_is_deterministic(self):
        legacy = v1_profile([v1_event("correct"), v1_event("incorrect", source="assessment")])
        first, _ = fp.migrate_v1_to_v2(copy.deepcopy(legacy))
        second, _ = fp.migrate_v1_to_v2(copy.deepcopy(legacy))
        first.pop("migrations")
        second.pop("migrations")
        self.assertEqual(first, second)

    def test_migration_is_idempotent(self):
        legacy = v1_profile([v1_event("correct", source="assessment") for _ in range(4)])
        once, changed_once = fp.migrate_v1_to_v2(copy.deepcopy(legacy))
        twice, changed_twice = fp.migrate_v1_to_v2(copy.deepcopy(once))
        self.assertTrue(changed_once)
        self.assertFalse(changed_twice, "a second pass must find nothing left to change")
        self.assertEqual(once, twice)
        self.assertEqual(twice["migrated_from"], V1_SCHEMA,
                         "a re-run must not overwrite where the profile came from")

    def test_loading_a_v2_profile_does_not_re_migrate(self):
        self.write_v1(v1_profile([v1_event("correct")]))
        migrated = fp.load("legacy")
        fp.save(migrated)
        reloaded = fp.load("legacy")
        self.assertEqual(len(reloaded["migrations"]), 1)

    def test_derived_labels_reproduce_from_the_events_alone(self):
        """Every stored aggregate must be recomputable from the observations.

        A counter that cannot be re-derived is a claim about history that
        nothing can check.
        """
        self.write_v1(v1_profile(
            [v1_event("correct", source="assessment") for _ in range(3)]
            + [v1_event("incorrect") for _ in range(2)]
            + [v1_event("correct", assistance="full")],
            independent_correct=99,
            independent_incorrect=99,
            classification="PROMISING_STRENGTH",
        ))
        row = fp.load("legacy")["domains"]["formal_reasoning"]
        derived_independent = sum(
            1 for e in row["observations"]
            if e["verified"]
            and fp.is_independent(e["assistance"])
            and fp.is_user_owned(e["execution_owner"])
        )
        self.assertEqual(row["independent_correct"] + row["independent_incorrect"],
                         derived_independent)
        derived_assisted = sum(
            1 for e in row["observations"]
            if not (e["verified"]
                    and fp.is_independent(e["assistance"])
                    and fp.is_user_owned(e["execution_owner"]))
        )
        self.assertEqual(row["assisted_correct"] + row["assisted_incorrect"],
                         derived_assisted)
        self.assertEqual(row["classification"], fp.classify(row))
        self.assertEqual(
            row["classification"],
            ev.summarize(fp.observations_for(row)).classification.value,
        )


class RelevanceTests(ProfileTestCase):
    def test_marking_relevance_never_writes_competence_state(self):
        """Relevance is routing metadata. v1 documented this; v2 must keep it true."""
        profile = fp.new_profile("p")
        for _ in range(50):
            fp.mark_relevance(profile, ["formal_reasoning", "causal_inference"])
        for name in ("formal_reasoning", "causal_inference"):
            row = profile["domains"][name]
            self.assertEqual(row["observations"], [])
            self.assertEqual(row["independent_correct"], 0)
            self.assertEqual(row["independent_incorrect"], 0)
            self.assertEqual(row["assisted_correct"], 0)
            self.assertEqual(row["assisted_incorrect"], 0)
            self.assertNotIn("classification", row)
            self.assertEqual(fp.classify(row), "INSUFFICIENT_EVIDENCE")
            self.assertGreaterEqual(row["relevance_mentions"], 50)

    def test_declaring_a_domain_is_not_competence_either(self):
        profile = fp.new_profile("p")
        fp.ensure_domain(profile, "security_privacy", declared=True)
        row = profile["domains"]["security_privacy"]
        self.assertEqual(row["state"], "DECLARED_RELEVANT")
        self.assertEqual(fp.classify(row), "INSUFFICIENT_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
