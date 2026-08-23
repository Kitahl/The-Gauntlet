"""D5 - declared capability attributes must actually govern routing."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_capabilities as caps  # noqa: E402
import foil_tool_policy as tp  # noqa: E402


class CapabilityRegistryTests(unittest.TestCase):
    def test_every_declared_attribute_is_required_and_validated(self):
        caps.validate_registry()
        for name, meta in caps.CAPABILITIES.items():
            self.assertTrue(caps.REQUIRED_ATTRIBUTES <= set(meta), name)

    def test_claim_routes_only_reference_known_capabilities(self):
        known = set(caps.CAPABILITIES)
        for claim, route in caps.CLAIM_ROUTES.items():
            self.assertTrue(route, claim)
            for capability in route:
                self.assertIn(capability, known, f"{claim} -> {capability}")

    def test_capability_names_validates_before_returning(self):
        self.assertEqual(set(caps.capability_names()), set(caps.CAPABILITIES))

    def test_unknown_capability_write_query_is_an_error_not_a_false(self):
        with self.assertRaises(ValueError):
            caps.capability_writes("NOT_A_CAPABILITY")

    def test_no_capability_currently_declares_write_authority(self):
        """Recorded as a fact about the registry, not an aspiration.

        `tools/foil_tool_broker.py` refuses write-capable tools on exactly this
        basis, so if a write-capable capability is ever added, this test is the
        place that says the broker's reasoning needs revisiting.
        """
        self.assertEqual(
            [name for name in caps.CAPABILITIES if caps.capability_writes(name)], []
        )


class ToolPolicyTests(unittest.TestCase):
    def test_manifest_cannot_grant_write_to_a_read_only_capability(self):
        """v1 routed WEB_SEARCH (writes=False) as write-capable."""
        manifest = {"providers": [{"name": "X", "capability": "WEB_SEARCH",
                                   "status": "READY", "write_allowed": True}]}
        with self.assertRaises(tp.CapabilityWriteError):
            tp.select_provider(manifest, "WEB_SEARCH", require_write=True)
        route = tp.route_claim(manifest, "current_fact", require_write=True)
        self.assertEqual(route["status"], "REFUSED_WRITE")
        self.assertEqual(tp.route_claim(manifest, "current_fact")["status"], "READY")

    def test_read_routing_is_unchanged(self):
        manifest = {"providers": [
            {"name": "A", "capability": "SCHOLARLY_SEARCH", "status": "READY", "priority": 10},
            {"name": "B", "capability": "SCHOLARLY_SEARCH", "status": "READY", "priority": 5},
        ]}
        self.assertEqual(tp.select_provider(manifest, "SCHOLARLY_SEARCH")["name"], "B")

    def test_only_ready_providers_are_selected(self):
        manifest = {"providers": [
            {"name": "A", "capability": "WEB_SEARCH", "status": "CONFIGURED"},
        ]}
        self.assertIsNone(tp.select_provider(manifest, "WEB_SEARCH"))
        self.assertEqual(tp.route_claim(manifest, "current_fact")["status"], "UNAVAILABLE")

    def test_route_falls_back_along_the_declared_order(self):
        manifest = {"providers": [
            {"name": "web", "capability": "WEB_SEARCH", "status": "READY"},
        ]}
        route = tp.route_claim(manifest, "prior_art")
        self.assertEqual(route["status"], "READY")
        self.assertEqual(route["capability"], "WEB_SEARCH")
        self.assertEqual(route["provider"]["name"], "web")

    def test_unclassified_claim_types_are_reported_not_guessed(self):
        route = tp.route_claim({"providers": []}, "not_a_claim_type")
        self.assertEqual(route["status"], "UNCLASSIFIED")

    def test_unknown_capability_is_rejected(self):
        with self.assertRaises(ValueError):
            tp.select_provider({"providers": []}, "NOT_A_CAPABILITY")

    def test_normalize_drops_incomplete_rows_rather_than_inventing_defaults(self):
        manifest = {"providers": [
            {"name": "", "capability": "WEB_SEARCH", "status": "READY"},
            {"name": "ok", "capability": "", "status": "READY"},
            {"name": "keep", "capability": "web_search", "status": "ready"},
        ]}
        rows = tp.normalize_manifest(manifest)["providers"]
        self.assertEqual([row["name"] for row in rows], ["keep"])
        self.assertEqual(rows[0]["capability"], "WEB_SEARCH")
        self.assertEqual(rows[0]["status"], "READY")
        self.assertFalse(rows[0]["write_allowed"])


if __name__ == "__main__":
    unittest.main()
