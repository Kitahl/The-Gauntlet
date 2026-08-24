"""Model layer — any LLM through configuration rather than code.

The `ModelLayerTests` / `SetupTests` cases are ported from the update package's
`tests/test_foil_update.py`; `ClaudeJsonParserTests` and `CliDeliveryTests` are
new coverage for the `cli` additions (stdin delivery, `claude_json` parsing,
argv-token effort flags).
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_capabilities as caps  # noqa: E402
import foil_models as fm  # noqa: E402
import foil_setup as fs  # noqa: E402
import foil_tool_policy as tp  # noqa: E402


class ModelLayerTests(unittest.TestCase):
    """Any LLM, through configuration rather than code."""

    def test_every_preset_expands_to_a_valid_spec(self):
        for name in fm.PRESETS:
            spec = fm.spec_from_row({"preset": name, "model": "example"})
            self.assertIn(spec.family, fm.ADAPTER_FAMILIES, name)
            self.assertIsInstance(spec.determinism_class, fm.Determinism, name)

    def test_unknown_family_and_preset_fail_closed(self):
        with self.assertRaises(ValueError):
            fm.spec_from_row({"id": "x", "family": "not_a_family"})
        with self.assertRaises(ValueError):
            fm.spec_from_row({"preset": "not_a_preset"})
        with self.assertRaises(ValueError):
            fm.spec_from_row({"id": "x", "family": "mock", "nonsense_key": 1})

    def test_missing_credential_reports_unavailable_not_ready(self):
        spec = fm.spec_from_row({"id": "k", "preset": "openai", "model": "m",
                                 "api_key_env": "FOIL_TEST_DEFINITELY_UNSET"})
        self.assertEqual(fm.probe(spec)["status"], fm.ProviderStatus.UNAVAILABLE.value)

    def test_configured_is_never_reported_as_ready(self):
        """Only a live probe may return READY."""
        spec = fm.spec_from_row({"id": "m", "preset": "mock"})
        self.assertEqual(fm.probe(spec, live=False)["status"],
                         fm.ProviderStatus.CONFIGURED.value)
        self.assertEqual(fm.probe(spec, live=True)["status"], fm.ProviderStatus.READY.value)

    def test_missing_command_is_unavailable(self):
        spec = fm.spec_from_row({"id": "c", "family": "cli",
                                 "command": ["foil-no-such-binary-xyz"]})
        self.assertEqual(fm.probe(spec)["status"], fm.ProviderStatus.UNAVAILABLE.value)

    def test_unreachable_endpoint_raises_rather_than_returning_empty_text(self):
        spec = fm.spec_from_row({"id": "d", "family": "openai_chat", "model": "m",
                                 "base_url": "http://127.0.0.1:9/v1", "timeout_seconds": 2})
        with self.assertRaises(fm.ModelError):
            fm.complete(spec, "hello")

    def test_secrets_are_never_written_to_a_receipt(self):
        os.environ["FOIL_TEST_SECRET"] = "sk-super-secret-value"
        try:
            spec = fm.spec_from_row({"id": "s", "preset": "openai", "model": "m",
                                     "api_key_env": "FOIL_TEST_SECRET",
                                     "headers": {"X-Org": "secret-org"}})
            blob = json.dumps(fm.redacted(spec))
            self.assertNotIn("sk-super-secret-value", blob)
            self.assertNotIn("secret-org", blob)
            self.assertIn("FOIL_TEST_SECRET", blob)
            self.assertTrue(json.loads(blob)["api_key_present"])
            response = fm.complete(fm.spec_from_row({"id": "m", "preset": "mock"}), "hi")
            self.assertNotIn("text", response.to_receipt())
        finally:
            os.environ.pop("FOIL_TEST_SECRET", None)

    def test_determinism_class_drives_replicate_requirement(self):
        self.assertFalse(fm.Determinism.SEEDED.requires_replicates)
        self.assertTrue(fm.Determinism.TEMPERATURE_ONLY.requires_replicates)
        self.assertTrue(fm.Determinism.NONDETERMINISTIC.requires_replicates)

    def test_mock_adapter_is_deterministic_and_offline(self):
        spec = fm.spec_from_row({"id": "m", "preset": "mock"})
        first = fm.complete(spec, "same prompt")
        second = fm.complete(spec, "same prompt")
        self.assertEqual(first.text, second.text)
        self.assertNotEqual(first.text, fm.complete(spec, "other prompt").text)

    def test_model_capabilities_are_routable(self):
        caps.validate_registry()
        for capability in ("TEXT_GENERATION", "REASONING"):
            self.assertIn(capability, caps.CAPABILITIES)
        manifest = {"providers": [{"name": "any", "capability": "REASONING",
                                   "status": "READY"}]}
        self.assertEqual(tp.route_claim(manifest, "model_reasoning")["status"], "READY")


def _script_spec(body: str, **overrides) -> fm.ModelSpec:
    """A `cli` model whose command is a throwaway Python script."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
    handle.write(body)
    handle.close()
    row = {"id": "script", "family": "cli", "command": [sys.executable, handle.name]}
    row.update(overrides)
    return fm.spec_from_row(row)


