"""Structured second-layer calibration for FOIL.

Layer 1 (foil_assessment.py) is a broad domain screen. This module adds a
stranger-friendly Layer 2 screen for cross-cutting reasoning capabilities.
It is an engineering calibration instrument, not a psychometric diagnosis.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import foil_calibration as fc
import foil_profile

SCHEMA = "egrt.foil-layer2.v1"

# Two independently scored scenarios per facet. Correct responses live in this
# module, never in the generated session payload.
ITEMS: list[dict[str, Any]] = [
    {
        "id": "formalization-1",
        "facet": "formalization_precision",
        "kind": "quantifier_negation",
        "representation": "logic-language",
        "prompt": "A claim says: 'Every run of this method succeeds.' Which statement is the exact negation?",
        "correct": "At least one run of the method does not succeed",
        "distractors": ["No run succeeds", "Most runs fail", "The method has not been tested enough"],
    },
    {
        "id": "formalization-2",
        "facet": "formalization_precision",
        "kind": "success_definition",
        "representation": "research-claim",
        "prompt": "A team says 'the new system works better' but has not defined better. What is the strongest next move?",
        "correct": "Specify the baseline, metric, scope, assumptions, and refutation condition",
        "distractors": ["Collect more examples first", "Assume faster means better", "Rewrite the claim more confidently"],
    },
    {
        "id": "decomposition-1",
        "facet": "decomposition_systems",
        "kind": "load_bearing_unknown",
        "representation": "project-planning",
        "prompt": "A project has ten polish tasks, but one unmeasured condition determines whether the core approach can work. What should be isolated first?",
        "correct": "The load-bearing condition that can invalidate the approach",
        "distractors": ["The easiest cosmetic task", "The task with the most files", "All tasks equally"],
    },
    {
        "id": "decomposition-2",
        "facet": "decomposition_systems",
        "kind": "state_boundary",
        "representation": "systems",
        "prompt": "Two processes share state; one may be using a stale snapshot. What is the most useful first decomposition?",
        "correct": "Identify state ownership, refresh semantics, and the boundary where versions can diverge",
        "distractors": ["Add more logging everywhere", "Restart both processes and assume the problem is solved", "Rename the shared file"],
    },
    {
        "id": "error-1",
        "facet": "error_detection",
        "kind": "evaluator_fallibility",
        "representation": "benchmark",
        "prompt": "A benchmark marks an answer wrong, but direct recomputation shows the candidate answer is mathematically correct. What follows?",
        "correct": "The evaluator/key must be audited before using the benchmark verdict",
        "distractors": ["The benchmark is always right", "The candidate must change its answer", "Average the two answers"],
    },
    {
        "id": "error-2",
        "facet": "error_detection",
        "kind": "hidden_assumption",
        "representation": "argument",
        "prompt": "An argument says 'the test suite is green, therefore production behavior is correct.' What is the load-bearing defect?",
        "correct": "The tests may not observe the production failure modes being claimed absent",
        "distractors": ["Green is the wrong color", "Production behavior is never testable", "More test files automatically make the inference valid"],
    },
    {
        "id": "evidence-1",
        "facet": "evidence_discipline",
        "kind": "scope_entailment",
        "representation": "literature",
        "prompt": "A paper reports a 20% gain on one benchmark. A summary claims a 20% gain in all domains. What is supported?",
        "correct": "Only the benchmark-specific gain unless further evidence supports the broader scope",
        "distractors": ["The all-domain claim", "The method fails in every other domain", "Whichever claim has more citations"],
    },
    {
        "id": "evidence-2",
        "facet": "evidence_discipline",
        "kind": "source_independence",
        "representation": "source-chain",
        "prompt": "Five articles repeat the same press release without independent data. How much independent corroboration is that?",
        "correct": "Essentially one underlying evidentiary source",
        "distractors": ["Five independent confirmations", "Zero evidence of any kind", "Enough to prove causality"],
    },
    {
        "id": "causal-1",
        "facet": "causal_reasoning",
        "kind": "confounding",
        "representation": "observational",
        "prompt": "Umbrella use and traffic accidents both rise on rainy days. What is the strongest first causal explanation?",
        "correct": "Rain is a common cause of umbrella use and accident risk",
        "distractors": ["Umbrellas necessarily cause accidents", "Accidents cause umbrellas", "Correlation proves no relation exists"],
    },
    {
        "id": "causal-2",
        "facet": "causal_reasoning",
        "kind": "intervention",
        "representation": "experiment",
        "prompt": "A strong X-Y correlation is observed. Which evidence most directly supports the claim that changing X changes Y?",
        "correct": "A well-designed intervention on X with an appropriate comparison and identified assumptions",
        "distractors": ["A larger correlation coefficient", "More mentions of X in papers", "A prettier regression plot"],
    },
    {
        "id": "quant-1",
        "facet": "quantitative_reasoning",
        "kind": "units",
        "representation": "dimensional-analysis",
        "prompt": "A reported speedup is computed by dividing 120 seconds by 30 seconds. What is the correct unit for the ratio?",
        "correct": "Dimensionless; it is a 4x ratio",
        "distractors": ["Seconds squared", "Seconds", "Runs per second"],
    },
    {
        "id": "quant-2",
        "facet": "quantitative_reasoning",
        "kind": "base_rate",
        "representation": "risk",
        "prompt": "A rare event has a 1% base rate. A detector is 90% sensitive but has a 10% false-positive rate. What should you avoid assuming after a positive result?",
        "correct": "That the event is 90% likely without accounting for the base rate and false positives",
        "distractors": ["That sensitivity matters", "That false positives matter", "That Bayes-style updating can be useful"],
    },
    {
        "id": "execution-1",
        "facet": "implementation_execution",
        "kind": "executable_claim",
        "representation": "software",
        "prompt": "A claim says a command-line tool handles spaces in file paths. The code is available. What is the strongest check?",
        "correct": "Run the tool on a path containing spaces and inspect the actual result",
        "distractors": ["Read only the README", "Ask another model whether it should work", "Assume quoting is correct because the code looks clean"],
    },
    {
        "id": "execution-2",
        "facet": "implementation_execution",
        "kind": "integration_check",
        "representation": "runtime",
        "prompt": "Unit tests pass but the feature fails only when two components are connected. What evidence is now most diagnostic?",
        "correct": "An integration or end-to-end execution that reproduces the connected state",
        "distractors": ["More isolated unit tests only", "A design mockup", "A changelog entry"],
    },
    {
        "id": "planning-1",
        "facet": "planning_prioritization",
        "kind": "value_of_information",
        "representation": "decision",
        "prompt": "Two next actions have similar upside. One is cheap and reversible and would reveal whether the expensive irreversible action is worthwhile. Which should usually go first under high uncertainty?",
        "correct": "The cheap reversible information-gathering action",
        "distractors": ["The expensive irreversible action", "Whichever sounds more ambitious", "Random choice"],
    },
    {
        "id": "planning-2",
        "facet": "planning_prioritization",
        "kind": "stop_rule",
        "representation": "research-program",
        "prompt": "A line of work has repeatedly failed the same predeclared criterion with no new evidence or mechanism. What is the disciplined next state?",
        "correct": "Stop or redirect until materially new evidence or a different mechanism appears",
        "distractors": ["Repeat indefinitely", "Lower the criterion after seeing the failures", "Declare success because effort was high"],
    },
    {
        "id": "meta-1",
        "facet": "metacognitive_calibration",
        "kind": "confidence_update",
        "representation": "feedback",
        "prompt": "You were 95% confident in an answer, then a direct calculation falsifies it. What should happen to the belief?",
        "correct": "Update the belief substantially and investigate why confidence was miscalibrated",
        "distractors": ["Keep the original belief because confidence was high", "Ignore the calculation", "Increase confidence to defend consistency"],
    },
    {
        "id": "meta-2",
        "facet": "metacognitive_calibration",
        "kind": "uncertain_memory",
        "representation": "current-fact",
        "prompt": "You are unsure about a current software version and know versions change frequently. What is the better response?",
        "correct": "Treat memory as uncertain and check a current authoritative source",
        "distractors": ["Answer from memory with high confidence", "Choose the version that sounds newest", "Use the oldest tutorial available"],
    },
    {
        "id": "transfer-1",
        "facet": "transfer_adaptation",
        "kind": "changed_context",
        "representation": "method-transfer",
        "prompt": "A debugging method worked on one system. You move to a different system with different state ownership. What is the strongest transfer strategy?",
        "correct": "Carry over the underlying diagnostic principle but revalidate assumptions and interfaces",
        "distractors": ["Copy every step unchanged", "Discard all prior knowledge", "Assume matching terminology means matching behavior"],
    },
    {
        "id": "transfer-2",
        "facet": "transfer_adaptation",
        "kind": "changed_representation",
        "representation": "notation-transfer",
        "prompt": "A person solves a concept in familiar notation but fails when the same structure is expressed differently. What does that most directly call for?",
        "correct": "A changed-representation probe before claiming durable ownership",
        "distractors": ["A permanent weakness label", "More of the identical notation", "A personality classification"],
    },
    {
        "id": "tool-1",
        "facet": "tool_selection",
        "kind": "native_verifier",
        "representation": "claim-types",
        "prompt": "Which mapping best matches claim type to verifier?",
        "correct": "Theorem→proof/prover; current fact→current source; software behavior→execution/test; causal claim→identification/intervention evidence",
        "distractors": ["Use web search for all four", "Use model confidence for all four", "Use unit tests for all four"],
    },
    {
        "id": "tool-2",
        "facet": "tool_selection",
        "kind": "independence",
        "representation": "verification",
        "prompt": "Why can checking an answer with the exact same method that produced it be weak verification?",
        "correct": "The same failure mode may reproduce the same error, so a differently failing verifier can add information",
        "distractors": ["Any repeated check is invalid", "Independent checks are always slower and therefore worse", "Verification should never reuse information"],
    },
    {
        "id": "uncertainty-1",
        "facet": "uncertainty_management",
        "kind": "scope_split",
        "representation": "conflicting-evidence",
        "prompt": "Two strong sources disagree, but one studies population A and the other population B. What is the strongest immediate conclusion?",
        "correct": "The disagreement may be a scope split; preserve both until transport between A and B is justified",
        "distractors": ["Average the claims", "Choose the newer source regardless of scope", "Declare one source false without further analysis"],
    },
    {
        "id": "uncertainty-2",
        "facet": "uncertainty_management",
        "kind": "absence_claim",
        "representation": "search",
        "prompt": "A prior-art search finds nothing in the searched sources. What does that establish?",
        "correct": "Only that nothing relevant was found in the searched scope; nonexistence or novelty remains stronger than the evidence",
        "distractors": ["The idea is novel everywhere", "The idea is impossible", "The search proves no related work exists"],
    },
]

OPEN_PROBES = [
    {
        "id": "design-open",
        "facet": "design_reasoning",
        "prompt": "Design a compact research status view for desktop and phone. It must show current state, one next action, evidence/uncertainty, and a path to details. Include keyboard and low-vision constraints. State two tradeoffs and a validation plan.",
        "rubric": ["constraint coverage", "information hierarchy", "accessibility", "tradeoffs", "validation plan"],
    },
    {
        "id": "creative-open",
        "facet": "creative_search",
        "prompt": "For a constrained problem of your choice, generate five mechanism-distinct solutions. For each, state what structural assumption changes. Then choose one and improve it after identifying its main weakness.",
        "rubric": ["mechanism diversity", "appropriateness", "structural distinction", "evaluation", "improvement"],
    },
    {
        "id": "explain-open",
        "facet": "communication_explanation",
        "prompt": "Explain to a bright beginner why a green test suite does not prove every real-world failure mode is absent. Give one concrete example, one practical rule, and answer a changed-assumption follow-up.",
        "rubric": ["correctness", "clarity", "example quality", "actionable rule", "changed-assumption transfer"],
    },
]

FACET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "formalization_precision": ("formalize", "quantifier", "proof obligation", "define exactly", "specification"),
    "decomposition_systems": ("decompose", "architecture", "dependency", "boundary", "state ownership", "failure mode"),
    "error_detection": ("audit", "find the bug", "what is wrong", "red team", "counterexample", "failure"),
    "evidence_discipline": ("evidence", "citation", "source", "prior art", "verify this claim", "literature"),
    "causal_reasoning": ("causal", "confound", "intervention", "counterfactual", "mediator", "collider"),
    "quantitative_reasoning": ("calculate", "derive", "estimate", "probability", "statistics", "equation", "units"),
    "implementation_execution": ("run", "execute", "test", "compile", "debug", "implementation"),
    "planning_prioritization": ("prioritize", "roadmap", "what next", "critical path", "stop rule", "decision"),
    "metacognitive_calibration": ("confidence", "are you sure", "uncertain", "calibrate", "check yourself"),
    "transfer_adaptation": ("transfer", "generalize", "different context", "new representation", "adapt this"),
    "tool_selection": ("which tool", "verifier", "solver", "search or", "how do we verify"),
    "uncertainty_management": ("conflicting evidence", "unknown", "inconclusive", "scope split", "not found"),
    "design_reasoning": ("design", "ux", "interface", "accessibility", "layout"),
    "creative_search": ("brainstorm", "creative", "alternatives", "novel approach", "ideation"),
    "communication_explanation": ("explain", "teach", "rewrite", "presentation", "communicate"),
}


def infer_facets(text: str) -> list[str]:
    low = text.lower()
    return [facet for facet, keywords in FACET_KEYWORDS.items() if any(keyword in low for keyword in keywords)]


def mark_facet_relevance(profile: dict[str, Any], facets: list[str], source: str = "prompt") -> None:
    deep = fc.ensure_deep(profile)
    relevance = deep.setdefault("facet_relevance", {})
    for facet in facets:
        if facet not in fc.FACETS:
            continue
        row = relevance.setdefault(facet, {"mentions": 0, "sources": []})
        row["mentions"] = int(row.get("mentions", 0)) + 1
        if source not in row["sources"]:
            row["sources"].append(source)


def _options(rng: random.Random, correct: str, distractors: list[str]) -> list[str]:
    values = [correct]
    for value in distractors:
        if value not in values:
            values.append(value)
    rng.shuffle(values)
    return values


def build(profile: dict[str, Any], seed: int | None = None, mode: str = "standard") -> dict[str, Any]:
    if mode not in {"short", "standard"}:
        raise ValueError("mode must be short or standard")
    actual_seed = seed if seed is not None else random.SystemRandom().randrange(1, 2**31)
    rng = random.Random(actual_seed)
    per_facet: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for template in ITEMS:
        count = per_facet.get(template["facet"], 0)
        if mode == "short" and count >= 1:
            continue
        per_facet[template["facet"]] = count + 1
        selected.append(
            {
                "id": template["id"],
                "facet": template["facet"],
                "kind": template["kind"],
                "representation": template["representation"],
                "prompt": template["prompt"],
                "options": _options(rng, template["correct"], template["distractors"]),
                "confidence_prompt": "Confidence 0-100?",
            }
        )
    rng.shuffle(selected)
    open_probes = OPEN_PROBES if mode == "standard" else OPEN_PROBES[:2]
    facets = sorted({item["facet"] for item in selected})
    return {
        "schema": SCHEMA,
        "seed": actual_seed,
        "mode": mode,
        "profile_id": profile["id"],
        "purpose": "Second-stage cross-cutting calibration after the broad FOIL onboarding screen.",
        "limits": [
            "Not an IQ, personality, clinical, employment, or psychometrically calibrated test.",
            "Two micro-scenarios per facet create provisional routing evidence only.",
            "Open production tasks require rubric or independent review before they count as verified evidence.",
            "Questionnaire evidence cannot replace later real-work, transfer, and delayed-retest evidence.",
        ],
        "self_estimate_facets": facets,
        "objective_items": selected,
        "open_probes": open_probes,
        "response_schema": {
            "self_estimates": {facet: None for facet in facets},
            "objective": {
                item["id"]: {"choice": None, "confidence": None, "assistance": "none"}
                for item in selected
            },
            "open": {
                item["id"]: {"response": None, "assistance": "none", "reviewer": None}
                for item in open_probes
            },
        },
        "existing_maturity": fc.maturity(profile),
    }


def _template(item_id: str) -> dict[str, Any]:
    for item in ITEMS:
        if item["id"] == item_id:
            return item
    raise KeyError(item_id)


def answer(item: dict[str, Any]) -> str:
    return str(_template(str(item["id"]))["correct"])


def _normalize(item: dict[str, Any], value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int) and 0 <= value < len(item["options"]):
        return str(item["options"][value])
    text = str(value).strip()
    if len(text) == 1 and text.upper() in "ABCD":
        index = ord(text.upper()) - ord("A")
        if index < len(item["options"]):
            return str(item["options"][index])
    return text or None


def score(session: dict[str, Any], responses: dict[str, Any]) -> dict[str, Any]:
    rows: dict[str, list[dict[str, Any]]] = {}
    brier_terms: list[float] = []
    item_results: list[dict[str, Any]] = []
    for item in session["objective_items"]:
        raw = responses.get("objective", {}).get(item["id"], {})
        choice = _normalize(item, raw.get("choice"))
        if choice is None:
            continue
        correct = choice == answer(item)
        assistance = str(raw.get("assistance") or "none")
        confidence = None
        if raw.get("confidence") not in {None, ""}:
            try:
                confidence = max(0.0, min(100.0, float(raw["confidence"])))
            except (TypeError, ValueError):
                confidence = None
        if confidence is not None:
            probability = confidence / 100.0
            brier_terms.append((probability - (1.0 if correct else 0.0)) ** 2)
        result = {
            "item_id": item["id"],
            "facet": item["facet"],
            "kind": item["kind"],
            "representation": item["representation"],
            "correct": correct,
            "assistance": assistance,
            "confidence": confidence,
        }
        rows.setdefault(item["facet"], []).append(result)
        item_results.append(result)

    facet_evidence: dict[str, Any] = {}
    follow_up: list[dict[str, str]] = []
    for facet in session["self_estimate_facets"]:
        observations = rows.get(facet, [])
        independent = [row for row in observations if row["assistance"] in {"none", "independent"}]
        passed = sum(bool(row["correct"]) for row in independent)
        count = len(independent)
        if count < 2:
            classification = "INSUFFICIENT_EVIDENCE"
        elif passed == count:
            classification = "PROMISING_STRENGTH"
        elif passed == 0:
            classification = "POSSIBLE_GAP"
        else:
            classification = "UNCERTAIN"
        facet_evidence[facet] = {
            "independent_n": count,
            "independent_pass": passed,
            "classification": classification,
            "representations": sorted({row["representation"] for row in independent}),
            "note": "Provisional cross-cutting evidence; real-work and transfer evidence outrank this screen.",
        }
        if classification == "PROMISING_STRENGTH":
            action = "confirm with harder real-work or changed-context transfer"
        elif classification == "POSSIBLE_GAP":
            action = "run a discriminator before durable personalization"
        else:
            action = "collect a second changed-representation or real-work observation"
        follow_up.append({"facet": facet, "action": action})

    brier = sum(brier_terms) / len(brier_terms) if brier_terms else None
    return {
        "schema": SCHEMA,
        "seed": session["seed"],
        "mode": session["mode"],
        "profile_status": "PROVISIONAL_LAYER2",
        "facet_evidence": facet_evidence,
        "calibration": {"brier": brier, "n": len(brier_terms), "lower_is_better": True},
        "self_estimates": responses.get("self_estimates", {}),
        "open_status": {item["id"]: "NEEDS_RUBRIC_REVIEW" for item in session["open_probes"]},
        "item_results": item_results,
        "follow_up": follow_up,
        "ownership_ceiling": "Layer 2 micro-scenarios cannot certify OWNED, TRANSFERRED, or DEFENSIBLE capability.",
    }


def apply_to_profile(profile: dict[str, Any], report: dict[str, Any]) -> None:
    deep = fc.ensure_deep(profile)
    deep.setdefault("layer2_self_estimates", {}).update(
        {key: value for key, value in report.get("self_estimates", {}).items() if value is not None}
    )
    for result in report.get("item_results", []):
        probe_id = f"layer2:{report['seed']}:{result['item_id']}"
        if any(event.get("probe_id") == probe_id for event in deep.get("probe_history", [])):
            continue
        fc.record(
            profile,
            probe_id=probe_id,
            domain="cross_domain",
            facet=result["facet"],
            kind=result["kind"],
            outcome="pass" if result["correct"] else "fail",
            assistance=result["assistance"],
            verified=True,
            confidence=result.get("confidence"),
            representation=result["representation"],
            source="layer2_screen",
        )
    deep["layer2_last_report"] = {
        "seed": report["seed"],
        "mode": report["mode"],
        "profile_status": report["profile_status"],
        "open_status": report["open_status"],
    }


def _write(path: str, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOIL Layer 2 structured calibration")
    sub = parser.add_subparsers(dest="cmd", required=True)

    start = sub.add_parser("start")
    start.add_argument("--profile")
    start.add_argument("--seed", type=int)
    start.add_argument("--mode", choices=["short", "standard"], default="standard")
    start.add_argument("--out", default="foil_layer2.json")
    start.add_argument("--responses", default="foil_layer2_responses.json")

    score_cmd = sub.add_parser("score")
    score_cmd.add_argument("session")
    score_cmd.add_argument("responses")
    score_cmd.add_argument("--profile")
    score_cmd.add_argument("--out", default="foil_layer2_report.json")

    args = parser.parse_args(argv)
    profile = foil_profile.load(args.profile)
    if args.cmd == "start":
        session = build(profile, args.seed, args.mode)
        _write(args.out, session)
        _write(args.responses, session["response_schema"])
        print(f"created {args.out} and {args.responses}; seed={session['seed']}")
        return 0

    session = json.loads(Path(args.session).read_text(encoding="utf-8"))
    responses = json.loads(Path(args.responses).read_text(encoding="utf-8"))
    report = score(session, responses)
    apply_to_profile(profile, report)
    foil_profile.save(profile)
    _write(args.out, report)
    print(f"created {args.out} and updated profile {profile['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
