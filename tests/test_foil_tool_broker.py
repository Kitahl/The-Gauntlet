"""D6 - the PreToolUse broker, the point where a frozen-run budget is enforced.

Every case drives the real hook as the host does: a subprocess, hook JSON on
stdin, decision on stdout, exit code 0 either way. Testing the functions in
process would prove nothing about the contract the host actually reads.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_capabilities as caps  # noqa: E402
import foil_task_guard as tg  # noqa: E402
import foil_tool_broker as broker  # noqa: E402

BROKER = ROOT / "tools" / "foil_tool_broker.py"
PROMPT = "the frozen prompt"


def base_env() -> dict[str, str]:
    """A clean environment: no inherited Claude Code session variables.

    The hook must be driven by FOIL_TASK_* alone. Leaking the parent session's
    variables in would make the test agree with whatever the developer's shell
    happened to hold.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("CLAUDE", "FOIL_"))
    }
    env["PYTHONIOENCODING"] = "utf-8"
    return env


class BrokerTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.state = self.dir / "run.json"
        self.write_state(budgets={"search": 1, "followup": 1})

    def write_state(self, *, budgets: dict[str, int]) -> None:
        tg._atomic_save(self.state, tg.start_state(
            task_id="task-1", prompt=PROMPT, condition="COND", budgets=budgets))

    def active_env(self, **overrides: str) -> dict[str, str]:
        env = base_env()
        env.update({
            "FOIL_TASK_RUN": str(self.state),
            "FOIL_TASK_ID": "task-1",
            "FOIL_TASK_CONDITION": "COND",
            "FOIL_TASK_PROMPT_SHA256": tg.prompt_hash(PROMPT),
        })
        env.update(overrides)
        return env

    def run_hook(self, tool_name: str, env: dict[str, str], **tool_input):
        payload = {
            "tool_name": tool_name,
            "tool_input": tool_input or {"query": "x"},
            "session_id": "s-1",
            "cwd": str(self.dir),
        }
        return subprocess.run(
            [sys.executable, str(BROKER)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
            check=False,
        )

    def assertAllowed(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "", "an allow must print nothing")

    def assertDenied(self, result) -> str:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip(), "a deny must print a decision")
        payload = json.loads(result.stdout)
        block = payload["hookSpecificOutput"]
        self.assertEqual(block["hookEventName"], "PreToolUse")
        self.assertEqual(block["permissionDecision"], "deny")
        self.assertTrue(block["permissionDecisionReason"].strip())
        return block["permissionDecisionReason"]

    def used(self) -> dict:
        return json.loads(self.state.read_text(encoding="utf-8"))["used"]


class InactiveBrokerTests(BrokerTestCase):
    """FOIL_TASK_RUN is the single switch: unset means no run was intended."""

    def test_no_env_at_all_allows_silently(self):
        self.assertAllowed(self.run_hook("WebSearch", base_env()))

    def test_unset_or_empty_run_variable_deactivates_the_hook(self):
        for value in (None, "", "   "):
            env = self.active_env()
            if value is None:
                env.pop("FOIL_TASK_RUN")
            else:
                env["FOIL_TASK_RUN"] = value
            self.assertAllowed(self.run_hook("WebSearch", env))
        self.assertEqual(self.used()["search"], 0, "an inactive hook must not charge")

    def test_a_healthy_run_is_the_positive_control(self):
        """Without this, 'inert' could just mean 'the hook never works'."""
        self.assertAllowed(self.run_hook("WebSearch", self.active_env()))
        self.assertEqual(self.used()["search"], 1)


class PartialConfigurationTests(BrokerTestCase):
    """A set FOIL_TASK_RUN asserts a run is in progress; a broken one fails closed.

    Allowing here would let a partially configured run proceed completely
    unguarded while being indistinguishable from a healthy one.
    """

    def test_each_missing_variable_denies_rather_than_deactivating(self):
        for missing in ("FOIL_TASK_ID", "FOIL_TASK_CONDITION"):
            env = self.active_env()
            env.pop(missing)
            reason = self.assertDenied(self.run_hook("WebSearch", env))
            self.assertIn("only partially configured", reason)
            self.assertIn(missing, reason)
        env = self.active_env()
        env.pop("FOIL_TASK_PROMPT_SHA256")
        reason = self.assertDenied(self.run_hook("WebSearch", env))
        self.assertIn("FOIL_TASK_PROMPT or FOIL_TASK_PROMPT_SHA256", reason)
        self.assertEqual(self.used()["search"], 0, "a denied call must not charge")

    def test_blank_variables_count_as_missing(self):
        reason = self.assertDenied(self.run_hook("WebSearch", self.active_env(
            FOIL_TASK_ID="   ")))
        self.assertIn("FOIL_TASK_ID", reason)

    def test_state_path_that_does_not_exist_is_denied(self):
        absent = str(self.dir / "absent.json")
        env = self.active_env(FOIL_TASK_RUN=absent)
        reason = self.assertDenied(self.run_hook("WebSearch", env))
        self.assertIn("frozen FOIL run state file missing", reason)
        self.assertIn(absent, reason)
        self.assertIn("failing closed", reason)

    def test_write_tools_are_denied_under_a_broken_configuration_too(self):
        env = self.active_env(FOIL_TASK_RUN=str(self.dir / "absent.json"))
        self.assertDenied(self.run_hook("Bash", env, command="ls"))

    def test_the_refusal_is_scoped_to_brokered_tools(self):
        """An unbudgeted tool is guarded by nothing anyway.

        Refusing `Read` because the run is misconfigured would break unrelated
        work without protecting a single budget unit.
        """
        env = self.active_env(FOIL_TASK_RUN=str(self.dir / "absent.json"))
        for tool in ("Read", "Glob", "Grep"):
            self.assertAllowed(self.run_hook(tool, env))


