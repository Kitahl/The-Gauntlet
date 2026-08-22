from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_calibration as fc  # noqa: E402
import foil_profile as fp  # noqa: E402


class FoilCalibrationTests(unittest.TestCase):
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

    def test_blank_profile_gets_domain_discovery_and_cross_cutting_probes(self) -> None:
        profile = fp.load()
        plan = fc.build_plan(profile)
        kinds = {probe["kind"] for probe in plan["probes"]}
        self.assertIn("representative_work", kinds)
        self.assertIn("formalization", kinds)
        self.assertIn("adversarial_error_detection", kinds)
        self.assertEqual(plan["maturity"]["status"], "NOT_STARTED")

    def test_promising_strength_gets_harder_transfer_probe(self) -> None:
        profile = fp.load()
        fp.ensure_domain(profile, "formal_reasoning", declared=True)
        fp.observe(profile, "formal_reasoning", "correct", "none", representation="proof-a")
        fp.observe(profile, "formal_reasoning", "correct", "none", representation="proof-b")
        plan = fc.build_plan(profile)
        probes = [p for p in plan["probes"] if p["domain"] == "formal_reasoning"]
        self.assertTrue(any(p["kind"] == "harder_transfer" for p in probes))

    def test_possible_gap_gets_discriminator_not_permanent_label(self) -> None:
        profile = fp.load()
        fp.ensure_domain(profile, "probability_statistics", declared=True)
        fp.observe(profile, "probability_statistics", "incorrect", "none", representation="fraction")
        fp.observe(profile, "probability_statistics", "incorrect", "none", representation="bayes")
        self.assertEqual(profile["domains"]["probability_statistics"]["classification"], "POSSIBLE_GAP")
        plan = fc.build_plan(profile)
        probes = [p for p in plan["probes"] if p["domain"] == "probability_statistics"]
        self.assertTrue(any(p["kind"] == "discriminator" for p in probes))

    def test_assisted_or_unverified_pass_does_not_create_strength(self) -> None:
        profile = fp.load()
        fc.record(
            profile,
            probe_id="cross_domain:formalization:1",
            domain="cross_domain",
            facet="formalization_precision",
            kind="formalization",
            outcome="pass",
            assistance="full",
            verified=True,
        )
        fc.record(
            profile,
            probe_id="cross_domain:formalization:2",
            domain="cross_domain",
            facet="formalization_precision",
            kind="formalization",
            outcome="pass",
            assistance="none",
            verified=False,
        )
        row = profile["deep_calibration"]["facet_evidence"]["formalization_precision"]
        self.assertEqual(row["classification"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(row["independent_verified_pass"], 0)

    def test_two_verified_independent_changed_representation_passes_are_promising(self) -> None:
        profile = fp.load()
        for index in (1, 2):
            fc.record(
                profile,
                probe_id=f"formal_reasoning:harder_transfer:{index}",
                domain="formal_reasoning",
                facet="transfer_adaptation",
                kind="harder_transfer",
                outcome="pass",
                assistance="none",
                verified=True,
                confidence=80,
                representation=f"representation-{index}",
            )
        row = profile["deep_calibration"]["facet_evidence"]["transfer_adaptation"]
        self.assertEqual(row["classification"], "PROMISING_STRENGTH")
        self.assertEqual(profile["domains"]["formal_reasoning"]["classification"], "PROMISING_STRENGTH")

    def test_duplicate_probe_id_is_rejected(self) -> None:
        profile = fp.load()
        kwargs = dict(
            probe_id="cross_domain:verifier_selection:1",
            domain="cross_domain",
            facet="tool_selection",
            kind="verifier_selection",
            outcome="pass",
            assistance="none",
            verified=True,
        )
        fc.record(profile, **kwargs)
        with self.assertRaises(ValueError):
            fc.record(profile, **kwargs)

    def test_deep_profile_ready_requires_broad_evidence_not_one_domain(self) -> None:
        profile = fp.load()
        for index in range(20):
            fc.record(
                profile,
                probe_id=f"formal_reasoning:harder_transfer:{index}",
                domain="formal_reasoning",
                facet="transfer_adaptation",
                kind="harder_transfer",
                outcome="pass",
                assistance="none",
                verified=True,
                confidence=90,
                representation=f"r{index}",
            )
        state = fc.maturity(profile)
        self.assertNotEqual(state["status"], "DEEP_PROFILE_READY")
        self.assertIn("distinct_domains", state["missing"])
        self.assertIn("cross_cutting_facets", state["missing"])

    def test_deep_profile_ready_after_all_engineering_coverage_gates(self) -> None:
        profile = fp.load()
        facets = list(fc.FACETS)[:8]
        domains = ["formal_reasoning", "software_engineering", "research_evidence", "design_ux"]
        kinds = [
            "harder_transfer",
            "changed_representation",
            "discriminator",
            "real_work",
            "real_work",
            "domain_error_detection",
            "adversarial_error_detection",
            "design_tradeoff",
            "creative_mechanisms",
            "explain_back",
            "formalization",
            "verifier_selection",
            "systems_decomposition",
            "critical_path",
        ]
        for index, kind in enumerate(kinds):
            fc.record(
                profile,
                probe_id=f"p{index}",
                domain=domains[index % len(domains)],
                facet=facets[index % len(facets)],
                kind=kind,
                outcome="pass",
                assistance="none",
                verified=True,
                confidence=80,
                representation=f"rep-{index}",
            )
        state = fc.maturity(profile)
        self.assertEqual(state["status"], "DEEP_PROFILE_READY")
        self.assertEqual(state["missing"], [])

    def test_context_exposes_only_hypotheses_and_coverage(self) -> None:
        profile = fp.load()
        text = fc.deep_context(profile)
        self.assertIn("FOIL_DEEP_PROFILE", text)
        self.assertIn("coverage gaps", text)
        self.assertIn("Assisted/unverified success does not establish", text)


if __name__ == "__main__":
    unittest.main()
