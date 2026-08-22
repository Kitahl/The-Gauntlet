from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_equalizer as fe  # noqa: E402
import foil_profile as fp  # noqa: E402


class FoilEqualizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EGR_FOIL_PROFILE_DIR": self.temp.name}, clear=False)
        self.env.start()
        profile = fp.new_profile("stranger")
        fp.save(profile)
        fp.activate("stranger")

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_blank_profile_plan_covers_all_capability_families(self) -> None:
        profile = fp.load()
        plan = fe.build_plan(profile, max_probes=24)
        families = {probe["family"] for probe in plan["probes"]}
        self.assertTrue(set(fe.FAMILY_TARGETS).issubset(families))
        self.assertEqual(plan["coverage_before"]["status"], "NOT_STARTED")

    def test_repeated_same_facet_cannot_satisfy_family_balance(self) -> None:
        profile = fp.load()
        for i in range(4):
            fe.record(
                profile,
                probe_id=f"p{i}",
                family="reasoning_representation",
                facet="verbal_reasoning",
                domain="cross_domain",
                kind="qualifier_preservation",
                outcome="pass",
                assistance="none",
                verified=True,
                representation=f"r{i}",
            )
        state = fe.coverage(profile)
        self.assertEqual(state["family_distinct_facets"]["reasoning_representation"], 1)
        self.assertIn("reasoning_representation", state["missing_families"])

    def test_assisted_or_unverified_results_do_not_count(self) -> None:
        profile = fp.load()
        fe.record(profile, probe_id="a", family="reasoning_representation", facet="verbal_reasoning", domain="cross_domain", kind="qualifier_preservation", outcome="pass", assistance="full", verified=True)
        fe.record(profile, probe_id="b", family="reasoning_representation", facet="spatial_structural_reasoning", domain="cross_domain", kind="structure_transform", outcome="pass", assistance="none", verified=False)
        self.assertEqual(fe.coverage(profile)["family_distinct_facets"]["reasoning_representation"], 0)

    def test_arbitrary_relevant_domain_gets_profile_dependent_probe(self) -> None:
        profile = fp.load()
        fp.ensure_domain(profile, "rare_custom_domain", declared=True)
        plan = fe.build_plan(profile, max_probes=30)
        self.assertTrue(any(probe["domain"] == "rare_custom_domain" for probe in plan["probes"]))

    def test_delayed_retrieval_cannot_be_scored_immediately(self) -> None:
        profile = fp.load()
        plan = fe.build_plan(profile, max_probes=30)
        delayed = next(probe for probe in plan["probes"] if probe["kind"] == "delayed_unassisted_retrieval")
        with self.assertRaises(ValueError):
            fe.record(
                profile,
                probe_id=delayed["probe_id"],
                family=delayed["family"],
                facet=delayed["facet"],
                domain=delayed["domain"],
                kind=delayed["kind"],
                outcome="pass",
                assistance="none",
                verified=True,
            )

    def test_record_must_match_issued_probe_contract(self) -> None:
        profile = fp.load()
        plan = fe.build_plan(profile, max_probes=30)
        probe = plan["probes"][0]
        with self.assertRaises(ValueError):
            fe.record(
                profile,
                probe_id=probe["probe_id"],
                family=probe["family"],
                facet=probe["facet"],
                domain="wrong_domain",
                kind=probe["kind"],
                outcome="pass",
                assistance="none",
                verified=True,
            )

    def test_high_stakes_urgent_task_has_max_verification_min_friction(self) -> None:
        profile = fp.load()
        policy = fe.recommend_policy(profile, "Check the current official version and fix the repository build", stakes="high", goal="learning", urgency="urgent")
        self.assertEqual(policy["verification_intensity"], "maximum")
        self.assertEqual(policy["pedagogical_friction"], "minimal")
        self.assertEqual(policy["support_mode"], "direct_verified")
        self.assertIn("current_primary_source", policy["preferred_verifiers"])
        self.assertIn("execution_or_test", policy["preferred_verifiers"])

    def test_cold_promising_strength_does_not_enable_independent_first(self) -> None:
        profile = fp.load()
        fp.ensure_domain(profile, "formal_reasoning", declared=True)
        fp.observe(profile, "formal_reasoning", "correct", "none", representation="screen-a")
        fp.observe(profile, "formal_reasoning", "correct", "none", representation="screen-b")
        policy = fe.recommend_policy(profile, "Prove this theorem", goal="learning")
        self.assertNotEqual(policy["support_mode"], "independent_first")

    def test_current_fact_requires_external_verification_without_profile_evidence(self) -> None:
        policy = fe.recommend_policy(fp.load(), "What is the latest stable release version?")
        self.assertEqual(policy["verification_intensity"], "high")
        self.assertIn("current_primary_source", policy["preferred_verifiers"])

    def test_high_fidelity_requires_delayed_retention(self) -> None:
        profile = fp.load()
        fp.ensure_domain(profile, "formal_reasoning", declared=True)
        counter = 0
        for family, target in fe.FAMILY_TARGETS.items():
            facets = [facet for facet, fam in fe.FACET_FAMILY.items() if fam == family]
            for i in range(target):
                counter += 1
                kind = "harder_transfer" if counter <= 3 else "generic"
                if counter in {4, 5}:
                    kind = "real_work"
                if counter in {6, 7}:
                    kind = "adversarial_claim"
                fe.record(profile, probe_id=f"x{counter}", family=family, facet=facets[i], domain="formal_reasoning", kind=kind, outcome="pass", assistance="none", verified=True, confidence=80, representation=f"r{counter}")
        state = fe.coverage(profile)
        self.assertNotEqual(state["status"], "HIGH_FIDELITY_PROFILE")
        self.assertIn("delayed_unassisted_retrieval", state["missing_extra"])

    def test_issued_delayed_probe_can_be_recorded_after_not_before(self) -> None:
        profile = fp.load()
        plan = fe.build_plan(profile, max_probes=30)
        delayed = next(probe for probe in plan["probes"] if probe["kind"] == "delayed_unassisted_retrieval")
        state = profile["universal_refinement"]
        state["issued"][delayed["probe_id"]]["not_before"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        fe.record(profile, probe_id=delayed["probe_id"], family=delayed["family"], facet=delayed["facet"], domain=delayed["domain"], kind=delayed["kind"], outcome="pass", assistance="none", verified=True, confidence=75, representation="delayed-novel-case")
        self.assertEqual(fe.coverage(profile)["coverage"]["delayed_unassisted_retrieval"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