class BudgetEnforcementTests(BrokerTestCase):
    def test_first_search_is_allowed_and_charged_second_is_denied(self):
        self.assertAllowed(self.run_hook("WebSearch", self.active_env()))
        self.assertEqual(self.used()["search"], 1)
        reason = self.assertDenied(self.run_hook("WebSearch", self.active_env()))
        self.assertIn("budget", reason.lower())
        self.assertEqual(self.used()["search"], 1, "a denied call must not overspend")

    def test_budgets_are_tracked_per_operation(self):
        self.assertAllowed(self.run_hook("WebSearch", self.active_env()))
        self.assertAllowed(self.run_hook("WebFetch", self.active_env(), url="https://e"))
        self.assertEqual(self.used(), {"search": 1, "followup": 1})
        self.assertDenied(self.run_hook("WebFetch", self.active_env(), url="https://e"))

    def test_prompt_text_is_an_equivalent_binding(self):
        env = self.active_env()
        env.pop("FOIL_TASK_PROMPT_SHA256")
        env["FOIL_TASK_PROMPT"] = PROMPT
        self.assertAllowed(self.run_hook("WebSearch", env))
        self.assertEqual(self.used()["search"], 1)

    def test_mcp_tool_names_route_by_pattern(self):
        self.write_state(budgets={"search": 1, "followup": 1})
        self.assertAllowed(self.run_hook("mcp__paper-search__search_arxiv", self.active_env()))
        self.assertEqual(self.used()["search"], 1)
        self.assertAllowed(self.run_hook("mcp__fetcher__read_url", self.active_env()))
        self.assertEqual(self.used()["followup"], 1)

    def test_decisions_are_journalled_and_the_chain_stays_valid(self):
        self.run_hook("WebSearch", self.active_env())
        self.run_hook("WebSearch", self.active_env())
        state = json.loads(self.state.read_text(encoding="utf-8"))
        broker_events = [e for e in state["events"] if e.get("kind") == "BROKER"]
        self.assertEqual([e["decision"] for e in broker_events], ["allow", "deny"])
        self.assertTrue(tg.attest(state)["valid"])


class WriteRefusalTests(BrokerTestCase):
    WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "PowerShell")

    def test_write_tools_are_denied_by_default(self):
        for tool in self.WRITE_TOOLS:
            reason = self.assertDenied(self.run_hook(tool, self.active_env(), command="ls"))
            self.assertIn("capability_writes", reason, tool)

    def test_the_refusal_matches_the_registry_it_cites(self):
        """The reason is only true because no capability declares writes=True."""
        self.assertEqual(
            [name for name in caps.CAPABILITIES if caps.capability_writes(name)], []
        )

    def test_explicit_opt_in_admits_writes(self):
        """Positive control: same input, one env variable different."""
        env = self.active_env(FOIL_TASK_ALLOW_WRITES="1")
        for tool in self.WRITE_TOOLS:
            self.assertAllowed(self.run_hook(tool, env, command="ls"))
        self.assertEqual(self.used(), {"search": 0, "followup": 0},
                         "writes are not a budget line")

    def test_any_other_value_is_not_an_opt_in(self):
        for value in ("0", "true", "yes", ""):
            env = self.active_env(FOIL_TASK_ALLOW_WRITES=value)
            self.assertDenied(self.run_hook("Bash", env, command="ls"))


class FailClosedTests(BrokerTestCase):
    def test_wrong_task_id_is_denied(self):
        reason = self.assertDenied(self.run_hook("WebSearch", self.active_env(
            FOIL_TASK_ID="a-different-task")))
        self.assertIn("task_id mismatch", reason)
        self.assertEqual(self.used()["search"], 0)

    def test_wrong_condition_is_denied(self):
        reason = self.assertDenied(self.run_hook("WebSearch", self.active_env(
            FOIL_TASK_CONDITION="OTHER")))
        self.assertIn("condition mismatch", reason)

    def test_wrong_prompt_digest_is_denied(self):
        reason = self.assertDenied(self.run_hook("WebSearch", self.active_env(
            FOIL_TASK_PROMPT_SHA256="0" * 64)))
        self.assertIn("prompt hash mismatch", reason)

    def test_closed_run_is_denied(self):
        state = json.loads(self.state.read_text(encoding="utf-8"))
        tg.close(state)
        tg._atomic_save(self.state, state)
        reason = self.assertDenied(self.run_hook("WebSearch", self.active_env()))
        self.assertIn("not open", reason)

    def test_corrupt_state_file_is_denied_not_allowed(self):
        self.state.write_text("{not json at all", encoding="utf-8")
        reason = self.assertDenied(self.run_hook("WebSearch", self.active_env()))
        self.assertIn("failing closed", reason)

    def test_state_file_missing_the_budget_is_denied(self):
        self.write_state(budgets={"followup": 1})
        reason = self.assertDenied(self.run_hook("WebSearch", self.active_env()))
        self.assertIn("not budgeted", reason)