class ClaudeJsonParserTests(unittest.TestCase):
    """`output_parser: claude_json` — read the envelope, or fail loudly."""

    def test_valid_envelope_yields_result_and_records_session_metadata(self):
        spec = _script_spec(
            "import json,sys\n"
            "sys.stdin.read()\n"
            "print(json.dumps({'type':'result','subtype':'success','result':'forty-two',\n"
            "  'session_id':'sess-1','total_cost_usd':0.0123,'num_turns':3,'duration_ms':987}))\n",
            output_parser="claude_json",
        )
        response = fm.complete(spec, "what is the answer")
        self.assertEqual(response.text, "forty-two")
        self.assertEqual(response.usage["session_id"], "sess-1")
        self.assertEqual(response.usage["total_cost_usd"], 0.0123)
        self.assertEqual(response.usage["num_turns"], 3)
        self.assertEqual(response.usage["duration_ms"], 987)
        self.assertEqual(response.finish_reason, "success")

    def test_absent_optional_metadata_is_simply_absent(self):
        spec = _script_spec(
            "import json,sys\nsys.stdin.read()\nprint(json.dumps({'result':'ok'}))\n",
            output_parser="claude_json",
        )
        response = fm.complete(spec, "hi")
        self.assertEqual(response.text, "ok")
        for key in fm.CLAUDE_JSON_USAGE_FIELDS:
            if key != "session_id":
                self.assertNotIn(key, response.usage)

    def test_is_error_and_subtype_are_surfaced_without_raising(self):
        """The parser reports the failure; it does not decide what to do about it.

        Whether a failed run is scoreable is the caller's policy. Raising here
        would force every caller into one answer, and inferring the failure from
        `subtype` alone would miss an envelope that sets the flag without
        changing the subtype.
        """
        spec = _script_spec(
            "import json,sys\n"
            "sys.stdin.read()\n"
            "print(json.dumps({'type':'result','subtype':'error_during_execution',\n"
            "  'is_error':True,'result':'the session failed','session_id':'sess-e'}))\n",
            output_parser="claude_json",
        )
        response = fm.complete(spec, "hi")
        self.assertEqual(response.text, "the session failed")
        self.assertIs(response.usage["is_error"], True)
        self.assertEqual(response.usage["subtype"], "error_during_execution")
        self.assertEqual(response.finish_reason, "error_during_execution")

    def test_is_error_defaults_to_false_and_is_always_present(self):
        spec = _script_spec(
            "import json,sys\n"
            "sys.stdin.read()\n"
            "print(json.dumps({'type':'result','subtype':'success','result':'ok'}))\n",
            output_parser="claude_json",
        )
        response = fm.complete(spec, "hi")
        self.assertIn("is_error", response.usage)
        self.assertIs(response.usage["is_error"], False)
        self.assertEqual(response.usage["subtype"], "success")

    def test_absent_subtype_is_an_empty_string_not_a_missing_key(self):
        spec = _script_spec(
            "import json,sys\n"
            "sys.stdin.read()\n"
            "print(json.dumps({'result':'ok'}))\n",
            output_parser="claude_json",
        )
        response = fm.complete(spec, "hi")
        self.assertEqual(response.usage["subtype"], "")
        self.assertIs(response.usage["is_error"], False)
        # `finish_reason` still falls back through `type` to "cli". The error
        # state and the finish label are different questions and are not conflated.
        self.assertEqual(response.finish_reason, "cli")

    def test_the_flag_and_the_subtype_are_not_derived_from_each_other(self):
        """An envelope may flag an error while still reporting subtype "success".

        This is the case a subtype-only check misses, and the reason the runner
        consults both signals.
        """
        spec = _script_spec(
            "import json,sys\n"
            "sys.stdin.read()\n"
            "print(json.dumps({'type':'result','subtype':'success','is_error':True,\n"
            "  'result':'partial'}))\n",
            output_parser="claude_json",
        )
        response = fm.complete(spec, "hi")
        self.assertIs(response.usage["is_error"], True)
        self.assertEqual(response.usage["subtype"], "success")
        self.assertEqual(response.finish_reason, "success")

    def test_missing_result_field_raises_rather_than_returning_the_envelope(self):
        spec = _script_spec(
            "import json,sys\nsys.stdin.read()\n"
            "print(json.dumps({'type':'result','is_error':True,'session_id':'s'}))\n",
            output_parser="claude_json",
        )
        with self.assertRaises(fm.ModelError) as ctx:
            fm.complete(spec, "hi")
        self.assertIn("no 'result' field", str(ctx.exception))

    def test_non_json_stdout_raises_rather_than_being_scored_as_an_answer(self):
        spec = _script_spec(
            "import sys\nsys.stdin.read()\nprint('Usage: claude [options]')\n",
            output_parser="claude_json",
        )
        with self.assertRaises(fm.ModelError) as ctx:
            fm.complete(spec, "hi")
        self.assertIn("not JSON", str(ctx.exception))

    def test_non_string_result_raises(self):
        spec = _script_spec(
            "import json,sys\nsys.stdin.read()\nprint(json.dumps({'result':{'a':1}}))\n",
            output_parser="claude_json",
        )
        with self.assertRaises(fm.ModelError):
            fm.complete(spec, "hi")

    def test_unknown_parser_and_wrong_family_fail_closed(self):
        with self.assertRaises(ValueError):
            fm.spec_from_row({"id": "x", "family": "cli", "command": ["true"],
                              "output_parser": "yaml"})
        with self.assertRaises(ValueError):
            fm.spec_from_row({"id": "x", "preset": "openai", "model": "m",
                              "output_parser": "claude_json"})


