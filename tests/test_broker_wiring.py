"""B1 - the broker hook is only a boundary for the tools the host routes to it.

`.claude/settings.json` decides which tool calls ever reach
`tools/foil_tool_broker.py`. The broker classifies MCP retrieval tools by
pattern and charges them budget, but its `TOOL_PATTERNS` are dead code if the
host's `PreToolUse` matcher never selects an `mcp__*` name: the call runs, the
hook is not consulted, and the ledger records a frozen run that quietly spent
unbudgeted searches.

These tests pin the two halves against each other. The matcher must admit every
tool the broker budgets, and the broker must budget what the matcher admits.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_tool_broker as broker  # noqa: E402

SETTINGS = ROOT / ".claude" / "settings.json"
BROKER_SCRIPT = "tools/foil_tool_broker.py"

#: Names the host may present. The MCP spellings are the regression: they are
#: what a retrieval MCP server actually produces, and none of them matched.
MUST_REACH_THE_BROKER = (
    "WebSearch",
    "WebFetch",
    "Edit",
    "Write",
    "MultiEdit",
    "NotebookEdit",
    "Bash",
    "PowerShell",
    "mcp__x__web_search",
    "mcp__paper-search__search_arxiv",
    "mcp__fetcher__read_url",
    "mcp__searxng__searxng_search",
)


def settings() -> dict:
    return json.loads(SETTINGS.read_text(encoding="utf-8"))


def broker_matchers() -> list[str]:
    """Every PreToolUse matcher whose hooks invoke the broker script."""
    found = []
    for entry in settings().get("hooks", {}).get("PreToolUse", []):
        payload = json.dumps(entry.get("hooks", []))
        if BROKER_SCRIPT in payload:
            found.append(entry.get("matcher", ""))
    return found


class BrokerMatcherTests(unittest.TestCase):
    def test_exactly_one_pretooluse_entry_invokes_the_broker(self) -> None:
        self.assertEqual(len(broker_matchers()), 1, broker_matchers())

    def test_the_matcher_selects_mcp_and_builtin_tool_names(self) -> None:
        expression = re.compile(broker_matchers()[0])
        for name in MUST_REACH_THE_BROKER:
            self.assertIsNotNone(
                expression.fullmatch(name),
                f"{name!r} never reaches the broker under matcher "
                f"{broker_matchers()[0]!r}",
            )

    def test_the_matcher_does_not_select_unbudgeted_tools(self) -> None:
        """Negative control: a matcher of `.*` would pass the test above too."""
        expression = re.compile(broker_matchers()[0])
        for name in ("Read", "Glob", "Grep", "TodoWrite", "Task"):
            self.assertIsNone(expression.fullmatch(name), name)

    def test_every_matched_tool_is_one_the_broker_classifies(self) -> None:
        """The two halves agree: nothing is routed that the broker ignores."""
        for name in MUST_REACH_THE_BROKER:
            self.assertIsNotNone(broker.classify_tool(name), name)

    def test_every_exact_tool_the_broker_budgets_is_matched(self) -> None:
        expression = re.compile(broker_matchers()[0])
        for name in broker.TOOL_OPERATIONS:
            self.assertIsNotNone(expression.fullmatch(name), name)


class SettingsHookFormTests(unittest.TestCase):
    """Exec form is used deliberately, and the docs say the placeholder holds.

    https://code.claude.com/docs/en/hooks, "Exec form and shell form":
    "There is no shell, so each `args` element is one argument exactly as
    written, and path placeholders like `${CLAUDE_PLUGIN_ROOT}` are substituted
    into `command` and into each `args` element as plain strings."
    `${CLAUDE_PROJECT_DIR}` is one of those placeholders, so the exec-form
    `args` entry below resolves. This test pins the shape the quote covers: a
    bare interpreter in `command`, and the placeholder inside `args`.
    """

    def test_the_broker_hook_uses_exec_form_with_the_project_dir_placeholder(self) -> None:
        entries = [
            hook
            for entry in settings().get("hooks", {}).get("PreToolUse", [])
            for hook in entry.get("hooks", [])
            if BROKER_SCRIPT in json.dumps(hook)
        ]
        self.assertEqual(len(entries), 1, entries)
        hook = entries[0]
        self.assertEqual(hook["type"], "command")
        self.assertEqual(hook["command"], "python")
        self.assertIn("args", hook, "exec form requires args; shell form omits it")
        self.assertEqual(hook["args"], ["${CLAUDE_PROJECT_DIR}/" + BROKER_SCRIPT])


if __name__ == "__main__":
    unittest.main()
