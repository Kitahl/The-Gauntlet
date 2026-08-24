"""Claude Code adapter for Mirror (technical identifier ``foil``).

``FOIL_AUTO_MODE`` controls the event-driven hook:

* ``legacy`` (default) preserves the 0.5.1 profile emission and relevance writes;
* ``off`` performs no profile I/O and emits no context;
* ``observe`` computes a privacy-safe activation receipt but emits and writes nothing;
* ``smart`` loads the profile only after a cheap wake gate and emits at most 1,200 chars.

The smart path does not poll, call a model/tool/network, persist prompts, or import
Gauntlet/Mastermind runtime code.  Deterministic task relevance is accepted only
through FOIL's canonical ``TaskCapabilityRequirement`` and requirement router.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MIN_PROFILE_BUDGET = 600
SMART_CONTEXT_BUDGET = 1200
_AUTO_MODES = frozenset({"legacy", "off", "observe", "smart"})


def _input() -> dict[str, Any]:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _auto_mode() -> str:
    value = str(os.environ.get("FOIL_AUTO_MODE") or "legacy").strip().lower()
    return value if value in _AUTO_MODES else "off"


def _project_root() -> Path:
    """Resolve the host project without importing Gauntlet configuration."""
    configured = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("EGR_PROJECT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def build_payload(profile: dict[str, Any], task_line: str = "") -> str:
    """Compose the legacy emission and hold it to the existing 4,000-char budget."""
    from foil_calibration import deep_context
    from foil_profile import PAYLOAD_BUDGET, TRUNCATION_MARK, compact_context

    try:
        deep = deep_context(profile)
    except Exception:  # noqa: BLE001 - optional context must never break a prompt
        deep = ""
    reserved = len(deep) + len(task_line) + 2
    profile_budget = max(MIN_PROFILE_BUDGET, PAYLOAD_BUDGET - reserved)
    parts = [compact_context(profile, budget=profile_budget), deep, task_line]
    payload = "\n".join(part for part in parts if part)
    if len(payload) > PAYLOAD_BUDGET:
        payload = payload[: max(0, PAYLOAD_BUDGET - len(TRUNCATION_MARK))] + TRUNCATION_MARK
    return payload


def _emit(profile: dict[str, Any], task_line: str = "") -> None:
    payload = build_payload(profile, task_line)
    if payload:
        print(payload)


def _legacy_session() -> int:
    from foil_profile import bootstrap_active

    try:
        profile = bootstrap_active()
    except Exception:  # noqa: BLE001 - profiles are optional, hooks are fail-soft
        return 0
    _emit(profile)
    return 0


def _legacy_prompt(data: Mapping[str, Any]) -> int:
    from foil_domains import infer_domains as infer_extended_domains
    from foil_layer2 import infer_facets, mark_facet_relevance
    from foil_profile import bootstrap_active, infer_domains, mark_relevance, save
    from foil_runtime_bridge import record_prompt_adaptation

    text = str(data.get("prompt") or "")
    try:
        profile = bootstrap_active()
    except Exception:  # noqa: BLE001 - profiles are optional, hooks are fail-soft
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
    except Exception:  # noqa: BLE001 - relevance marking is best-effort
        domains, facets = [], []
    try:
        try:
            from egrt_hook import _explicit_aliases

            foil_alias = "foil" in _explicit_aliases(text)
        except Exception:  # noqa: BLE001 - explicit-alias detection is best-effort
            foil_alias = False
        typed_receipts = record_prompt_adaptation(
            _project_root(),
            profile,
            domains,
            facets,
            prompt_text=text,
            foil_alias=foil_alias,
        )
        typed_status = f"receipts={len(typed_receipts)}"
    except Exception as exc:  # noqa: BLE001 - availability is not factual evidence
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


def _canonical_requirements(data: Mapping[str, Any]) -> tuple[object, ...]:
    rows = data.get("foil_task_requirements")
    if not isinstance(rows, list) or not rows:
        return ()
    from foil_requirements import TaskCapabilityRequirement

    requirements: list[object] = []
    try:
        for row in rows:
            if not isinstance(row, Mapping):
                return ()
            requirements.append(
                TaskCapabilityRequirement(
                    requirement_id=row.get("requirement_id"),
                    capability=row.get("capability"),
                    importance=row.get("importance", "MEDIUM"),
                    required_level=row.get("required_level", "WORKING"),
                    evidence_obligation=row.get("evidence_obligation"),
                    representation=row.get("representation"),
                    context=row.get("context"),
                )
            )
    except (TypeError, ValueError):
        return ()
    return tuple(requirements)


def _continuation_lease(data: Mapping[str, Any]) -> object | None:
    row = data.get("foil_continuation_lease")
    if not isinstance(row, Mapping):
        return None
    from foil_activation_monitor import ContinuationLease

    try:
        return ContinuationLease(
            issued_at_monotonic=float(row["issued_at_monotonic"]),
            expires_at_monotonic=float(row["expires_at_monotonic"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _frozen_binding(data: Mapping[str, Any]) -> str | None:
    value = data.get("foil_frozen_run_binding") or os.environ.get("FOIL_TASK_RUN")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _available_context(data: Mapping[str, Any]) -> int:
    value = data.get("foil_available_context_chars", SMART_CONTEXT_BUDGET)
    if isinstance(value, bool):
        return 0
    try:
        return max(0, min(SMART_CONTEXT_BUDGET, int(value)))
    except (TypeError, ValueError):
        return 0


def _l0_wake_candidate(data: Mapping[str, Any]) -> bool:
    """Cheap conservative prefilter before importing the monitor or profile stack."""
    text = str(data.get("prompt") or "").casefold()
    requirements = data.get("foil_task_requirements")
    continuation = data.get("foil_continuation_lease")
    return bool(
        "foil" in text
        or _frozen_binding(data)
        or (isinstance(requirements, list) and requirements)
        or isinstance(continuation, Mapping)
    )


def _monitored(data: Mapping[str, Any], selected_mode: str) -> int:
    from foil_activation_monitor import (
        ActivationEvent,
        FeatureMode,
        FoilActivationMonitor,
    )

    text = str(data.get("prompt") or "")
    requirements = _canonical_requirements(data)

    def load_profile() -> object | None:
        from foil_profile import load

        return load()

    def route(candidate: object, profile: object) -> bool:
        from foil_policy import TaskContext
        from foil_requirements import route_requirements

        if not isinstance(candidate, tuple) or not isinstance(profile, Mapping):
            return False
        decision = route_requirements(TaskContext(), candidate, profile=profile)
        return decision.selected_complement is not None

    def render(profile: object) -> str:
        from foil_profile import compact_context

        if not isinstance(profile, Mapping):
            return ""
        return compact_context(dict(profile), budget=SMART_CONTEXT_BUDGET)

    monitor = FoilActivationMonitor(
        profile_loader=load_profile,
        requirement_router=route,
        context_renderer=render,
        max_active_context_chars=SMART_CONTEXT_BUDGET,
    )
    decision = monitor.evaluate(
        ActivationEvent(
            prompt=text,
            task_requirement=requirements or None,
            requirement_joinable=bool(requirements),
            frozen_run_binding=_frozen_binding(data),
            continuation_lease=_continuation_lease(data),
            available_context_chars=_available_context(data),
        ),
        FeatureMode(selected_mode),
    )
    if selected_mode == "smart" and decision.active_context:
        print(decision.active_context)
    return 0


def session() -> int:
    selected_mode = _auto_mode()
    if selected_mode == "legacy":
        return _legacy_session()
    if selected_mode == "off":
        return 0
    if not _l0_wake_candidate({}):
        return 0
    return _monitored({}, selected_mode)


def prompt() -> int:
    data = _input()
    selected_mode = _auto_mode()
    if selected_mode == "legacy":
        return _legacy_prompt(data)
    if selected_mode == "off":
        return 0
    if not _l0_wake_candidate(data):
        return 0
    return _monitored(data, selected_mode)


def main(argv: list[str] | None = None) -> int:
    mode = (argv or sys.argv[1:] or ["session"])[0]
    if mode == "prompt":
        return prompt()
    return session()


if __name__ == "__main__":
    raise SystemExit(main())
