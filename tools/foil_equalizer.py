"""FOIL Layer 2C: universal evidence equalizer and task-policy compiler.

Balances deep-calibration evidence across transferable capability families and
compiles profile evidence into current-task support/verification policy. This is
an engineering personalization layer, not a validated psychometric model.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import foil_domains
import foil_profile

SCHEMA = "egrt.foil-universal-refinement.v1"

FACET_FAMILY = {
    "formalization_precision": "reasoning_representation",
    "quantitative_reasoning": "reasoning_representation",
    "verbal_reasoning": "reasoning_representation",
    "spatial_structural_reasoning": "reasoning_representation",
    "data_interpretation": "reasoning_representation",
    "evidence_discipline": "epistemic_scientific",
    "causal_reasoning": "epistemic_scientific",
    "experimental_design": "epistemic_scientific",
    "benchmark_construct_validity": "epistemic_scientific",
    "uncertainty_management": "epistemic_scientific",
    "error_detection": "epistemic_scientific",
    "decomposition_systems": "systems_execution",
    "implementation_execution": "systems_execution",
    "interface_integration": "systems_execution",
    "tool_selection": "systems_execution",
    "design_reasoning": "creation_communication",
    "creative_search": "creation_communication",
    "communication_explanation": "creation_communication",
    "self_explanation": "creation_communication",
    "planning_prioritization": "strategy_integration",
    "integration_synthesis": "strategy_integration",
    "metacognitive_calibration": "learning_metacognition",
    "transfer_adaptation": "learning_metacognition",
    "learning_diagnosis": "learning_metacognition",
    "retrieval_retention": "learning_metacognition",
    "decision_calibration": "learning_metacognition",
}

# Targets count distinct independently verified facets, not repeated questions.
FAMILY_TARGETS = {
    "reasoning_representation": 3,
    "epistemic_scientific": 3,
    "systems_execution": 2,
    "creation_communication": 2,
    "strategy_integration": 2,
    "learning_metacognition": 3,
}

# family, facet, kind, instruction, review contract
PROBES = [
    ("reasoning_representation", "verbal_reasoning", "qualifier_preservation", "Restate a dense claim while preserving qualifiers, exceptions, scope, and uncertainty; then state one refuter.", "Check semantic/scope preservation and silent strengthening."),
    ("reasoning_representation", "spatial_structural_reasoning", "structure_transform", "Reconstruct a small diagram/dependency/spatial structure in another representation and answer one relation query.", "Verify structural relation preservation; presentation preference is not aptitude."),
    ("reasoning_representation", "data_interpretation", "table_rate_uncertainty", "Interpret unequal denominators, rates, counts, and uncertainty; give one licensed and one invalid conclusion.", "Check denominators, uncertainty, and scope."),
    ("epistemic_scientific", "experimental_design", "experiment_design", "Design the smallest discriminating experiment: population, intervention, comparator, endpoint, controls, analysis/stopping rule, and failure interpretation.", "Check identification, leakage, selection, and decision relevance."),
    ("epistemic_scientific", "benchmark_construct_validity", "benchmark_scope", "Given a strong benchmark result and a broader capability claim, state what is licensed, what is not, and design a transfer/holdout test.", "Check contamination, construct validity, metric fit, and generalization."),
    ("epistemic_scientific", "error_detection", "adversarial_claim", "Diagnose and repair a plausible but materially wrong argument whose first load-bearing defect is fixed before scoring.", "The planted defect must be independently known before judging."),
    ("systems_execution", "interface_integration", "interface_integration", "Integrate components with mismatched assumptions. Specify contracts, state ownership, first end-to-end test, failure propagation, and rollback boundary.", "Check interfaces, ownership, and executable diagnostics."),
    ("systems_execution", "tool_selection", "mixed_verifier_selection", "Match arithmetic, theorem, current-fact, empirical, software, and design claims to diagnostic verifiers.", "Verifier must match the claim and fail independently enough to add information."),
    ("creation_communication", "design_reasoning", "design_constraint_shift", "Design under accessibility, space, and information constraints; then adapt when one high-impact constraint changes.", "Check hierarchy, accessibility, tradeoffs, validation, and structural adaptation."),
    ("creation_communication", "creative_search", "mechanism_diversity", "Generate five mechanism-distinct solutions; remove one assumption and identify which mechanisms survive.", "Count structural diversity, not wording diversity."),
    ("creation_communication", "self_explanation", "teach_and_transfer", "Explain a familiar method, state failure conditions, then handle a changed-context case without material help.", "Check correctness, boundaries, explanation, and transfer."),
    ("strategy_integration", "integration_synthesis", "conflicting_requirements", "Resolve conflicting cost, risk, speed, quality, and stakeholder requirements; name the one unknown most likely to change the decision.", "Check tradeoffs, assumptions, dependencies, and sensitivity."),
    ("strategy_integration", "planning_prioritization", "portfolio_priority", "Prioritize tasks by reversibility, information value, cost, dependency position, and downside; justify stop/defer choices.", "Prefer upstream, information-rich, reversible actions when uncertainty matters."),
    ("learning_metacognition", "learning_diagnosis", "same_error_different_cause", "Given similar errors with different causes, choose the smallest probe separating knowledge, retrieval, wording, context, and execution explanations.", "Do not reward immediate trait labeling."),
    ("learning_metacognition", "metacognitive_calibration", "confidence_and_help", "Commit answer, confidence, and help/search need before feedback; score correctness separately from calibration/help choice.", "Confidence and help preference are not ability scores."),
    ("learning_metacognition", "retrieval_retention", "delayed_unassisted_retrieval", "After a real delay, reconstruct/apply a previously demonstrated method on a non-identical case without relevant assistance.", "Invalid if immediate, cued by the original solution, or materially assisted."),
]

TASK_PATTERNS = {
    "formalization_precision": ("prove", "theorem", "formal", "logic", "counterexample"),
    "quantitative_reasoning": ("calculate", "estimate", "probability", "statistics", "equation"),
    "evidence_discipline": ("source", "paper", "research", "latest", "current", "evidence", "citation"),
    "experimental_design": ("experiment", "ablation", "control", "causal", "preregister"),
    "benchmark_construct_validity": ("benchmark", "score", "evaluation", "generalize", "holdout"),
    "decomposition_systems": ("architecture", "system", "integration", "workflow", "dependency", "distributed"),
    "implementation_execution": ("code", "implement", "debug", "repository", "build", "test"),
    "design_reasoning": ("design", "ui", "ux", "accessibility", "layout", "interface"),
    "creative_search": ("brainstorm", "creative", "invent", "ideas", "novel"),
    "communication_explanation": ("explain", "teach", "write", "presentation", "document"),
    "planning_prioritization": ("plan", "roadmap", "priority", "decide", "strategy", "next"),
    "tool_selection": ("verify", "tool", "solver", "search", "browser", "run"),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure(profile: dict[str, Any]) -> dict[str, Any]:
    state = profile.setdefault(
        "universal_refinement",
        {"schema": SCHEMA, "created_at": now(), "events": [], "issued": {}, "self_estimates": {}, "assessment_context": {}},
    )
    for key, default in (("events", []), ("issued", {}), ("self_estimates", {}), ("assessment_context", {})):
        state.setdefault(key, default)
    return state


def ingest_layer1(profile: dict[str, Any], report: dict[str, Any]) -> None:
    state = ensure(profile)
    state["self_estimates"].update(
        {foil_profile.normalize_domain(key): value for key, value in report.get("self_estimates", {}).items() if value is not None}
    )
    state["assessment_context"] = {key: value for key, value in report.get("context", {}).items() if value not in (None, "")}
    state["updated_at"] = now()


def all_events(profile: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *profile.get("deep_calibration", {}).get("probe_history", []),
        *profile.get("universal_refinement", {}).get("events", []),
    ]


def independent_verified(event: dict[str, Any]) -> bool:
    return (
        bool(event.get("verified"))
        and event.get("assistance") in {"none", "independent"}
        and event.get("outcome") in {"pass", "fail", "mixed"}
    )


def event_family(event: dict[str, Any]) -> str | None:
    if event.get("family"):
        return str(event["family"])
    return FACET_FAMILY.get(str(event.get("facet") or ""))


def relevant_domains(profile: dict[str, Any]) -> list[str]:
    ranked: list[tuple[int, int, str]] = []
    for name, row in profile.get("domains", {}).items():
        relevant = bool(row.get("declared")) or int(row.get("relevance_mentions", 0)) > 0 or bool(row.get("observations"))
        if relevant:
            ranked.append((0 if row.get("declared") else 1, -int(row.get("relevance_mentions", 0)), name))
    return [name for _, _, name in sorted(ranked)]


def coverage(profile: dict[str, Any]) -> dict[str, Any]:
    good = [event for event in all_events(profile) if independent_verified(event)]
    family_facets = {family: set() for family in FAMILY_TARGETS}
    observed_domains: set[str] = set()
    representations: set[str] = set()
    kinds: list[str] = []
    confidence_count = 0
    for event in good:
        family = event_family(event)
        facet = str(event.get("facet") or "")
        if family in family_facets and facet:
            family_facets[family].add(facet)
        domain = str(event.get("domain") or "")
        if domain and domain not in {"cross_domain", "domain_discovery"}:
            observed_domains.add(domain)
        if event.get("representation"):
            representations.add(str(event["representation"]))
        kinds.append(str(event.get("kind") or ""))
        confidence_count += int(event.get("confidence") is not None)

    family_counts = {family: len(facets) for family, facets in family_facets.items()}
    missing_families = [family for family, target in FAMILY_TARGETS.items() if family_counts[family] < target]
    relevant = relevant_domains(profile)
    domain_target = min(3, len(relevant))
    domain_evidence = len(observed_domains.intersection(relevant))
    transfer = sum(kind in {"changed_representation", "harder_transfer", "discriminator", "teach_and_transfer", "structure_transform"} for kind in kinds)
    real_work = sum(kind == "real_work" for kind in kinds)
    adversarial = sum(kind in {"adversarial_claim", "adversarial_error_detection", "domain_error_detection"} for kind in kinds)
    delayed = sum(kind == "delayed_unassisted_retrieval" for kind in kinds)
    extra = {
        "relevant_domain_evidence": (domain_evidence, domain_target),
        "distinct_representations": (len(representations), 6),
        "transfer_events": (transfer, 3),
        "real_work_samples": (real_work, 2 if relevant else 0),
        "adversarial_error_detection": (adversarial, 2),
        "confidence_bearing_results": (confidence_count, 8),
        "delayed_unassisted_retrieval": (delayed, 1),
    }
    missing_extra = [name for name, (value, target) in extra.items() if value < target]

    if not good:
        status = "NOT_STARTED"
    elif not missing_families and not missing_extra:
        status = "HIGH_FIDELITY_PROFILE"
    elif not missing_families and missing_extra == ["delayed_unassisted_retrieval"]:
        status = "HIGH_FIDELITY_PENDING_RETENTION"
    elif len(good) >= 8 and sum(family not in missing_families for family in FAMILY_TARGETS) >= 4:
        status = "PERSONALIZED_OPERATIONAL"
    else:
        status = "EQUALIZING"

    return {
        "schema": SCHEMA,
        "status": status,
        "family_distinct_facets": family_counts,
        "family_targets": FAMILY_TARGETS,
        "missing_families": missing_families,
        "coverage": {name: {"value": value, "target": target} for name, (value, target) in extra.items()},
        "missing_extra": missing_extra,
        "note": "Evidence-coverage state for personalization; not an intelligence, personality, or psychometric score.",
    }


def probe_id(profile: dict[str, Any], domain: str, kind: str) -> str:
    prefix = f"{foil_profile.normalize_domain(domain)}:{kind}:"
    used = {str(event.get("probe_id") or "") for event in all_events(profile)} | set(ensure(profile)["issued"])
    index = 1
    while f"{prefix}{index}" in used:
        index += 1
    return f"{prefix}{index}"


def make_probe(profile: dict[str, Any], template: tuple[str, str, str, str, str], domain: str = "cross_domain") -> dict[str, Any]:
    family, facet, kind, instruction, review = template
    probe = {
        "probe_id": probe_id(profile, domain, kind),
        "family": family,
        "facet": facet,
        "domain": domain,
        "kind": kind,
        "instruction": instruction,
        "review": review,
        "assistance": "none",
    }
    if kind == "delayed_unassisted_retrieval":
        probe["not_before"] = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    return probe


def domain_probe(profile: dict[str, Any], domain: str) -> dict[str, Any]:
    row = profile.get("domains", {}).get(domain, {})
    classification = row.get("classification") or foil_profile.classify(row)
    if classification == "PROMISING_STRENGTH":
        kind = "harder_transfer"
        instruction = f"Give a harder {domain} task in a changed context with no material assistance; require method choice, solution, assumptions, and a refuter."
    elif classification == "POSSIBLE_GAP":
        kind = "discriminator"
        instruction = f"Give a fresh {domain} task whose representation separates knowledge gap, retrieval failure, ambiguity, and execution-slip explanations; collect confidence before feedback."
    elif classification == "UNCERTAIN":
        kind = "changed_representation"
        instruction = f"Give one independently solvable {domain} task that changes notation, context, or representation from prior evidence."
    else:
        kind = "real_work"
        instruction = f"Use a representative, non-sensitive {domain} task or artifact from the person's real work; require an independent first action and a claim-native check."
    real_work = kind == "real_work"
    return {
        "probe_id": probe_id(profile, domain, kind),
        "family": "systems_execution" if real_work else "learning_metacognition",
        "facet": "implementation_execution" if real_work else "transfer_adaptation",
        "domain": domain,
        "kind": kind,
        "instruction": instruction,
        "review": "Record outcome, assistance, confidence, representation, and independent verifier/evidence.",
        "assistance": "none",
    }


def build_plan(profile: dict[str, Any], assessment_report: dict[str, Any] | None = None, max_probes: int = 12) -> dict[str, Any]:
    if assessment_report:
        ingest_layer1(profile, assessment_report)
    state = ensure(profile)
    cov = coverage(profile)
    good = [event for event in all_events(profile) if independent_verified(event)]
    completed_facets = {str(event.get("facet") or "") for event in good}
    probes: list[dict[str, Any]] = []

    for family in cov["missing_families"]:
        target = FAMILY_TARGETS[family]
        needed = target - cov["family_distinct_facets"][family]
        for template in PROBES:
            if template[0] == family and template[1] not in completed_facets:
                probes.append(make_probe(profile, template))
                if sum(probe["family"] == family for probe in probes) >= needed:
                    break

    # Self-estimates are compared neutrally; the person is not told which direction FOIL expects.
    for domain, estimate in state.get("self_estimates", {}).items():
        row = profile.get("domains", {}).get(domain, {})
        classification = row.get("classification") or foil_profile.classify(row)
        if estimate is not None and classification != "INSUFFICIENT_EVIDENCE":
            probes.append({
                "probe_id": probe_id(profile, domain, "self_estimate_check"),
                "family": "learning_metacognition",
                "facet": "decision_calibration",
                "domain": domain,
                "kind": "self_estimate_check",
                "instruction": f"Give a fresh independent {domain} task without revealing whether prior self-estimate and observed performance agree. Collect confidence before feedback and use the result only as another observation.",
                "review": "Do not label over/under-confidence from one mismatch.",
                "assistance": "none",
            })

    relevant = relevant_domains(profile)
    evidenced = {str(event.get("domain") or "") for event in good}
    for domain in relevant[:6]:
        classification = profile.get("domains", {}).get(domain, {}).get("classification")
        if domain not in evidenced or classification in {"PROMISING_STRENGTH", "POSSIBLE_GAP", "UNCERTAIN"}:
            probes.append(domain_probe(profile, domain))

    if cov["coverage"]["delayed_unassisted_retrieval"]["value"] < 1:
        retention = next(template for template in PROBES if template[2] == "delayed_unassisted_retrieval")
        probes.append(make_probe(profile, retention))

    unique: list[dict[str, Any]] = []
    signatures: set[tuple[str, str, str]] = set()
    for probe in probes:
        signature = (probe["domain"], probe["facet"], probe["kind"])
        if signature in signatures:
            continue
        signatures.add(signature)
        unique.append(probe)
        if len(unique) >= max(1, max_probes):
            break

    for probe in unique:
        state["issued"][probe["probe_id"]] = {key: probe.get(key) for key in ("family", "facet", "domain", "kind", "not_before")}
    state["updated_at"] = now()
    return {
        "schema": SCHEMA,
        "profile_id": profile["id"],
        "created_at": now(),
        "coverage_before": cov,
        "probes": unique,
        "limits": [
            "Not an IQ, personality, clinical, employment, or validated psychometric test.",
            "Preferences tune interaction style only; they are not learning-style aptitude claims.",
            "Highest-fidelity status requires delayed unassisted retrieval plus real-work evidence.",
            "Newer verified real-work evidence overrides onboarding priors.",
        ],
    }


def record(
    profile: dict[str, Any], *, probe_id: str, family: str, facet: str, domain: str, kind: str,
    outcome: str, assistance: str, verified: bool, confidence: float | None = None,
    representation: str | None = None, note: str | None = None,
) -> None:
    if family not in FAMILY_TARGETS or FACET_FAMILY.get(facet) != family:
        raise ValueError("invalid family/facet combination")
    if outcome not in {"pass", "fail", "mixed"}:
        raise ValueError("outcome must be pass, fail, or mixed")
    state = ensure(profile)
    if any(event.get("probe_id") == probe_id for event in all_events(profile)):
        raise ValueError(f"probe already recorded: {probe_id}")
    issued = state["issued"].get(probe_id)
    if issued:
        expected = (issued.get("family"), issued.get("facet"), issued.get("domain"), issued.get("kind"))
        if expected != (family, facet, domain, kind):
            raise ValueError("record metadata does not match issued probe")
        if issued.get("not_before") and datetime.now(timezone.utc) < datetime.fromisoformat(str(issued["not_before"])):
            raise ValueError(f"delayed retrieval probe is not valid before {issued['not_before']}")
    event = {
        "time": now(), "probe_id": probe_id, "family": family, "facet": facet,
        "domain": foil_profile.normalize_domain(domain), "kind": kind, "outcome": outcome,
        "assistance": assistance, "verified": bool(verified), "confidence": confidence,
        "representation": representation or kind, "source": "universal_refinement",
    }
    if note:
        event["note"] = note[:400]
    state["events"].append(event)
    state["events"] = state["events"][-400:]
    state["updated_at"] = event["time"]
    if independent_verified(event) and outcome in {"pass", "fail"} and event["domain"] not in {"cross_domain", "domain_discovery"}:
        foil_profile.observe(
            profile, event["domain"], "correct" if outcome == "pass" else "incorrect", assistance,
            confidence=confidence, source="universal_refinement", representation=representation or kind, note=note,
        )


def task_facets(text: str) -> list[str]:
    low = text.lower()
    return list(dict.fromkeys(facet for facet, patterns in TASK_PATTERNS.items() if any(pattern in low for pattern in patterns)))


def task_domains(text: str) -> list[str]:
    return list(dict.fromkeys([*foil_profile.infer_domains(text), *foil_domains.infer_domains(text)]))


def facet_class(profile: dict[str, Any], facet: str) -> str:
    deep = profile.get("deep_calibration", {}).get("facet_evidence", {}).get(facet)
    if deep:
        return str(deep.get("classification") or "INSUFFICIENT_EVIDENCE")
    rows = [event for event in ensure(profile)["events"] if event.get("facet") == facet and independent_verified(event)]
    if len(rows) < 2:
        return "INSUFFICIENT_EVIDENCE"
    passed = sum(event.get("outcome") == "pass" for event in rows)
    failed = sum(event.get("outcome") == "fail" for event in rows)
    if passed >= 2 and failed == 0:
        return "PROMISING_STRENGTH"
    if failed >= 2 and passed == 0:
        return "POSSIBLE_GAP"
    return "UNCERTAIN"


def recommend_policy(profile: dict[str, Any], task: str, *, stakes: str = "normal", goal: str = "balance", urgency: str = "normal") -> dict[str, Any]:
    facets = task_facets(task)
    domains = task_domains(task)
    facet_classes = {facet: facet_class(profile, facet) for facet in facets}
    domain_classes = {
        domain: (profile.get("domains", {}).get(domain, {}).get("classification") or foil_profile.classify(profile.get("domains", {}).get(domain, {})))
        for domain in domains
    }
    values = [*facet_classes.values(), *domain_classes.values()]
    gap = any(value == "POSSIBLE_GAP" for value in values)
    uncertain = any(value in {"UNCERTAIN", "INSUFFICIENT_EVIDENCE"} for value in values)
    promising = bool(values) and all(value == "PROMISING_STRENGTH" for value in values)
    mature = coverage(profile)["status"] in {"PERSONALIZED_OPERATIONAL", "HIGH_FIDELITY_PENDING_RETENTION", "HIGH_FIDELITY_PROFILE"}
    trusted = promising and mature

    current = bool(re.search(r"\b(latest|current|today|recent|version|price|law|schedule|who is|as of)\b", task, re.I))
    executable = bool(re.search(r"\b(code|build|compile|run|test|debug|repository|sql|script)\b", task, re.I))
    formal = bool(re.search(r"\b(prove|theorem|formal|logic|counterexample|exact)\b", task, re.I))
    high = stakes.lower() in {"high", "critical", "max"}
    fast = urgency.lower() in {"high", "urgent", "deadline"}
    learning = goal.lower() in {"learn", "learning", "independence", "mastery"}

    verification = "maximum" if high else "high" if current or executable or formal or "evidence_discipline" in facets else "ordinary"
    if fast or high:
        support, friction = "direct_verified", "minimal"
    elif learning and trusted:
        support, friction = "independent_first", "commitment"
    elif learning and gap:
        support, friction = "worked_example_then_faded_probe", "light"
    elif learning and (uncertain or promising):
        support, friction = "minimal_diagnostic_then_scaffold", "light"
    elif gap:
        support, friction = "solve_with_explicit_complement", "minimal"
    else:
        support, friction = "solve_then_optional_transfer", "minimal"

    verifiers: list[str] = []
    if current:
        verifiers.append("current_primary_source")
    if executable:
        verifiers.append("execution_or_test")
    if formal:
        verifiers.append("formal_or_exhaustive_check")
    if "experimental_design" in facets or "causal_reasoning" in facets:
        verifiers.append("causal_design_and_assumption_check")
    if not verifiers:
        verifiers.append("claim_native_check_if_load_bearing")

    return {
        "schema": SCHEMA,
        "task_domains": domains,
        "task_facets": facets,
        "evidence_classes": {"facets": facet_classes, "domains": domain_classes},
        "support_mode": support,
        "verification_intensity": verification,
        "pedagogical_friction": friction,
        "preferred_verifiers": verifiers,
        "diagnostic_probe_needed": bool(learning and (gap or uncertain)),
        "profile_coverage": coverage(profile)["status"],
        "rule": "Current task evidence overrides profile priors; verification intensity and pedagogical friction are separate controls.",
    }


def context(profile: dict[str, Any], task: str | None = None) -> str:
    state = coverage(profile)
    lines = [
        f"<FOIL_EQUALIZER status={state['status']!r}>",
        f"missing families: {', '.join(state['missing_families']) or 'none'}",
        f"missing coverage: {', '.join(state['missing_extra']) or 'none'}",
    ]
    if task:
        policy = recommend_policy(profile, task)
        lines.extend([
            f"task facets: {', '.join(policy['task_facets']) or 'unclassified'}",
            f"support mode: {policy['support_mode']}",
            f"verification: {policy['verification_intensity']}",
            f"pedagogical friction: {policy['pedagogical_friction']}",
        ])
    lines.extend([
        "Profile evidence is provisional; domain relevance is not competence; current task evidence overrides stale priors.",
        "</FOIL_EQUALIZER>",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOIL universal profile equalizer")
    sub = parser.add_subparsers(dest="cmd", required=True)
    start = sub.add_parser("start")
    start.add_argument("--profile")
    start.add_argument("--assessment-report")
    start.add_argument("--max-probes", type=int, default=12)
    start.add_argument("--out", default="foil_equalizer_plan.json")
    status = sub.add_parser("status")
    status.add_argument("--profile")
    policy = sub.add_parser("policy")
    policy.add_argument("--profile")
    policy.add_argument("--task", required=True)
    policy.add_argument("--stakes", default="normal")
    policy.add_argument("--goal", default="balance")
    policy.add_argument("--urgency", default="normal")
    rec = sub.add_parser("record")
    rec.add_argument("--profile")
    rec.add_argument("--probe-id", required=True)
    rec.add_argument("--family", required=True, choices=sorted(FAMILY_TARGETS))
    rec.add_argument("--facet", required=True, choices=sorted(FACET_FAMILY))
    rec.add_argument("--domain", required=True)
    rec.add_argument("--kind", required=True)
    rec.add_argument("--outcome", required=True, choices=["pass", "fail", "mixed"])
    rec.add_argument("--assistance", default="none")
    rec.add_argument("--verified", action="store_true")
    rec.add_argument("--confidence", type=float)
    rec.add_argument("--representation")
    rec.add_argument("--note")
    args = parser.parse_args(argv)
    profile = foil_profile.load(args.profile)
    if args.cmd == "start":
        report = json.loads(Path(args.assessment_report).read_text(encoding="utf-8")) if args.assessment_report else None
        payload = build_plan(profile, report, args.max_probes)
        foil_profile.save(profile)
        Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(args.out)
        return 0
    if args.cmd == "status":
        print(json.dumps(coverage(profile), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "policy":
        print(json.dumps(recommend_policy(profile, args.task, stakes=args.stakes, goal=args.goal, urgency=args.urgency), indent=2, ensure_ascii=False))
        return 0
    record(
        profile,
        probe_id=args.probe_id,
        family=args.family,
        facet=args.facet,
        domain=args.domain,
        kind=args.kind,
        outcome=args.outcome,
        assistance=args.assistance,
        verified=args.verified,
        confidence=args.confidence,
        representation=args.representation,
        note=args.note,
    )
    foil_profile.save(profile)
    print(json.dumps(coverage(profile), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
