"""Adaptive FOIL onboarding questionnaire.

The assessment creates provisional routing evidence, not an IQ/personality,
clinical, diagnostic, or employment score. Objective answer keys are derived
from generative parameters and are not stored in the public session payload.
"""
from __future__ import annotations

import argparse
import json
import random
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

import foil_profile

SCHEMA = "egrt.foil-assessment.v1"
SCREEN_DOMAINS = [
    "quantitative_reasoning",
    "formal_reasoning",
    "probability_statistics",
    "causal_inference",
    "software_engineering",
    "systems_reliability",
    "research_evidence",
    "scientific_method",
    "security_privacy",
    "planning_decision_making",
]
STYLE_ITEMS = [
    ("mechanism_first", "I prefer understanding why a method works before memorizing steps."),
    ("examples_first", "Concrete examples help me more than abstract definitions at the beginning."),
    ("independent_first", "When stakes allow, I prefer making an independent attempt before seeing a worked solution."),
    ("verification_depth", "For important claims, I prefer explicit evidence and independent checks even when slower."),
    ("visual_spatial", "Diagrams or spatial representations often help me think."),
    ("option_breadth", "I prefer seeing several plausible approaches before committing to one."),
]
CONTEXT_QUESTIONS = [
    ("goal", "What do you most want FOIL to help you become better at?"),
    ("work_domains", "What fields or kinds of problems do you work on most?"),
    ("experience", "Briefly describe your practical experience in those areas."),
    ("tools", "What tools, languages, or workflows do you already use comfortably?"),
    ("constraints", "What constraints matter most: time, cost, compute, risk, accessibility, or something else?"),
    ("help_mode", "When stuck, do you prefer a hint, checklist, worked example, direct solution, or choice?"),
    ("learning_goal", "Do you prioritize fastest completion, independent learning, or a balance?"),
    ("other_domains", "List any other domains FOIL should know are relevant to you, separated by commas."),
]
OPEN_PROBES = [
    {
        "id": "design",
        "domain": "design_ux",
        "prompt": (
            "Design a compact phone-and-desktop research status panel that shows current state, one next action, "
            "evidence/uncertainty, and a path to details. Include keyboard and low-vision accessibility. "
            "Explain two tradeoffs."
        ),
        "rubric": ["constraint coverage", "information hierarchy", "accessibility", "tradeoffs", "validation plan"],
    },
    {
        "id": "creativity",
        "domain": "creativity_ideation",
        "prompt": (
            "List 10 common single nouns that are as semantically different from one another as possible. "
            "Avoid proper nouns, jargon, and near-synonyms."
        ),
        "rubric": ["validity", "uniqueness", "semantic breadth"],
    },
    {
        "id": "explanation",
        "domain": "teaching_explanation",
        "prompt": (
            "Explain to a bright beginner why checking an answer with the same method that produced it can miss errors. "
            "Use one concrete example and one practical rule."
        ),
        "rubric": ["correctness", "clarity", "example quality", "actionable rule"],
    },
]


def _choices(rng: random.Random, correct: str, distractors: list[str]) -> list[str]:
    values = [correct]
    for value in distractors:
        if value != correct and value not in values:
            values.append(value)
    fillers = ["Cannot be determined", "None of these", "0", "1"]
    for filler in fillers:
        if len(values) >= 4:
            break
        if filler != correct and filler not in values:
            values.append(filler)
    values = values[:4]
    rng.shuffle(values)
    return values


def _quantitative(rng: random.Random, index: int) -> dict[str, Any]:
    if index == 0:
        rate = rng.randint(3, 9)
        minutes = rng.randint(4, 10)
        target = rng.randint(6, 14)
        done = rate * minutes
        correct = str(rate * target)
        return {
            "kind": "rate",
            "prompt": f"A process completes {done} units in {minutes} minutes at a constant rate. How many in {target} minutes?",
            "options": _choices(rng, correct, [str(rate * (target + 1)), str(done + target), str(rate * (target - 1))]),
            "params": {"done": done, "minutes": minutes, "target": target},
        }
    coefficient = rng.randint(2, 8)
    x_value = rng.randint(-8, 12)
    offset = rng.randint(-10, 10)
    result = coefficient * x_value + offset
    sign = "+" if offset >= 0 else "-"
    return {
        "kind": "linear_equation",
        "prompt": f"Solve: {coefficient}x {sign} {abs(offset)} = {result}",
        "options": _choices(rng, str(x_value), [str(x_value + 1), str(x_value - 1), str(result - offset)]),
        "params": {"a": coefficient, "b": offset, "c": result},
    }


