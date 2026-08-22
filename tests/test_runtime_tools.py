from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gauntlet_boundary as gb
import gauntlet_monitor as gm
import foil_profile as fp
import foil_assessment as fa


class RuntimeToolTests(unittest.TestCase):
    def test_boundary_stage1_frame_and_costume(self):
        self.assertEqual(gb.stage1("This failed again with the same approach", [], 0.72), "frame")
        self.assertEqual(gb.stage1("This is our novel framework and only remaining option", [], 0.72), "costume")
        self.assertIsNone(gb.stage1("This is similar to an existing known method", [], 0.72))

    def test_monitor_configurable_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".gauntlet.json").write_text(json.dumps({"state_dir": ".state", "governing_files": ["A.md"]}))
            (root / "A.md").write_text("a")
            gm.snapshot(root)
            (root / "A.md").write_text("b")
            code, drift = gm.check(root)
            self.assertEqual(code, 1)
            self.assertTrue(any("A.md" in x for x in drift))

    def test_profile_persistence_is_outside_repo_and_dynamic(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"EGR_FOIL_PROFILE_DIR": td}, clear=False):
                pr = fp.new_profile("Research User")
                fp.save(pr); fp.activate("Research User")
                pr = fp.load()
                fp.observe(pr, "new_domain_name", "incorrect", "none", confidence=90)
                fp.save(pr)
                pr = fp.load("research-user")
                self.assertIn("new_domain_name", pr["domains"])
                self.assertEqual(pr["domains"]["new_domain_name"]["classification"], "INSUFFICIENT_EVIDENCE")
                fp.observe(pr, "new_domain_name", "incorrect", "none")
                self.assertEqual(pr["domains"]["new_domain_name"]["classification"], "POSSIBLE_GAP")

    def test_assessment_blank_and_setup_domain_inference(self):
        session = fa.build(seed=42, setup_text="I work on causal inference and UI design")
        self.assertIn("causal_inference", session["selected_domains"])
        self.assertIn("design_ux", session["selected_domains"])
        blank = session["response_schema"]
        self.assertTrue(all(v["choice"] is None for v in blank["objective"].values()))

    def test_assessment_perfect_is_promising_not_owned(self):
        session = fa.build(seed=5)
        resp = session["response_schema"]
        for item in session["objective_items"]:
            resp["objective"][item["id"]]["choice"] = fa.answer(item)
        report = fa.score(session, resp)
        self.assertTrue(all(x["classification"] == "PROMISING_STRENGTH" for x in report["domain_evidence"].values()))

    def test_settings_use_project_dir_not_private_path(self):
        text = (ROOT / ".claude/settings.json").read_text()
        self.assertIn("${CLAUDE_PROJECT_DIR}", text)
        for forbidden in ["tombl", "novelty-harness", "Tribunal", "C:\\Users"]:
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