class MalformedPayloadTests(BrokerTestCase):
    """B2 - an unreadable payload inside a frozen run fails closed.

    The hook cannot tell which tool an unparseable payload was about, so it
    cannot tell whether the call is budgeted. Treating that as "nothing to
    broker" made corrupting stdin a way to run a budgeted tool for free: the
    call proceeds, no unit is charged, and the receipt reports a spend that
    never happened. Outside a run there is nothing to protect, so the hook
    stays inert - that difference is the whole design.
    """

    MALFORMED = ("{not json", "", "[]", '"str"', "   ", "null", "123")

    def run_raw(self, stdin: str, env: dict[str, str]):
        return subprocess.run(
            [sys.executable, str(BROKER)],
            input=stdin,
            capture_output=True, text=True, env=env, timeout=120, check=False,
        )

    def test_malformed_stdin_denies_while_a_run_is_active(self):
        for stdin in self.MALFORMED:
            reason = self.assertDenied(self.run_raw(stdin, self.active_env()))
            self.assertEqual(reason, "hook payload unreadable; failing closed", repr(stdin))

    def test_malformed_stdin_stays_inert_with_no_run(self):
        """Same inputs, one variable different: FOIL_TASK_RUN is unset."""
        for stdin in self.MALFORMED:
            result = self.run_raw(stdin, base_env())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "", repr(stdin))

    def test_a_blank_run_variable_is_also_inert(self):
        env = self.active_env(FOIL_TASK_RUN="   ")
        self.assertEqual(self.run_raw("{not json", env).stdout.strip(), "")

    def test_a_well_formed_payload_is_the_positive_control(self):
        """Without this, the deny above could just be "the hook always denies"."""
        self.assertAllowed(self.run_hook("Read", self.active_env()))

    def test_a_denial_on_malformed_input_charges_nothing(self):
        self.assertDenied(self.run_raw("{not json", self.active_env()))
        self.assertEqual(self.used(), {"search": 0, "followup": 0})


class ToolNameNormalisationTests(BrokerTestCase):
    """B4 - the exact-name table matched case-sensitively, the patterns did not.

    `mcp__x__SEARCH` was budgeted but `websearch` was not, so a change of case
    on a built-in name walked around the budget entirely.
    """

    def test_case_and_whitespace_variants_classify_as_the_canonical_name(self):
        for variant in ("websearch", "WEBSEARCH", " WebSearch ", "\tWebSearch\n"):
            self.assertEqual(broker.classify_tool(variant), "search", repr(variant))
        for variant in ("bash", "BASH", "Bash "):
            self.assertEqual(broker.classify_tool(variant), "write", repr(variant))
        for variant in ("webfetch", " WEBFETCH"):
            self.assertEqual(broker.classify_tool(variant), "followup", repr(variant))

    def test_every_canonical_name_survives_the_variants(self):
        for name, operation in broker.TOOL_OPERATIONS.items():
            for variant in (name, name.lower(), name.upper(), f"  {name}  "):
                self.assertEqual(broker.classify_tool(variant), operation, variant)

    def test_normalisation_does_not_invent_budgeted_tools(self):
        """Negative control: unrelated names still classify as unbudgeted."""
        for name in ("", "   ", "Read", "read", " Grep ", "WebSearchExtra", "notbash"):
            self.assertIsNone(broker.classify_tool(name), repr(name))

    def test_a_lowercased_search_is_charged_end_to_end(self):
        """The unit test above is in-process; this is the host's contract."""
        self.assertAllowed(self.run_hook("websearch", self.active_env()))
        self.assertEqual(self.used()["search"], 1)
        self.assertDenied(self.run_hook(" WebSearch ", self.active_env()))

    def test_a_lowercased_write_tool_is_still_refused(self):
        reason = self.assertDenied(self.run_hook("bash", self.active_env(), command="ls"))
        self.assertIn("capability_writes", reason)


class UnbudgetedToolTests(BrokerTestCase):
    def test_unknown_tools_pass_through_untouched(self):
        for tool in ("Read", "Glob", "Grep", "TodoWrite", "mcp__memory__list_notes"):
            self.assertAllowed(self.run_hook(tool, self.active_env()))
        self.assertEqual(self.used(), {"search": 0, "followup": 0})

    def test_an_unbudgeted_tool_writes_no_ledger_event(self):
        before = len(json.loads(self.state.read_text(encoding="utf-8"))["events"])
        self.run_hook("Read", self.active_env())
        after = len(json.loads(self.state.read_text(encoding="utf-8"))["events"])
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