def _formal(_: random.Random, index: int) -> dict[str, Any]:
    if index == 0:
        return {
            "kind": "modus_tollens",
            "prompt": "If P implies Q and Q is false, what follows?",
            "options": ["P is false", "P is true", "Nothing about P follows", "Q is true"],
            "params": {},
        }
    return {
        "kind": "counterexample",
        "prompt": "A claim says every even integer greater than 2 is divisible by 4. What is the strongest response?",
        "options": ["Give 6 as a counterexample", "Give 8 as an example", "Ask for more samples", "The claim is true by definition"],
        "params": {},
    }


def _probability(rng: random.Random, index: int) -> dict[str, Any]:
    red = rng.randint(2, 7)
    blue = rng.randint(2, 7)
    total = red + blue
    if index == 0:
        fraction = Fraction(red, total)
        correct = f"{fraction.numerator}/{fraction.denominator}"
        return {
            "kind": "simple_probability",
            "prompt": f"A bag has {red} red and {blue} blue tokens. What is P(red)?",
            "options": _choices(rng, correct, [f"{blue}/{total}", f"{red}/{blue}", f"1/{total}"]),
            "params": {"red": red, "blue": blue},
        }
    fraction = Fraction(blue, total - 1)
    correct = f"{fraction.numerator}/{fraction.denominator}"
    return {
        "kind": "conditional_probability",
        "prompt": f"A bag has {red} red and {blue} blue tokens. A red token is removed. What is P(next is blue)?",
        "options": _choices(rng, correct, [f"{blue}/{total}", f"{red - 1}/{total - 1}", f"1/{total - 1}"]),
        "params": {"red": red, "blue": blue},
    }


def _causal(_: random.Random, index: int) -> dict[str, Any]:
    if index == 0:
        return {
            "kind": "confounding",
            "prompt": "People who carry umbrellas are observed to be near more traffic accidents on rainy days. What is the strongest first causal concern?",
            "options": ["Rain is a common cause of umbrella use and accident risk", "Umbrellas necessarily cause accidents", "Accidents cause umbrellas", "No causal analysis is possible"],
            "params": {},
        }
    return {
        "kind": "intervention_scope",
        "prompt": "A correlation between X and Y is strong. Which result would most directly strengthen a claim that changing X changes Y?",
        "options": ["A well-designed intervention on X with an appropriate comparison", "A larger correlation coefficient", "More citations mentioning X", "A prettier scatterplot"],
        "params": {},
    }


def _software(_: random.Random, index: int) -> dict[str, Any]:
    if index == 0:
        return {
            "kind": "complexity",
            "prompt": "A program loops over n records and, for each, loops over all n records again. Dominant complexity?",
            "options": ["O(1)", "O(n)", "O(n log n)", "O(n²)"],
            "params": {},
        }
    return {
        "kind": "false_green",
        "prompt": "Unit tests pass but production fails only under load. What is the strongest next check?",
        "options": ["Rerun the same unit tests", "Measure production-like load/resource behavior", "Rewrite docs", "Assume users are wrong"],
        "params": {},
    }


def _systems(_: random.Random, index: int) -> dict[str, Any]:
    if index == 0:
        return {
            "kind": "idempotency",
            "prompt": "A client may retry the same payment request after a timeout. What property most directly prevents duplicate charges?",
            "options": ["Idempotent request handling with a stable request key", "A faster font", "More log lines", "Random retry delays only"],
            "params": {},
        }
    return {
        "kind": "stale_state",
        "prompt": "A long-running worker loaded configuration at startup while another process may update it. What must be checked before assuming the worker sees the new value?",
        "options": ["The worker's reload/state-update semantics", "Whether the file extension changed", "The README title", "Nothing; all processes see changes automatically"],
        "params": {},
    }


def _evidence(_: random.Random, index: int) -> dict[str, Any]:
    if index == 0:
        return {
            "kind": "fresh_source",
            "prompt": "You need the current stable version of a software package. Which evidence is strongest?",
            "options": ["Model memory", "An old tutorial", "Current official release/documentation", "An undated forum comment"],
            "params": {},
        }
    return {
        "kind": "scope_entailment",
        "prompt": "A paper reports +20% on one benchmark, but a claim says +20% in all domains. What is warranted?",
        "options": ["The all-domain claim is proved", "Only the benchmark-specific result is supported", "The method fails elsewhere", "Citation count decides"],
        "params": {},
    }


