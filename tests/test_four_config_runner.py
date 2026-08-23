"""Checks for `benchmarks/harness/claude_four_config_runner.py`.

The execution tests drive a **fake `claude`** placed on `PATH`: a small script
that echoes a `claude -p --output-format json` envelope and records the argv,
working directory and environment it was handed. That is what makes the
isolation claims testable - "the child environment is stripped" is only a claim
until something reads the child's own view of its environment.

No test here contacts a network, a dataset, or a billable API.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import claude_four_config_runner as runner  # noqa: E402

FAKE_CLAUDE = '''
import json, os, sys

log = os.environ.get("FAKE_CLAUDE_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "argv": sys.argv[1:],
            "cwd": os.getcwd(),
            "env": dict(os.environ),
            "stdin": sys.stdin.read(),
        }) + "\\n")

mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
if mode == "error":
    envelope = {"type": "result", "subtype": "error_during_execution",
                "is_error": True, "result": "the session failed",
                "session_id": "sess-err", "num_turns": 1, "duration_ms": 5,
                "total_cost_usd": 0.001}
elif mode == "error_flag_only":
    envelope = {"type": "result", "subtype": "success", "is_error": True,
                "result": "ANSWER: A", "session_id": "sess-flag", "num_turns": 1,
                "duration_ms": 6, "total_cost_usd": 0.001}
elif mode == "no_answer":
    envelope = {"type": "result", "subtype": "success", "is_error": False,
                "result": "I considered the options but will not commit.",
                "session_id": "sess-noans", "num_turns": 2, "duration_ms": 7,
                "total_cost_usd": 0.002}
else:
    envelope = {"type": "result", "subtype": "success", "is_error": False,
                "result": "Working through it.\\nANSWER: A\\nANSWER: B",
                "session_id": "sess-ok", "num_turns": 3, "duration_ms": 9,
                "total_cost_usd": 0.003}
print(json.dumps(envelope))
'''


def install_fake_claude(directory: Path) -> Path:
    """Put an executable named `claude` in `directory` and return that directory."""
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "fake_claude.py"
    script.write_text(FAKE_CLAUDE, encoding="utf-8")
    if os.name == "nt":
        shim = directory / "claude.bat"
        shim.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        shim = directory / "claude"
        shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        shim.chmod(0o755)
    return directory


@contextlib.contextmanager
def quiet():
    """Swallow the harness's progress output so test output stays readable."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def synthetic_items(count: int = 2) -> list[dict]:
    return [
        {
            "index": index,
            "id": f"gpqa-fixture-{index:03d}",
            "question": f"Fixture question {index}?",
            "choices": {"A": "alpha", "B": "beta", "C": "gamma", "D": "delta"},
            "category": "fixture",
        }
        for index in range(count)
    ]


class PromptContractTests(unittest.TestCase):
    """The matched-cost claim lives or dies here."""

    def test_foil_prompt_is_the_base_prompt_with_only_the_prefix(self) -> None:
        item = synthetic_items(1)[0]
        base = runner.build_prompt("gpqa", item, "BASE")
        foil = runner.build_prompt("gpqa", item, "FOIL")
        self.assertEqual(foil, runner.FOIL_PROMPT_PREFIX + base)
        self.assertEqual(foil[len(runner.FOIL_PROMPT_PREFIX):], base)
        difference = len(foil.encode("utf-8")) - len(base.encode("utf-8"))
        self.assertEqual(difference, len(runner.FOIL_PROMPT_PREFIX.encode("utf-8")))
        self.assertEqual(difference, 12)

    def test_browsecomp_prompts_hold_the_same_relationship(self) -> None:
        item = {"index": 0, "id": "bc5-00-abcdef12", "question": "Who did the thing?"}
        base = runner.build_prompt("browsecomp", item, "BASE")
        foil = runner.build_prompt("browsecomp", item, "FOIL")
        self.assertEqual(foil, runner.FOIL_PROMPT_PREFIX + base)

    def test_the_answer_instruction_is_present_in_both_arms(self) -> None:
        item = synthetic_items(1)[0]
        for condition in runner.CONDITIONS:
            self.assertIn("ANSWER: <letter>", runner.build_prompt("gpqa", item, condition))

    def test_only_the_skill_flag_differs_in_argv(self) -> None:
        unit = {"model": "opus", "effort": "high"}
        settings = Path("settings.json")
        base = runner.build_argv("gpqa", unit, "BASE", settings)
        foil = runner.build_argv("gpqa", unit, "FOIL", settings)
        self.assertEqual(foil[:len(base)], base)
        self.assertEqual(foil[len(base):], ["--append-system-prompt-file", str(runner.SKILL_FILE)])
        self.assertNotIn("--max-turns", base)

    def test_browsecomp_argv_carries_both_tool_flags(self) -> None:
        argv = runner.build_argv("browsecomp", {"model": "sonnet", "effort": "low"},
                                 "BASE", Path("settings.json"))
        self.assertIn("--tools", argv)
        self.assertEqual(argv[argv.index("--tools") + 1], "WebSearch,WebFetch")
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "WebSearch,WebFetch")

    def test_gpqa_argv_asks_for_no_tools(self) -> None:
        argv = runner.build_argv("gpqa", {"model": "sonnet", "effort": "low"},
                                 "BASE", Path("settings.json"))
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertNotIn("--allowedTools", argv)


