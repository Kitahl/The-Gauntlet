"""Claude Code hook adapter for automatic FOIL profile bootstrap/relevance.

The prompt hook stores only inferred domain relevance metadata. It does not
store raw prompt text. Deep-calibration state is injected as compact routing
context when available.
"""
from __future__ import annotations

import json
import sys

from foil_calibration import deep_context
from foil_profile import (
    bootstrap_active,
    compact_context,
    infer_domains,
    mark_relevance,
    save,
)


def _input() -> dict:
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}


def _print_context(profile: dict) -> None:
    print(compact_context(profile))
    print(deep_context(profile))


def session() -> int:
    profile = bootstrap_active()
    _print_context(profile)
    return 0


def prompt() -> int:
    data = _input()
    text = str(data.get("prompt") or "")
    profile = bootstrap_active()
    domains = infer_domains(text)
    if domains:
        mark_relevance(profile, domains, source="prompt")
        save(profile)
    current = ", ".join(domains) if domains else "unclassified"
    _print_context(profile)
    print(
        f"<FOIL_CURRENT_TASK domains={current!r}>Domain relevance is routing metadata, not competence evidence.</FOIL_CURRENT_TASK>"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    mode = (argv or sys.argv[1:] or ["session"])[0]
    if mode == "prompt":
        return prompt()
    return session()


if __name__ == "__main__":
    raise SystemExit(main())
