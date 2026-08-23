from __future__ import annotations

import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_assessment as fa  # noqa: E402
import foil_hook as fh  # noqa: E402
import foil_profile as fp  # noqa: E402
import gauntlet_boundary as gb  # noqa: E402
import gauntlet_monitor as gm  # noqa: E402


class RuntimeToolTests(unittest.TestCase):
    def test_boundary_stage1_frame_and_costume(self) -> None:
        self.assertEqual(
            gb.stage1("This failed again with the same approach", [], 0.72),
            "frame",
        )
        self.assertEqual(
            gb.stage1("This is our novel framework and only remaining option", [], 0.72),
            "costume",
        )
        self.assertIsNone(
            gb.stage1("This is similar to an existing known method", [], 0.72)
        )

    def test_boundary_persists_only_lossy_history_fingerprints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gauntlet.json").write_text(
                json.dumps({"state_dir": ".state"}),
                encoding="utf-8",
            )
            raw = "This failed again with confidential-marker-48219"
            gb.reset(root)
            op, _ = gb.evaluate(raw, "", root=root, judge=lambda *_: True)
            self.assertEqual(op, "frame")
            state_path = root / ".state" / "gauntlet_boundary.json"
            serialized = state_path.read_text(encoding="utf-8")
            self.assertNotIn(raw, serialized)
            state = json.loads(serialized)
            self.assertTrue(state["history"])
            self.assertTrue(all(gb.FINGERPRINT.fullmatch(item) for item in state["history"]))
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(state_path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(state_path.parent.stat().st_mode), 0o700)

    def test_stop_hook_active_short_circuits(self) -> None:
        stream = io.StringIO(json.dumps({"stop_hook_active": True, "last_assistant_message": "failed again"}))
        with patch("sys.stdin", stream):
            self.assertEqual(gb.main([]), 0)

    def test_monitor_configurable_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gauntlet.json").write_text(
                json.dumps({"state_dir": ".state", "governing_files": ["A.md"]}),
                encoding="utf-8",
            )
            (root / "A.md").write_text("a", encoding="utf-8")
            gm.snapshot(root)
            state_path = root / ".state" / "gauntlet_monitor.json"
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(state_path.stat().st_mode), 0o600)
            (root / "A.md").write_text("b", encoding="utf-8")
            code, drift = gm.check(root)
            self.assertEqual(code, 1)
            self.assertTrue(any("A.md" in item for item in drift))

    def test_profile_persistence_is_outside_repo_and_dynamic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {"EGR_FOIL_PROFILE_DIR": directory},
                clear=False,
            ):
                profile = fp.new_profile("Research User")
                profile_path = fp.save(profile)
                fp.activate("Research User")
                active_path = fp.profile_home() / "active_profile"
                if os.name != "nt":
                    self.assertEqual(stat.S_IMODE(fp.profile_home().stat().st_mode), 0o700)
                    self.assertEqual(stat.S_IMODE(profile_path.parent.stat().st_mode), 0o700)
                    self.assertEqual(stat.S_IMODE(profile_path.stat().st_mode), 0o600)
                    self.assertEqual(stat.S_IMODE(active_path.stat().st_mode), 0o600)
                profile = fp.load()
                fp.observe(
                    profile,
                    "new_domain_name",
                    "incorrect",
                    "none",
                    confidence=90,
                )
                fp.save(profile)
                profile = fp.load("research-user")
                self.assertIn("new_domain_name", profile["domains"])
                self.assertEqual(
                    profile["domains"]["new_domain_name"]["classification"],
                    "INSUFFICIENT_EVIDENCE",
                )
                fp.observe(profile, "new_domain_name", "incorrect", "none")
                self.assertEqual(
                    profile["domains"]["new_domain_name"]["classification"],
                    "POSSIBLE_GAP",
                )

    def test_prompt_hook_bootstraps_and_marks_relevance_without_raw_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {"EGR_FOIL_PROFILE_DIR": directory},
                clear=False,
            ):
                raw_prompt = "Help me reason about quantum physics and a causal DAG"
                stdin = io.StringIO(json.dumps({"prompt": raw_prompt}))
                output = io.StringIO()
                with patch("sys.stdin", stdin), redirect_stdout(output):
                    self.assertEqual(fh.prompt(), 0)
                profile = fp.load()
                self.assertIn("physics", profile["domains"])
                self.assertIn("causal_inference", profile["domains"])
                serialized = json.dumps(profile)
                self.assertNotIn(raw_prompt, serialized)
                self.assertIn("FOIL_CURRENT_TASK", output.getvalue())

    def test_assessment_blank_and_setup_domain_inference(self) -> None:
        session = fa.build(
            seed=42,
            setup_text="I work on causal inference, UI design, and materials science",
        )
        self.assertIn("causal_inference", session["selected_domains"])
        self.assertIn("design_ux", session["selected_domains"])
        self.assertIn("chemistry_materials", session["selected_domains"])
        blank = session["response_schema"]
        self.assertTrue(
            all(item["choice"] is None for item in blank["objective"].values())
        )

    def test_assessment_perfect_is_promising_not_owned(self) -> None:
        session = fa.build(seed=5)
        responses = session["response_schema"]
        for item in session["objective_items"]:
            responses["objective"][item["id"]]["choice"] = fa.answer(item)
        report = fa.score(session, responses)
        self.assertTrue(
            all(
                result["classification"] == "PROMISING_STRENGTH"
                for result in report["domain_evidence"].values()
            )
        )
        self.assertIn("cannot certify OWNED", report["ownership_ceiling"])

    def test_settings_use_project_dir_and_current_foil_hook(self) -> None:
        text = (ROOT / ".claude/settings.json").read_text(encoding="utf-8")
        self.assertIn("${CLAUDE_PROJECT_DIR}", text)
        self.assertIn("tools/foil_hook.py", text)
        for forbidden in ["tombl", "novelty-harness", "Tribunal", "C:\\Users"]:
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
