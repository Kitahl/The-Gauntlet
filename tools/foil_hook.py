"""Claude Code hook adapter for automatic FOIL profile bootstrap/relevance.

The prompt hook stores only inferred domain/facet relevance metadata. It does
not store raw prompt text. Deep-calibration and universal-refinement state are
injected as compact routing context when available.
"""
from __future__ import annotations

import json
import sys

from foil_calibration import deep_context
from foil_domains import infer_domains as infer_extended_domains
from foil_equalizer import context as equalizer_context
from foil_layer2 import infer_facets, mark_facet_relevance
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


def _print_context(profile: dict, task: str | None = None) -> None:
    print(compact_context(profile))
    print(deep_context(profile))
    print(equalizer_context(profile, task))


def session() -> int:
    profile = bootstrap_active()
    _print_context(profile)
    return 0


def prompt() -> int:
    data = _input()
    text = str(data.get("prompt") or "")
    profile = bootstrap_active()
    domains = list(dict.fromkeys([*infer_domains(text), *infer_extended_domains(text)]))
    facets = infer_facets(text)
    changed = False
    if domains:
        mark_relevance(profile, domains, source="prompt")
        changed = True
    if facets:
        mark_facet_relevance(profile, facets, source="prompt")
        changed = True
    if changed:
        save(profile)
    current_domains = ", ".join(domains) if domains else "unclassified"
    current_facets = ", ".join(facets) if facets else "unclassified"
    _print_context(profile, text)
    print(
        f"<FOIL_CURRENT_TASK domains={current_domains!r} facets={current_facets!r}>"
        "Domain/facet relevance is routing metadata, not competence evidence."
        "</FOIL_CURRENT_TASK>"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    mode = (argv or sys.argv[1:] or ["session"])[0]
    if mode == "prompt":
        return prompt()
    return session()


if __name__ == "__main__":
    raise SystemExit(main())