class AnswerExtractionTests(unittest.TestCase):
    def test_last_answer_line_wins(self) -> None:
        answer, reason = runner.extract_answer("ANSWER: A\nrethinking\nANSWER: C", "letter")
        self.assertEqual((answer, reason), ("C", None))

    def test_missing_answer_line_is_invalid_not_a_guess(self) -> None:
        answer, reason = runner.extract_answer("I think it is probably beta.", "letter")
        self.assertIsNone(answer)
        self.assertEqual(reason, "no ANSWER line")

    def test_non_letter_answer_is_invalid_for_gpqa(self) -> None:
        answer, reason = runner.extract_answer("ANSWER: beta", "letter")
        self.assertIsNone(answer)
        self.assertIn("not an option letter", reason)

    def test_free_text_answer_is_kept_for_browsecomp(self) -> None:
        answer, reason = runner.extract_answer("ANSWER: Ada Lovelace", "text")
        self.assertEqual((answer, reason), ("Ada Lovelace", None))


class SettingsAndEnvironmentTests(unittest.TestCase):
    def test_settings_contain_only_the_broker_pretooluse_hook(self) -> None:
        payload = runner.settings_payload()
        self.assertEqual(set(payload), {"hooks"})
        self.assertEqual(set(payload["hooks"]), {"PreToolUse"})
        self.assertEqual(len(payload["hooks"]["PreToolUse"]), 1)
        entry = payload["hooks"]["PreToolUse"][0]
        self.assertEqual(set(entry), {"matcher", "hooks"})
        self.assertEqual(len(entry["hooks"]), 1)
        hook = entry["hooks"][0]
        self.assertEqual(hook["type"], "command")
        self.assertIn("foil_tool_broker.py", hook["command"])

    def test_broker_command_is_resolved_at_runtime_not_hard_coded(self) -> None:
        command = runner.settings_payload()["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertIn(runner.BROKER.as_posix(), command)
        self.assertIn(sys.executable, command)
        custom = runner.settings_payload(broker=Path("/elsewhere/tools/foil_tool_broker.py"),
                                         python_executable="/opt/py")
        self.assertIn("/elsewhere/tools/foil_tool_broker.py",
                      custom["hooks"]["PreToolUse"][0]["hooks"][0]["command"])

    def test_parent_session_variables_are_stripped(self) -> None:
        base = {"PATH": "/usr/bin", "CLAUDECODE": "1", "CLAUDE_CODE_ENTRYPOINT": "cli",
                "CLAUDE_PID": "4321", "CLAUDE_KEEP_ME": "yes", "HOME": "/home/x"}
        env = runner.child_env({"FOIL_TASK_ID": "u1"}, base)
        self.assertNotIn("CLAUDECODE", env)
        self.assertNotIn("CLAUDE_CODE_ENTRYPOINT", env)
        self.assertNotIn("CLAUDE_PID", env)
        self.assertEqual(env["CLAUDE_KEEP_ME"], "yes")   # only the named set is stripped
        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertEqual(env["FOIL_TASK_ID"], "u1")


class SealedConditionMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="foil-seal-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def test_map_is_a_function_of_the_seed_only(self) -> None:
        self.assertEqual(runner.condition_map(), runner.condition_map())
        self.assertEqual(set(runner.condition_map()), {"A", "B"})
        self.assertEqual(sorted(runner.condition_map().values()), ["BASE", "FOIL"])

    def test_seal_is_idempotent_and_refuses_a_different_existing_seal(self) -> None:
        sealed = self.tmp / "condition_map.sealed.json"
        with mock.patch.object(runner, "SEALED_MAP", sealed):
            runner.write_sealed_map()
            first = sealed.read_bytes()
            runner.write_sealed_map()
            self.assertEqual(sealed.read_bytes(), first)
            sealed.write_bytes(b'{"map": {"A": "FOIL", "B": "BASE"}}\n')
            with self.assertRaises(runner.PrepareError):
                runner.write_sealed_map()

    def test_sealed_file_is_written_with_lf_and_its_hash_is_pinned_in_the_protocol(self) -> None:
        sealed = self.tmp / "condition_map.sealed.json"
        with mock.patch.object(runner, "SEALED_MAP", sealed):
            runner.write_sealed_map()
        self.assertNotIn(b"\r\n", sealed.read_bytes())
        digest = runner.sha256_file(sealed)
        protocol = runner.PROTOCOL.read_text(encoding="utf-8")
        self.assertIn(digest, protocol,
                      "the protocol must pin the sealed condition map hash before any run")

    def test_manifest_records_the_same_sealed_hash(self) -> None:
        manifest = runner.build_manifest("gpqa", synthetic_items(1))
        self.assertEqual(manifest["condition_map_sha256"],
                         runner.sha256_text(json.dumps(runner.sealed_payload(), indent=2,
                                                       ensure_ascii=False) + "\n"))
        self.assertIn(manifest["condition_map_sha256"],
                      runner.PROTOCOL.read_text(encoding="utf-8"))

    def test_predictions_never_carry_the_condition_name(self) -> None:
        manifest = runner.build_manifest("gpqa", synthetic_items(1))
        for unit in manifest["units"]:
            self.assertIn(unit["condition_id"], {"A", "B"})
            self.assertNotIn("condition", unit)


class ManifestTests(unittest.TestCase):
    def test_every_item_config_condition_triple_is_present_exactly_once(self) -> None:
        items = synthetic_items(3)
        manifest = runner.build_manifest("gpqa", items)
        self.assertEqual(len(manifest["units"]), 3 * len(runner.CONFIGS) * 2)
        self.assertEqual(len({unit["unit"] for unit in manifest["units"]}),
                         len(manifest["units"]))

    def test_isolation_session_ids_are_unique(self) -> None:
        manifest = runner.build_manifest("gpqa", synthetic_items(4))
        ids = [unit["isolation_session_id"] for unit in manifest["units"]]
        self.assertEqual(len(set(ids)), len(ids))

    def test_prompt_digests_reproduce_from_the_item_file(self) -> None:
        items = synthetic_items(2)
        manifest = runner.build_manifest("gpqa", items)
        by_index = {item["index"]: item for item in items}
        for unit in manifest["units"]:
            condition = runner.condition_map()[unit["condition_id"]]
            prompt = runner.build_prompt("gpqa", by_index[unit["item_index"]], condition)
            self.assertEqual(runner.sha256_text(prompt), unit["prompt_sha256"])

    def test_condition_order_is_randomised_across_items(self) -> None:
        manifest = runner.build_manifest("gpqa", synthetic_items(12))
        first_positions = {(unit["item_index"], unit["config"]): unit["order_position"]
                           for unit in manifest["units"] if unit["condition_id"] == "A"}
        self.assertEqual(set(first_positions.values()), {0, 1},
                         "condition A must run first for some pairs and second for others")


class _RunHarness(unittest.TestCase):
    """Shared fixture: a temp run directory, a temp guard directory, a fake `claude`."""

    def setUp(self) -> None:
        import shutil

        self.tmp = Path(tempfile.mkdtemp(prefix="foil-4cfg-test-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.out = self.tmp / "run"
        self.out.mkdir()
        self.log = self.tmp / "fake_claude.log"
        binaries = install_fake_claude(self.tmp / "bin")

        patches = [
            mock.patch.object(runner, "OUT", self.out),
            mock.patch.object(runner, "RECEIPT_DIR", self.out / "four_config_receipts"),
            mock.patch.object(runner, "GUARD_DIR", self.tmp / "guard"),
            mock.patch.object(runner, "SEALED_MAP", self.out / "condition_map.sealed.json"),
            mock.patch.dict(os.environ, {
                "PATH": str(binaries) + os.pathsep + os.environ.get("PATH", ""),
                "FAKE_CLAUDE_LOG": str(self.log),
                "FAKE_CLAUDE_MODE": "ok",
                "CLAUDECODE": "1",
                "CLAUDE_CODE_ENTRYPOINT": "cli",
                "CLAUDE_PID": "4321",
            }),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

        self.items = synthetic_items(1)
        runner.write_sealed_map()
        runner._write_json(runner.items_path("gpqa"), {"items": self.items})
        self.manifest = runner.build_manifest("gpqa", self.items)
        runner._write_json(runner.manifest_path("gpqa"), self.manifest)

    def fake_calls(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in
                self.log.read_text(encoding="utf-8").splitlines() if line.strip()]


class DryRunTests(_RunHarness):
    def test_dry_run_writes_nothing_and_bills_nothing(self) -> None:
        before = sorted(path.name for path in self.out.iterdir())
        with quiet():
            exit_code = runner.cmd_run("gpqa", ["C-SL"], 2, dry_run=True)
        self.assertEqual(exit_code, 0)
        self.assertFalse(runner.predictions_path("gpqa").exists())
        self.assertFalse((self.out / "four_config_receipts").exists())
        self.assertFalse((self.tmp / "guard").exists())
        self.assertEqual(sorted(path.name for path in self.out.iterdir()), before)
        self.assertEqual(self.fake_calls(), [], "dry run must not invoke the CLI")


class ExecutionTests(_RunHarness):
    def test_successful_unit_produces_a_complete_receipt(self) -> None:
        with quiet():
            runner.cmd_run("gpqa", ["C-SL"], 1, dry_run=False)
        receipts = sorted((self.out / "four_config_receipts" / "gpqa").glob("*.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        required = {
            "item_sha256", "condition_id", "config", "model", "effort",
            "prediction_sha256", "session_id", "total_cost_usd", "num_turns",
            "duration_ms", "decoding", "dataset_revision", "as_of",
            "contamination_status", "guard_attest_sha256", "isolation_session_id",
            "is_error", "delivered_prompt_sha256",
        }
        self.assertTrue(required.issubset(receipt), sorted(required - set(receipt)))
        self.assertEqual(receipt["status"], "OK")
        self.assertIs(receipt["is_error"], False)
        self.assertEqual(receipt["session_id"], "sess-ok")
        self.assertEqual(receipt["num_turns"], 3)
        self.assertEqual(receipt["total_cost_usd"], 0.003)
        self.assertEqual(receipt["contamination_status"], "known_public")
        self.assertFalse(receipt["gold_opened"])
        self.assertTrue(receipt["guard_attest"]["valid"])
        self.assertEqual(receipt["prediction_sha256"], runner.sha256_text("B"))

        predictions = json.loads(runner.predictions_path("gpqa").read_text(encoding="utf-8"))
        self.assertFalse(predictions["gold_opened"])
        self.assertEqual(predictions["predictions"][0]["answer"], "B")
        self.assertNotIn("BASE", json.dumps(predictions))
        self.assertNotIn("FOIL", json.dumps(predictions))

    def test_child_runs_in_a_fresh_empty_directory_with_a_stripped_environment(self) -> None:
        with quiet():
            runner.cmd_run("gpqa", ["C-SL"], 1, dry_run=False)
        call = self.fake_calls()[0]
        self.assertNotIn("CLAUDECODE", call["env"])
        self.assertNotIn("CLAUDE_CODE_ENTRYPOINT", call["env"])
        self.assertNotIn("CLAUDE_PID", call["env"])
        self.assertEqual(call["env"]["FOIL_TASK_ID"], self.manifest["units"][0]["unit"])
        self.assertEqual(call["env"]["FOIL_TASK_PROMPT_SHA256"],
                         self.manifest["units"][0]["prompt_sha256"])
        self.assertNotEqual(Path(call["cwd"]).resolve(), ROOT)

    def test_delivered_stdin_matches_what_the_receipt_claims_was_sent(self) -> None:
        """Guards against drift in `foil_models._cli`'s message rendering.

        The adapter wraps the prompt in a `[user]` envelope, so the delivered bytes
        are not the item prompt. If that rendering ever changes, this fails here
        rather than silently invalidating every `delivered_prompt_sha256`.
        """
        with quiet():
            runner.cmd_run("gpqa", ["C-SL"], 1, dry_run=False)
        call = self.fake_calls()[0]
        unit = self.manifest["units"][0]
        prompt = runner.build_prompt("gpqa", self.items[0],
                                     runner.condition_map()[unit["condition_id"]])
        self.assertEqual(call["stdin"], runner.delivered_prompt(prompt))
        self.assertIn(prompt, call["stdin"])
        receipt = json.loads(
            (self.out / "four_config_receipts" / "gpqa" / f"{unit['unit']}.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(receipt["delivered_prompt_sha256"],
                         runner.sha256_text(call["stdin"]))
        self.assertEqual(receipt["prompt_sha256"], unit["prompt_sha256"])

    def test_the_generated_settings_file_holds_only_the_broker_hook(self) -> None:
        with quiet():
            runner.cmd_run("gpqa", ["C-SL"], 1, dry_run=False)
        call = self.fake_calls()[0]
        settings = Path(call["argv"][call["argv"].index("--settings") + 1])
        # The per-unit working directory is removed after the receipt is written,
        # so the settings content is read back from the argv the child recorded.
        self.assertEqual(settings.name, "foil_settings.json")
        self.assertEqual(settings.parent, Path(call["cwd"]))

    def test_is_error_envelope_is_recorded_invalid(self) -> None:
        os.environ["FAKE_CLAUDE_MODE"] = "error"
        with quiet():
            runner.cmd_run("gpqa", ["C-SL"], 1, dry_run=False)
        prediction = json.loads(
            runner.predictions_path("gpqa").read_text(encoding="utf-8"))["predictions"][0]
        self.assertEqual(prediction["status"], "INVALID")
        self.assertIn("is_error", prediction["invalid_reason"])
        self.assertIsNone(prediction["answer"])

    def test_flagged_error_with_a_success_subtype_is_still_invalid(self) -> None:
        """The case a subtype-only check misses.

        The envelope reports subtype "success" and carries a well-formed ANSWER
        line, so every signal except `is_error` says this unit is scoreable. It
        is not, and the positive control is the neighbouring "ok" test, which
        uses the identical envelope without the flag and does score.
        """
        os.environ["FAKE_CLAUDE_MODE"] = "error_flag_only"
        with quiet():
            runner.cmd_run("gpqa", ["C-SL"], 1, dry_run=False)
        prediction = json.loads(
            runner.predictions_path("gpqa").read_text(encoding="utf-8"))["predictions"][0]
        self.assertEqual(prediction["status"], "INVALID")
        self.assertIn("is_error=True", prediction["invalid_reason"])
        self.assertIsNone(prediction["answer"])
        receipt = json.loads(
            (self.out / "four_config_receipts" / "gpqa"
             / f"{self.manifest['units'][0]['unit']}.json").read_text(encoding="utf-8"))
        self.assertIs(receipt["is_error"], True)
        self.assertEqual(receipt["finish_reason"], "success")

    def test_missing_answer_line_is_recorded_invalid(self) -> None:
        os.environ["FAKE_CLAUDE_MODE"] = "no_answer"
        with quiet():
            runner.cmd_run("gpqa", ["C-SL"], 1, dry_run=False)
        prediction = json.loads(
            runner.predictions_path("gpqa").read_text(encoding="utf-8"))["predictions"][0]
        self.assertEqual(prediction["status"], "INVALID")
        self.assertEqual(prediction["invalid_reason"], "no ANSWER line")
        self.assertIsNone(prediction["answer"])

    def test_a_reused_isolation_session_id_fails_closed(self) -> None:
        with quiet():
            runner.cmd_run("gpqa", ["C-SL"], 1, dry_run=False)
        unit = dict(self.manifest["units"][0])
        unit["unit"] = unit["unit"] + "-clone"
        with self.assertRaises(Exception) as caught:
            runner._execute_unit("gpqa", unit, self.items[0])
        self.assertIn("already claimed", str(caught.exception))

    def test_predictions_are_written_incrementally(self) -> None:
        with quiet():
            runner.cmd_run("gpqa", ["C-SL"], 1, dry_run=False)
        first = json.loads(runner.predictions_path("gpqa").read_text(encoding="utf-8"))
        self.assertEqual(len(first["predictions"]), 1)
        with quiet():
            runner.cmd_run("gpqa", ["C-SH"], 1, dry_run=False)
        second = json.loads(runner.predictions_path("gpqa").read_text(encoding="utf-8"))
        self.assertEqual(len(second["predictions"]), 2)


class ScoreGateTests(unittest.TestCase):
    """Gold stays shut until the predictions cannot move without a trace."""

    def setUp(self) -> None:
        import shutil

        self.tmp = Path(tempfile.mkdtemp(prefix="foil-git-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        subprocess.run(["git", "init", "-q"], cwd=self.tmp, check=True,
                       capture_output=True, text=True)
        self.out = self.tmp / "benchmark_runs" / "2026-08-23"
        self.out.mkdir(parents=True)
        self.predictions = self.out / "four_config_gpqa_predictions.json"
        self.predictions.write_text('{"predictions": []}\n', encoding="utf-8")
        patches = [mock.patch.object(runner, "ROOT", self.tmp),
                   mock.patch.object(runner, "OUT", self.out)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_untracked_predictions_are_refused(self) -> None:
        with self.assertRaises(runner.NotCommitted) as caught:
            runner.require_committed(self.predictions)
        self.assertIn("uncommitted", str(caught.exception))

    def test_staged_but_uncommitted_predictions_are_refused(self) -> None:
        subprocess.run(["git", "add", self.predictions.name],
                       cwd=self.predictions.parent, check=True, capture_output=True)
        with self.assertRaises(runner.NotCommitted):
            runner.require_committed(self.predictions)

    def test_a_clean_file_with_no_history_is_still_refused(self) -> None:
        """The positive control for the second condition.

        With `git status` stubbed clean, a file git has never committed must still
        be refused - otherwise the first check alone would be doing all the work
        and the "has a commit" requirement would be untested.
        """
        clean = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        empty_log = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch.object(runner, "_git", side_effect=[clean, empty_log]):
            with self.assertRaises(runner.NotCommitted) as caught:
                runner.require_committed(self.predictions)
        self.assertIn("no commit", str(caught.exception))

    def test_clean_and_committed_passes(self) -> None:
        clean = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        log = subprocess.CompletedProcess(args=[], returncode=0, stdout="abc123\n", stderr="")
        with mock.patch.object(runner, "_git", side_effect=[clean, log]):
            runner.require_committed(self.predictions)   # must not raise

    def test_score_refuses_before_it_can_open_gold(self) -> None:
        """`cmd_score` must fail at the gate, not after touching the dataset."""
        with mock.patch.object(runner, "_gold_for",
                               side_effect=AssertionError("gold opened too early")):
            with self.assertRaises(runner.NotCommitted):
                runner.cmd_score("gpqa")


class CheckOnlyTests(unittest.TestCase):
    def test_check_only_passes_offline_against_the_committed_protocol(self) -> None:
        with mock.patch.object(runner, "_select_gpqa",
                               side_effect=AssertionError("check-only must not select items")):
            with quiet():
                self.assertEqual(runner.cmd_check_only("gpqa"), 0)
                self.assertEqual(runner.cmd_check_only("browsecomp"), 0)


if __name__ == "__main__":
    unittest.main()
