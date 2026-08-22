"""Claude Code hook adapter for automatic FOIL profile bootstrap/relevance.

The prompt hook stores only inferred domain relevance metadata. It does not
store raw prompt text.
"""
from __future__ import annotations

import json
import sys

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


def session() -> int:
    profile = bootstrap_active()
    print(compact_context(profile))
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
    print(compact_context(profile))
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
