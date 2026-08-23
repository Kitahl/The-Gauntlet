"""Claude Code hook adapter for FOIL profile relevance + typed adaptation events.

The prompt hook stores only inferred domain/facet relevance metadata. It does
not store raw prompt text. Deep-calibration state is injected as compact routing
context when available. The typed bridge records hashed routing metadata and can
clear only explicit ADAPTATION obligations; factual warrant remains outside FOIL.

Two properties this adapter owes the session:

* **A bounded payload.** Everything the hook prints is one budget
  (`foil_profile.PAYLOAD_BUDGET`, 4,000 characters), well under the host's
  10,000-character cap on hook output, so a large or hostile profile can never
  crowd out the user's own prompt. The profile block is sized against what the
  deep block and the task line will occupy, and the whole emission is checked
  once more before it is printed.
* **Fail-soft.** A malformed, unreadable or partially-written profile file makes
  the hook print nothing and exit 0. A hook that raises would take the user's
  prompt down with it, and a profile is never worth that. The typed bridge is
  held to the same rule: an unavailable bridge is reported in the task line, it
  never raises through the hook.
"""
from __future__ import annotations

import json
import sys

from foil_calibration import deep_context
from foil_domains import infer_domains as infer_extended_domains
from foil_layer2 import infer_facets, mark_facet_relevance
from foil_profile import (
    PAYLOAD_BUDGET,
    TRUNCATION_MARK,
    bootstrap_active,
    compact_context,
    infer_domains,
    mark_relevance,
    save,
)
from foil_runtime_bridge import record_prompt_adaptation
from gauntlet_config import project_root

#: The profile block never shrinks below this, however large the other blocks
#: get: a payload with no provenance header is worse than no payload.
MIN_PROFILE_BUDGET = 600


def _input() -> dict:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return {}
    # Valid non-object JSON (list/null/number) must not reach the `.get(...)` calls.
    return data if isinstance(data, dict) else {}


def build_payload(profile: dict, task_line: str = "") -> str:
    """Compose the emission and hold it to one budget."""
    try:
        deep = deep_context(profile)
    except Exception:  # noqa: BLE001 - deep calibration is optional context, never fatal
        deep = ""
    reserved = len(deep) + len(task_line) + 2
    profile_budget = max(MIN_PROFILE_BUDGET, PAYLOAD_BUDGET - reserved)
    parts = [compact_context(profile, budget=profile_budget), deep, task_line]
    payload = "\n".join(part for part in parts if part)
    if len(payload) > PAYLOAD_BUDGET:
        payload = payload[: max(0, PAYLOAD_BUDGET - len(TRUNCATION_MARK))] + TRUNCATION_MARK
    return payload


def _emit(profile: dict, task_line: str = "") -> None:
    payload = build_payload(profile, task_line)
    if payload:
        print(payload)


def session() -> int:
    try:
        profile = bootstrap_active()
    except Exception:  # noqa: BLE001 - see the module docstring: never break the prompt
        return 0
    _emit(profile)
    return 0


def prompt() -> int:
    data = _input()
    text = str(data.get("prompt") or "")
    try:
        profile = bootstrap_active()
    except Exception:  # noqa: BLE001 - see the module docstring: never break the prompt
        return 0
    try:
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
    except Exception:  # noqa: BLE001 - relevance marking is best-effort, never fatal
        domains, facets = [], []
    try:
        try:
            from egrt_hook import _explicit_aliases
            foil_alias = "foil" in _explicit_aliases(text)
        except Exception:  # noqa: BLE001 - alias detection is best-effort, default to non-explicit
            foil_alias = False
        typed_receipts = record_prompt_adaptation(
            project_root(), profile, domains, facets, prompt_text=text, foil_alias=foil_alias,
        )
        typed_status = f"receipts={len(typed_receipts)}"
    except Exception as exc:  # noqa: BLE001 - availability signal, never a factual judgment
        # This is an integration availability signal, never a competence/factual
        # judgment. Preserve ordinary FOIL routing output even if typed logging fails.
        typed_status = f"UNAVAILABLE:{type(exc).__name__}"
    current_domains = ", ".join(domains) if domains else "unclassified"
    current_facets = ", ".join(facets) if facets else "unclassified"
    task_line = (
        f"<FOIL_CURRENT_TASK domains={current_domains!r} facets={current_facets!r} "
        f"typed_runtime={typed_status!r}>"
        "Domain/facet relevance is routing metadata, not competence evidence."
        "</FOIL_CURRENT_TASK>"
    )
    _emit(profile, task_line)
    return 0


def main(argv: list[str] | None = None) -> int:
    mode = (argv or sys.argv[1:] or ["session"])[0]
    if mode == "prompt":
        return prompt()
    return session()


if __name__ == "__main__":
    raise SystemExit(main())
