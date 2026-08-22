"""Second-stage FOIL calibration for building a deeper stranger profile.

Layer 1 (foil_assessment.py) is a broad cold-start screen. This module adds a
second, evidence-driven layer: changed-representation probes, adversarial error
detection, real-work samples, open production, confidence calibration, and
cross-domain transfer. It never claims psychometric calibration.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import foil_profile

SCHEMA = "egrt.foil-deep-calibration.v1"

FACETS: dict[str, str] = {
    "formalization_precision": "Turns informal claims into explicit objects, scope, assumptions, and refuters.",
    "decomposition_systems": "Finds load-bearing components, dependencies, interfaces, and failure modes.",
    "error_detection": "Detects plausible wrong answers, hidden assumptions, and invalid inference steps.",
    "evidence_discipline": "Matches claims to current, primary, scope-entailing evidence and counterevidence.",
    "causal_reasoning": "Separates association, estimand, identification, intervention, and transport.",
    "quantitative_reasoning": "Uses quantitative structure, units, derivations, and uncertainty correctly.",
    "implementation_execution": "Moves from proposed behavior to executable checks and artifact-level evidence.",
    "design_reasoning": "Balances constraints, hierarchy, accessibility, tradeoffs, and validation.",
    "creative_search": "Generates mechanism-distinct alternatives instead of surface variants.",
    "communication_explanation": "Explains a mechanism accurately, concretely, and at an appropriate level.",
    "planning_prioritization": "Identifies the load-bearing unknown and the cheapest useful discriminator.",
    "metacognitive_calibration": "Aligns confidence and help-seeking with observed correctness.",
    "transfer_adaptation": "Carries a method across changed representation, context, or task surface.",
    "tool_selection": "Chooses proof, search, execution, measurement, or review based on the claim type.",
    "uncertainty_management": "Keeps unresolved alternatives live and updates when evidence changes.",
}

GENERIC_PROBES = [
    {
        "facet": "formalization_precision",
        "kind": "formalization",
        "domain": "cross_domain",
        "instruction": (
            "Take a claim relevant to the person's work such as 'this method works better'. "
            "Without help, specify the objects/population, baseline, metric, quantifiers, assumptions, "
            "scope, and an observation that would refute the claim."
        ),
        "review": "Check completeness, silent strengthening, scope control, and refutability.",
    },
    {
        "facet": "error_detection",
        "kind": "adversarial_error_detection",
        "domain": "cross_domain",
        "instruction": (
            "Give a plausible but materially wrong solution or argument in a familiar domain. "
            "Ask the person to locate the first load-bearing error, explain why it fails, and repair it."
        ),
        "review": "The supplied candidate must contain a real, independently checkable defect.",
    },
    {
        "facet": "evidence_discipline",
        "kind": "evidence_scope",
        "domain": "research_evidence",
        "instruction": (
            "Present a claim supported by one primary source, one derivative summary, and one source with "
            "a narrower or conflicting scope. Ask which evidence can support the exact claim and why."
        ),
        "review": "Score entailment, source independence, freshness, and explicit residual uncertainty.",
    },
    {
        "facet": "decomposition_systems",
        "kind": "systems_decomposition",
        "domain": "systems_reliability",
        "instruction": (
            "Give a small system with retries, shared state, and one stale dependency. Ask for the minimal "
            "failure model, ownership boundaries, and the first executable check that distinguishes causes."
        ),
        "review": "Look for state ownership, retry/idempotency semantics, and a diagnostic rather than more logging alone.",
    },
    {
        "facet": "design_reasoning",
        "kind": "design_tradeoff",
        "domain": "design_ux",
        "instruction": (
            "Ask for a compact interface or workflow under mobile/desktop, keyboard, low-vision, and limited-space "
            "constraints. Require two explicit tradeoffs and a validation plan."
        ),
        "review": "Review constraint coverage, information hierarchy, accessibility, tradeoffs, and validation.",
    },
    {
        "facet": "creative_search",
        "kind": "creative_mechanisms",
        "domain": "creativity_ideation",
        "instruction": (
            "Give a constrained problem and ask for at least five mechanism-distinct approaches. "
            "Require the person to explain what structural assumption changes between approaches."
        ),
        "review": "Count mechanism diversity, not wording diversity; reject near-duplicate variants.",
    },
    {
        "facet": "communication_explanation",
        "kind": "explain_back",
        "domain": "teaching_explanation",
        "instruction": (
            "Ask the person to explain a familiar technical idea to a bright beginner using one concrete example, "
            "then answer one changed-assumption follow-up without help."
        ),
        "review": "Review correctness, clarity, example quality, and whether the follow-up reveals transferable understanding.",
    },
    {
        "facet": "planning_prioritization",
        "kind": "critical_path",
        "domain": "planning_decision_making",
        "instruction": (
            "Give several plausible next actions but make only one unresolved quantity load-bearing for the decision. "
            "Ask what to do next, why, and what evidence would change the priority."
        ),
        "review": "Prefer the cheapest action that reduces the load-bearing uncertainty; note reversibility and opportunity cost.",
    },
    {
        "facet": "tool_selection",
        "kind": "verifier_selection",
        "domain": "cross_domain",
        "instruction": (
            "Give four claims: one formal theorem claim, one current factual claim, one executable software claim, "
            "and one causal claim. Ask for the strongest appropriate verifier for each and why."
        ),
        "review": "Proof/formal check, current source, execution/test, and causal identification should remain distinct.",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_deep(profile: dict[str, Any]) -> dict[str, Any]:
    deep = profile.setdefault(
        "deep_calibration",
        {
            "schema": SCHEMA,
            "created_at": _now(),
            "updated_at": _now(),
            "probe_history": [],
            "facet_evidence": {},
        },
    )
    deep.setdefault("schema", SCHEMA)
    deep.setdefault("probe_history", [])
    deep.setdefault("facet_evidence", {})
    return deep


def _facet_row(deep: dict[str, Any], facet: str) -> dict[str, Any]:
    row = deep.setdefault("facet_evidence", {}).setdefault(
        facet,
        {
            "independent_verified_pass": 0,
            "independent_verified_fail": 0,
            "independent_verified_mixed": 0,
            "assisted_or_unverified": 0,
            "representations": [],
            "domains": [],
        },
    )
    return row


def _classification(row: dict[str, Any]) -> str:
    passed = int(row.get("independent_verified_pass", 0))
    failed = int(row.get("independent_verified_fail", 0))
    mixed = int(row.get("independent_verified_mixed", 0))
    total = passed + failed + mixed
    if total < 2:
        return "INSUFFICIENT_EVIDENCE"
    if passed >= 2 and failed == 0:
        return "PROMISING_STRENGTH"
    if failed >= 2 and passed == 0:
        return "POSSIBLE_GAP"
    return "UNCERTAIN"


def _relevant_domains(profile: dict[str, Any], limit: int = 6) -> list[tuple[str, dict[str, Any]]]:
    ranked: list[tuple[int, int, str, dict[str, Any]]] = []
    priority = {
        "POSSIBLE_GAP": 0,
        "UNCERTAIN": 1,
        "PROMISING_STRENGTH": 2,
        "INSUFFICIENT_EVIDENCE": 3,
    }
    for name, row in profile.get("domains", {}).items():
        classification = row.get("classification") or foil_profile.classify(row)
        relevant = bool(row.get("declared")) or int(row.get("relevance_mentions", 0)) > 0
        if not relevant and classification == "INSUFFICIENT_EVIDENCE":
            continue
        ranked.append(
            (
                priority.get(classification, 4),
                -int(row.get("relevance_mentions", 0)),
                name,
                row,
            )
        )
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(name, row) for _, _, name, row in ranked[:limit]]


def _probe_id(profile: dict[str, Any], domain: str, kind: str) -> str:
    deep = ensure_deep(profile)
    prefix = f"{domain}:{kind}:"
    count = sum(str(item.get("probe_id", "")).startswith(prefix) for item in deep["probe_history"])
    return f"{prefix}{count + 1}"


def _domain_probe(profile: dict[str, Any], domain: str, row: dict[str, Any]) -> dict[str, Any]:
    classification = row.get("classification") or foil_profile.classify(row)
    if classification == "POSSIBLE_GAP":
        kind = "discriminator"
        facet = "transfer_adaptation"
        instruction = (
            f"Use a fresh {domain} task that tests the same underlying capability through a different representation. "
            "The person works independently, states confidence before feedback, and explains the decisive step. "
            "Choose the task so ambiguity/retrieval/execution-slip explanations make different predictions."
        )
    elif classification == "UNCERTAIN":
        kind = "changed_representation"
        facet = "transfer_adaptation"
        instruction = (
            f"Give one independently solvable {domain} task that changes notation, context, or representation from prior evidence. "
            "Require a solution plus a brief explanation of why the method transfers."
        )
    elif classification == "PROMISING_STRENGTH":
        kind = "harder_transfer"
        facet = "transfer_adaptation"
        instruction = (
            f"Give a harder {domain} problem in a changed context with no material assistance. "
            "Require the person to choose the method, solve it, and state what would falsify their answer."
        )
    else:
        kind = "representative_work"
        facet = "transfer_adaptation"
        instruction = (
            f"Choose a representative {domain} task from the person's real work or learning context. "
            "Have them attempt it independently before assistance so the result can distinguish relevance from competence."
        )
    return {
        "probe_id": _probe_id(profile, domain, kind),
        "domain": domain,
        "facet": facet,
        "kind": kind,
        "instruction": instruction,
        "review": "Record outcome, assistance, confidence, representation, and whether the result was independently verified.",
    }


def _adversarial_domain_probe(profile: dict[str, Any], domain: str) -> dict[str, Any]:
    kind = "domain_error_detection"
    return {
        "probe_id": _probe_id(profile, domain, kind),
        "domain": domain,
        "facet": "error_detection",
        "kind": kind,
        "instruction": (
            f"Provide a plausible but wrong {domain} answer, argument, design, or implementation. "
            "Ask the person to identify the first load-bearing defect, repair it, and state how they would verify the repair."
        ),
        "review": "The planted defect must be independently known before scoring; do not let the evaluator invent the defect after the response.",
    }


def _real_work_probe(profile: dict[str, Any], domain: str) -> dict[str, Any]:
    kind = "real_work"
    return {
        "probe_id": _probe_id(profile, domain, kind),
        "domain": domain,
        "facet": "implementation_execution",
        "kind": kind,
        "instruction": (
            f"Select a real, non-sensitive task or artifact in {domain}. Ask the person to propose the next action independently, "
            "execute or verify the load-bearing part when feasible, and explain why that evidence is diagnostic."
        ),
        "review": "Prefer real artifact/execution evidence; redact sensitive material before storing any notes.",
    }


def build_plan(profile: dict[str, Any], max_domains: int = 6) -> dict[str, Any]:
    ensure_deep(profile)
    probes: list[dict[str, Any]] = []
    domains = _relevant_domains(profile, max_domains)

    for domain, row in domains:
        probes.append(_domain_probe(profile, domain, row))
    for domain, _ in domains[:3]:
        probes.append(_adversarial_domain_probe(profile, domain))
    for domain, _ in domains[:2]:
        probes.append(_real_work_probe(profile, domain))

    for template in GENERIC_PROBES:
        probes.append(
            {
                "probe_id": _probe_id(profile, template["domain"], template["kind"]),
                **template,
            }
        )

    if not domains:
        probes.insert(
            0,
            {
                "probe_id": _probe_id(profile, "domain_discovery", "representative_work"),
                "domain": "domain_discovery",
                "facet": "uncertainty_management",
                "kind": "representative_work",
                "instruction": (
                    "Ask the person for two recent tasks they found easy and two they found difficult. "
                    "For each, record what they attempted independently, what help/tools were available, and what actually failed or succeeded."
                ),
                "review": "Use this only to discover candidate domains; self-description alone does not establish competence.",
            },
        )

    return {
        "schema": SCHEMA,
        "profile_id": profile["id"],
        "created_at": _now(),
        "purpose": (
            "Second-stage calibration after cold start: discriminate uncertain/gap hypotheses, confirm apparent strengths with transfer, "
            "sample real work, and measure cross-cutting reasoning facets."
        ),
        "limits": [
            "Engineering calibration layer, not a validated psychometric test.",
            "Open probes require a real rubric, artifact check, or independent reviewer before being marked verified.",
            "Assisted or unverified success cannot establish an independent strength.",
            "A deep-profile readiness gate means evidence coverage is broad enough for stronger personalization; it is not an IQ/personality score.",
        ],
        "probes": probes,
        "maturity": maturity(profile),
    }


def record(
    profile: dict[str, Any],
    *,
    probe_id: str,
    domain: str,
    facet: str,
    kind: str,
    outcome: str,
    assistance: str,
    verified: bool,
    confidence: float | None = None,
    representation: str | None = None,
    source: str = "deep_calibration",
    note: str | None = None,
) -> None:
    if facet not in FACETS:
        raise ValueError(f"unknown facet: {facet}")
    if outcome not in {"pass", "fail", "mixed"}:
        raise ValueError("outcome must be pass, fail, or mixed")

    deep = ensure_deep(profile)
    if any(item.get("probe_id") == probe_id for item in deep["probe_history"]):
        raise ValueError(f"probe already recorded: {probe_id}")

    independent = assistance in {"none", "independent"}
    event: dict[str, Any] = {
        "time": _now(),
        "probe_id": probe_id,
        "domain": foil_profile.normalize_domain(domain),
        "facet": facet,
        "kind": kind,
        "outcome": outcome,
        "assistance": assistance,
        "verified": bool(verified),
        "confidence": confidence,
        "representation": representation or kind,
        "source": source,
    }
    if note:
        event["note"] = note[:400]
    deep["probe_history"].append(event)
    deep["probe_history"] = deep["probe_history"][-300:]
    deep["updated_at"] = event["time"]

    facet_row = _facet_row(deep, facet)
    if independent and verified:
        key = {
            "pass": "independent_verified_pass",
            "fail": "independent_verified_fail",
            "mixed": "independent_verified_mixed",
        }[outcome]
        facet_row[key] = int(facet_row.get(key, 0)) + 1
    else:
        facet_row["assisted_or_unverified"] = int(facet_row.get("assisted_or_unverified", 0)) + 1
    rep = str(event["representation"])
    dom = str(event["domain"])
    if rep not in facet_row["representations"]:
        facet_row["representations"].append(rep)
    if dom not in facet_row["domains"]:
        facet_row["domains"].append(dom)
    facet_row["classification"] = _classification(facet_row)

    if verified and outcome in {"pass", "fail"} and dom not in {"cross_domain", "domain_discovery"}:
        foil_profile.observe(
            profile,
            dom,
            "correct" if outcome == "pass" else "incorrect",
            assistance,
            confidence=confidence,
            source=source,
            representation=representation or kind,
            note=note,
        )


def maturity(profile: dict[str, Any]) -> dict[str, Any]:
    deep = ensure_deep(profile)
    history = deep.get("probe_history", [])
    independent_verified = [
        event
        for event in history
        if event.get("verified")
        and event.get("assistance") in {"none", "independent"}
        and event.get("outcome") in {"pass", "fail", "mixed"}
    ]
    domains = {
        event.get("domain")
        for event in independent_verified
        if event.get("domain") not in {"cross_domain", "domain_discovery", None}
    }
    facets = {event.get("facet") for event in independent_verified if event.get("facet")}
    transfer = sum(
        event.get("kind") in {"changed_representation", "harder_transfer", "discriminator", "explain_back"}
        for event in independent_verified
    )
    real_work = sum(event.get("kind") == "real_work" for event in independent_verified)
    adversarial = sum(
        event.get("kind") in {"adversarial_error_detection", "domain_error_detection"}
        for event in independent_verified
    )
    confidence = sum(event.get("confidence") is not None for event in independent_verified)
    open_production = sum(
        event.get("kind") in {"design_tradeoff", "creative_mechanisms", "explain_back"}
        for event in independent_verified
    )

    gates = {
        "independent_verified_probes": {"value": len(independent_verified), "target": 14},
        "distinct_domains": {"value": len(domains), "target": 4},
        "cross_cutting_facets": {"value": len(facets), "target": 8},
        "transfer_or_changed_representation": {"value": transfer, "target": 3},
        "real_work_samples": {"value": real_work, "target": 2},
        "adversarial_error_detection": {"value": adversarial, "target": 2},
        "confidence_bearing_results": {"value": confidence, "target": 8},
        "open_production_results": {"value": open_production, "target": 3},
    }
    missing = [
        name
        for name, row in gates.items()
        if int(row["value"]) < int(row["target"])
    ]

    if not history:
        status = "NOT_STARTED"
    elif not missing:
        status = "DEEP_PROFILE_READY"
    elif len(independent_verified) >= 7 and len(facets) >= 5 and len(domains) >= 3:
        status = "BROAD_PROFILE"
    else:
        status = "CALIBRATING"

    return {
        "status": status,
        "gates": gates,
        "missing": missing,
        "facet_hypotheses": {
            facet: _classification(row)
            for facet, row in sorted(deep.get("facet_evidence", {}).items())
        },
        "note": (
            "Readiness is an engineering evidence-coverage gate for stronger personalization, not a psychometric or intelligence score."
        ),
    }


def deep_context(profile: dict[str, Any]) -> str:
    state = maturity(profile)
    hypotheses = state["facet_hypotheses"]
    strengths = [name for name, value in hypotheses.items() if value == "PROMISING_STRENGTH"]
    gaps = [name for name, value in hypotheses.items() if value == "POSSIBLE_GAP"]
    uncertain = [name for name, value in hypotheses.items() if value == "UNCERTAIN"]
    return (
        f"<FOIL_DEEP_PROFILE maturity={state['status']!r}>\n"
        f"promising facets: {', '.join(strengths) or 'none'}\n"
        f"possible complement facets: {', '.join(gaps) or 'none'}\n"
        f"uncertain facets: {', '.join(uncertain) or 'none'}\n"
        f"coverage gaps: {', '.join(state['missing']) or 'none'}\n"
        "Use only task-relevant evidence. Newer real-work evidence outranks onboarding. "
        "Assisted/unverified success does not establish independent competence.\n"
        "</FOIL_DEEP_PROFILE>"
    )


def _write(path: str, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOIL second-stage deep calibration")
    sub = parser.add_subparsers(dest="cmd", required=True)

    start = sub.add_parser("start")
    start.add_argument("--profile")
    start.add_argument("--max-domains", type=int, default=6)
    start.add_argument("--out", default="foil_deep_calibration.json")

    status = sub.add_parser("status")
    status.add_argument("--profile")

    next_cmd = sub.add_parser("next")
    next_cmd.add_argument("--profile")
    next_cmd.add_argument("--count", type=int, default=5)

    record_cmd = sub.add_parser("record")
    record_cmd.add_argument("--profile")
    record_cmd.add_argument("--probe-id", required=True)
    record_cmd.add_argument("--domain", required=True)
    record_cmd.add_argument("--facet", required=True, choices=sorted(FACETS))
    record_cmd.add_argument("--kind", required=True)
    record_cmd.add_argument("--outcome", required=True, choices=["pass", "fail", "mixed"])
    record_cmd.add_argument("--assistance", default="none")
    record_cmd.add_argument("--verified", action="store_true")
    record_cmd.add_argument("--confidence", type=float)
    record_cmd.add_argument("--representation")
    record_cmd.add_argument("--source", default="deep_calibration")
    record_cmd.add_argument("--note")

    args = parser.parse_args(argv)
    profile = foil_profile.load(args.profile)

    if args.cmd == "start":
        payload = build_plan(profile, args.max_domains)
        _write(args.out, payload)
        print(args.out)
        return 0
    if args.cmd == "status":
        print(json.dumps(maturity(profile), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "next":
        payload = build_plan(profile)
        print(json.dumps(payload["probes"][: max(1, args.count)], indent=2, ensure_ascii=False))
        return 0

    record(
        profile,
        probe_id=args.probe_id,
        domain=args.domain,
        facet=args.facet,
        kind=args.kind,
        outcome=args.outcome,
        assistance=args.assistance,
        verified=args.verified,
        confidence=args.confidence,
        representation=args.representation,
        source=args.source,
        note=args.note,
    )
    foil_profile.save(profile)
    print(json.dumps(maturity(profile), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