class CliDeliveryTests(unittest.TestCase):
    def test_prompt_is_delivered_on_stdin_when_argv_has_no_placeholder(self):
        spec = _script_spec("import sys\nsys.stdout.write(sys.stdin.read())\n")
        response = fm.complete(spec, "needle-on-stdin")
        self.assertIn("needle-on-stdin", response.text)

    def test_prompt_is_delivered_in_argv_when_the_placeholder_is_present(self):
        spec = _script_spec("import sys\nprint(sys.argv[1])\n")
        spec = fm.spec_from_row({"id": "script", "family": "cli",
                                 "command": [*spec.command, "{prompt}"]})
        response = fm.complete(spec, "needle-in-argv")
        self.assertIn("needle-in-argv", response.text)

    def test_effort_and_model_are_plain_argv_tokens(self):
        """No vendor flag logic in the adapter: knobs are argv, `{model}` substitutes."""
        spec = _script_spec("import json,sys\nsys.stdin.read()\nprint(json.dumps(sys.argv[1:]))\n")
        spec = fm.spec_from_row({
            "id": "script", "family": "cli", "model": "some-model",
            "command": [*spec.command, "--model", "{model}", "--effort", "low",
                        "--output-format", "json"],
        })
        response = fm.complete(spec, "hi")
        self.assertEqual(json.loads(response.text)[-6:],
                         ["--model", "some-model", "--effort", "low", "--output-format", "json"])

    def test_claude_cli_preset_uses_stdin_json_and_stays_nondeterministic(self):
        spec = fm.spec_from_row({"preset": "claude_cli", "model": "some-model"})
        self.assertNotIn("{prompt}", " ".join(spec.command))
        self.assertEqual(spec.output_parser, "claude_json")
        self.assertEqual(spec.determinism, fm.Determinism.NONDETERMINISTIC.value)
        self.assertTrue(spec.determinism_class.requires_replicates)

    def test_none_stdout_becomes_model_error_not_attribute_error(self):
        spec = fm.spec_from_row({
            "id": "none-stdout",
            "family": "cli",
            "command": ["fake-cli"],
            "output_parser": "claude_json",
        })
        completed = mock.Mock(returncode=0, stdout=None, stderr=None)
        with (
            mock.patch.object(fm.shutil, "which", return_value="fake-cli"),
            mock.patch.object(fm.subprocess, "run", return_value=completed),
            self.assertRaises(fm.ModelError),
        ):
            fm.complete(spec, "hi")
    def test_a_failing_command_raises_rather_than_returning_empty_text(self):
        spec = _script_spec("import sys\nsys.stdin.read()\nsys.exit(3)\n")
        with self.assertRaises(fm.ModelError):
            fm.complete(spec, "hi")


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.config = Path(tempfile.mkdtemp()) / "models.json"
        # `foil_setup` is a CLI: it reports on stdout. Swallow that here so a
        # suite run's tail is the test summary and not a wall of config JSON.
        silence = redirect_stdout(io.StringIO())
        silence.__enter__()
        self.addCleanup(silence.__exit__, None, None, None)

    def test_roundtrip_add_role_and_resolve(self):
        fs.main(["--config", str(self.config), "add", "--id", "a", "--preset", "mock"])
        fs.main(["--config", str(self.config), "add", "--id", "b", "--preset", "mock"])
        fs.main(["--config", str(self.config), "roles", "--primary", "a", "--reviewer", "b"])
        config = fs.load_config(self.config)
        self.assertEqual(fs.spec_for_role(config, "primary").id, "a")
        self.assertEqual(fs.spec_for_role(config, "reviewer").id, "b")

    def test_unfilled_role_resolves_to_none_never_a_substitute(self):
        fs.main(["--config", str(self.config), "add", "--id", "a", "--preset", "mock"])
        config = fs.load_config(self.config)
        self.assertIsNone(fs.spec_for_role(config, "verifier"))

    def test_config_never_contains_a_secret(self):
        os.environ["FOIL_TEST_SECRET2"] = "sk-leak-me"
        try:
            fs.main(["--config", str(self.config), "add", "--id", "a", "--preset", "openai",
                     "--model", "m", "--api-key-env", "FOIL_TEST_SECRET2"])
            self.assertNotIn("sk-leak-me", self.config.read_text(encoding="utf-8"))
        finally:
            os.environ.pop("FOIL_TEST_SECRET2", None)

    def test_doctor_flags_a_self_reviewing_pool(self):
        fs.main(["--config", str(self.config), "add", "--id", "a", "--preset", "mock"])
        fs.main(["--config", str(self.config), "roles", "--primary", "a", "--reviewer", "a"])
        self.assertEqual(fs.main(["--config", str(self.config), "doctor"]), 1)

    def _doctor(self) -> dict:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = fs.main(["--config", str(self.config), "doctor"])
        report = json.loads(buffer.getvalue())
        report["exit_code"] = code
        return report

    def test_doctor_names_self_review_as_the_reason_not_just_a_nonzero_exit(self):
        """Positive control: `doctor` exits 1 for several reasons, so check the reason.

        A mock-only pool already exits 1, so a bare exit-code assertion would
        pass even if the independence check were deleted.
        """
        needle = "primary and reviewer are the same model"
        with redirect_stdout(io.StringIO()):
            fs.main(["--config", str(self.config), "add", "--id", "a", "--preset", "mock"])
            fs.main(["--config", str(self.config), "add", "--id", "b", "--preset", "mock"])
            fs.main(["--config", str(self.config), "roles", "--primary", "a", "--reviewer", "a"])
        same = self._doctor()
        self.assertEqual(same["exit_code"], 1)
        self.assertTrue(any(needle in finding for finding in same["findings"]), same["findings"])

        with redirect_stdout(io.StringIO()):
            fs.main(["--config", str(self.config), "roles", "--reviewer", "b"])
        distinct = self._doctor()
        self.assertFalse(any(needle in finding for finding in distinct["findings"]),
                         distinct["findings"])

    def test_add_accepts_an_output_parser(self):
        fs.main(["--config", str(self.config), "add", "--id", "agent", "--family", "cli",
                 "--command", "claude -p --output-format json",
                 "--output-parser", "claude_json"])
        config = fs.load_config(self.config)
        self.assertEqual(fs.specs(config)["agent"].output_parser, "claude_json")


if __name__ == "__main__":
    unittest.main()