def _science(_: random.Random, index: int) -> dict[str, Any]:
    if index == 0:
        return {
            "kind": "control_group",
            "prompt": "A treatment group improves after an intervention, but there is no control/comparison group. What is the central limitation?",
            "options": ["Improvement alone does not identify the intervention as the cause", "The sample must be exactly 100", "The outcome must be binary", "A comparison is unnecessary"],
            "params": {},
        }
    return {
        "kind": "preregistration",
        "prompt": "You will try many analyses and report the best-looking one. What most directly reduces selective-analysis bias?",
        "options": ["Pre-register the primary analysis/decision rule", "Increase font size", "Run fewer software tests", "Use more citations"],
        "params": {},
    }


def _security(_: random.Random, index: int) -> dict[str, Any]:
    if index == 0:
        return {
            "kind": "secret_storage",
            "prompt": "Where should an API key for a public repository normally live?",
            "options": ["Committed in source", "Environment/secret store outside tracked files", "README with the real key", "Issue comment"],
            "params": {},
        }
    return {
        "kind": "least_privilege",
        "prompt": "A tool only needs read access to one directory. What is the best default permission?",
        "options": ["Administrator access", "Read access only to the required scope", "Full disk access", "Disable authentication"],
        "params": {},
    }


def _planning(_: random.Random, index: int) -> dict[str, Any]:
    if index == 0:
        return {
            "kind": "critical_path",
            "prompt": "A project has many polish tasks but one unmeasured condition determines whether the approach works. What should be prioritized?",
            "options": ["Measure the load-bearing condition", "Polish everything equally", "Add branding", "Increase meeting count"],
            "params": {},
        }
    return {
        "kind": "reversibility",
        "prompt": "Two actions have similar expected value; one is cheap/reversible and one costly/irreversible. With high uncertainty, which is generally preferable first?",
        "options": ["The cheap reversible probe", "The costly irreversible action", "Choose randomly", "Avoid collecting evidence"],
        "params": {},
    }


GENERATORS: dict[str, Callable[[random.Random, int], dict[str, Any]]] = {
    "quantitative_reasoning": _quantitative,
    "formal_reasoning": _formal,
    "probability_statistics": _probability,
    "causal_inference": _causal,
    "software_engineering": _software,
    "systems_reliability": _systems,
    "research_evidence": _evidence,
    "scientific_method": _science,
    "security_privacy": _security,
    "planning_decision_making": _planning,
}
STATIC_ANSWERS = {
    "modus_tollens": "P is false",
    "counterexample": "Give 6 as a counterexample",
    "confounding": "Rain is a common cause of umbrella use and accident risk",
    "intervention_scope": "A well-designed intervention on X with an appropriate comparison",
    "complexity": "O(n²)",
    "false_green": "Measure production-like load/resource behavior",
    "idempotency": "Idempotent request handling with a stable request key",
    "stale_state": "The worker's reload/state-update semantics",
    "fresh_source": "Current official release/documentation",
    "scope_entailment": "Only the benchmark-specific result is supported",
    "control_group": "Improvement alone does not identify the intervention as the cause",
    "preregistration": "Pre-register the primary analysis/decision rule",
    "secret_storage": "Environment/secret store outside tracked files",
    "least_privilege": "Read access only to the required scope",
    "critical_path": "Measure the load-bearing condition",
    "reversibility": "The cheap reversible probe",
}


def answer(item: dict[str, Any]) -> str:
    kind = item["kind"]
    params = item.get("params", {})
    if kind == "rate":
        return str((params["done"] // params["minutes"]) * params["target"])
    if kind == "linear_equation":
        return str((params["c"] - params["b"]) // params["a"])
    if kind == "simple_probability":
        fraction = Fraction(params["red"], params["red"] + params["blue"])
        return f"{fraction.numerator}/{fraction.denominator}"
    if kind == "conditional_probability":
        fraction = Fraction(params["blue"], params["red"] + params["blue"] - 1)
        return f"{fraction.numerator}/{fraction.denominator}"
    return STATIC_ANSWERS[kind]


def _custom_domains(text: str | None) -> list[str]:
    if not text:
        return []
    raw = text.replace(";", ",").replace("\n", ",").split(",")
    parts = [foil_profile.normalize_domain(part) for part in raw if part.strip()]
    return list(dict.fromkeys(parts))


def build(
    seed: int | None = None,
    setup_text: str = "",
    extra_domains: list[str] | None = None,
) -> dict[str, Any]:
    actual_seed = seed if seed is not None else random.SystemRandom().randrange(1, 2**31)
    rng = random.Random(actual_seed)
    setup_relevant_domains = []
    for domain in [*foil_profile.infer_domains(setup_text), *(extra_domains or [])]:
        normalized = foil_profile.normalize_domain(domain)
        if normalized not in setup_relevant_domains:
            setup_relevant_domains.append(normalized)
    selected = list(SCREEN_DOMAINS)
    for domain in setup_relevant_domains:
        if domain not in selected:
            selected.append(domain)

    objective: list[dict[str, Any]] = []
    for domain in SCREEN_DOMAINS:
        for index in range(2):
            item = GENERATORS[domain](rng, index)
            item.update(
                {
                    "id": f"{domain}-{index + 1}",
                    "domain": domain,
                    "confidence_prompt": "Confidence 0-100?",
                }
            )
            objective.append(item)
    rng.shuffle(objective)

    return {
        "schema": SCHEMA,
        "seed": actual_seed,
        "setup_text": setup_text,
        "setup_relevant_domains": setup_relevant_domains,
        "selected_domains": selected,
        "limits": [
            "Experimental onboarding; not an IQ, clinical, diagnostic, or employment test.",
            "Initial classifications are provisional hypotheses.",
            "Self-report does not prove ability.",
            "Open design/creativity/explanation tasks need rubric or independent review.",
        ],
        "context_questions": [{"id": key, "prompt": prompt} for key, prompt in CONTEXT_QUESTIONS],
        "style_scale": {"min": 1, "max": 5},
        "style_items": [{"id": key, "prompt": prompt} for key, prompt in STYLE_ITEMS],
        "self_estimate_domains": selected,
        "objective_items": objective,
        "open_probes": OPEN_PROBES,
        "response_schema": {
            "context": {key: None for key, _ in CONTEXT_QUESTIONS},
            "style": {key: None for key, _ in STYLE_ITEMS},
            "self_estimates": {domain: None for domain in selected},
            "objective": {
                item["id"]: {"choice": None, "confidence": None, "assistance": "none"}
                for item in objective
            },
            "open": {
                item["id"]: {"response": None, "assistance": "none"}
                for item in OPEN_PROBES
            },
        },
    }


def normalize_choice(item: dict[str, Any], value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int) and 0 <= value < len(item["options"]):
        return item["options"][value]
    text = str(value).strip()
    if len(text) == 1 and text.upper() in "ABCD":
        index = ord(text.upper()) - ord("A")
        if index < len(item["options"]):
            return item["options"][index]
    return text or None


def score(session: dict[str, Any], responses: dict[str, Any]) -> dict[str, Any]:
    by_domain: dict[str, list[dict[str, Any]]] = {
        domain: [] for domain in session["selected_domains"]
    }
    brier_terms: list[float] = []

    for item in session["objective_items"]:
        raw = responses.get("objective", {}).get(item["id"], {})
        choice = normalize_choice(item, raw.get("choice"))
        if choice is None:
            continue
        correct = choice == answer(item)
        assistance = str(raw.get("assistance") or "none")
        confidence_value = raw.get("confidence")
        confidence: float | None = None
        if confidence_value not in (None, ""):
            try:
                confidence = max(0.0, min(100.0, float(confidence_value)))
            except (TypeError, ValueError):
                confidence = None
        if confidence is not None:
            probability = confidence / 100.0
            brier_terms.append((probability - (1.0 if correct else 0.0)) ** 2)
        by_domain[item["domain"]].append(
            {"correct": correct, "confidence": confidence, "assistance": assistance}
        )

    domain_evidence: dict[str, Any] = {}
    follow_up: list[dict[str, str]] = []
    for domain in session["selected_domains"]:
        rows = by_domain.get(domain, [])
        independent = [row for row in rows if row["assistance"] in {"none", "independent"}]
        correct = sum(bool(row["correct"]) for row in independent)
        count = len(independent)
        if count < 2:
            classification = "INSUFFICIENT_EVIDENCE"
        elif correct == count:
            classification = "PROMISING_STRENGTH"
        elif correct == 0:
            classification = "POSSIBLE_GAP"
        else:
            classification = "UNCERTAIN"
        domain_evidence[domain] = {
            "screened": domain in SCREEN_DOMAINS,
            "answered": len(rows),
            "independent_n": count,
            "independent_correct": correct,
            "classification": classification,
            "note": "Requires fresh follow-up before a stable competence label.",
        }
        if classification == "POSSIBLE_GAP":
            follow_up.append(
                {"domain": domain, "action": "fresh changed-representation no-help discriminator"}
            )
        elif classification == "UNCERTAIN":
            follow_up.append({"domain": domain, "action": "one independent discriminator"})
        elif classification == "PROMISING_STRENGTH":
            follow_up.append(
                {"domain": domain, "action": "harder transfer probe before relying on strength"}
            )

    brier = sum(brier_terms) / len(brier_terms) if brier_terms else None
    return {
        "schema": SCHEMA,
        "seed": session["seed"],
        "profile_status": "PROVISIONAL",
        "setup_relevant_domains": session.get("setup_relevant_domains", []),
        "domain_evidence": domain_evidence,
        "calibration": {"brier": brier, "n": len(brier_terms), "lower_is_better": True},
        "style": responses.get("style", {}),
        "self_estimates": responses.get("self_estimates", {}),
        "context": responses.get("context", {}),
        "open_status": {
            item["id"]: "NEEDS_RUBRIC_REVIEW" for item in session["open_probes"]
        },
        "follow_up": follow_up,
        "ownership_ceiling": "Onboarding cannot certify OWNED, TRANSFERRED, or DEFENSIBLE.",
    }


def apply_to_profile(name: str, report: dict[str, Any]) -> None:
    profile = foil_profile.load(name)

    for domain in report.get("setup_relevant_domains", []):
        foil_profile.ensure_domain(profile, domain, declared=True)
    for domain, value in report.get("self_estimates", {}).items():
        if value is not None:
            foil_profile.ensure_domain(profile, domain, declared=True)

    context = report.get("context", {})
    goal = context.get("goal")
    if goal:
        profile["goals"] = list(dict.fromkeys([*profile.get("goals", []), str(goal)]))
    relevant_text = " ".join(str(value) for value in context.values() if value)
    relevant_domains = [
        *foil_profile.infer_domains(relevant_text),
        *_custom_domains(context.get("other_domains")),
    ]
    for domain in relevant_domains:
        foil_profile.ensure_domain(profile, domain, declared=True)

    for domain, row in report.get("domain_evidence", {}).items():
        count = int(row.get("independent_n", 0))
        correct = int(row.get("independent_correct", 0))
        for index in range(count):
            foil_profile.observe(
                profile,
                domain,
                "correct" if index < correct else "incorrect",
                "none",
                source="assessment",
                representation=f"screen-{index + 1}",
            )

    for key, value in report.get("style", {}).items():
        if value is not None:
            profile.setdefault("preferences", {})[key] = value
    foil_profile.save(profile)


def _write(path: str, obj: Any) -> None:
    Path(path).write_text(
        json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    start = sub.add_parser("start")
    start.add_argument("--seed", type=int)
    start.add_argument("--setup-text", default="")
    start.add_argument("--domain", action="append", default=[])
    start.add_argument("--out", default="foil_assessment.json")
    start.add_argument("--responses", default="foil_responses.json")

    score_cmd = sub.add_parser("score")
    score_cmd.add_argument("session")
    score_cmd.add_argument("responses")
    score_cmd.add_argument("--out", default="foil_assessment_report.json")
    score_cmd.add_argument("--profile")

    args = parser.parse_args(argv)
    if args.cmd == "start":
        session = build(args.seed, args.setup_text, args.domain)
        _write(args.out, session)
        _write(args.responses, session["response_schema"])
        print(f"created {args.out} and {args.responses}; seed={session['seed']}")
        return 0

    session = json.loads(Path(args.session).read_text(encoding="utf-8"))
    responses = json.loads(Path(args.responses).read_text(encoding="utf-8"))
    report = score(session, responses)
    _write(args.out, report)
    if args.profile:
        apply_to_profile(args.profile, report)
    suffix = f" and updated profile {args.profile}" if args.profile else ""
    print(f"created {args.out}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
