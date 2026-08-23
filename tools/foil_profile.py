"""Persistent, privacy-preserving FOIL profiles.

Profiles are stored outside the repository by default. Raw prompts are never
stored by this tool; only explicit domain/evidence metadata is recorded.

Schema v2 (`egrt.foil-profile.v2`)
----------------------------------
v1 promoted ordinary, unverified usage outcomes straight into competence
classifications: two unchecked passes made a strength and two unchecked misses
made a gap. v2 makes the three conditions a competence claim actually depends on
explicit on every event -

* `verified`  - something other than the claimant checked the outcome;
* `assistance` - the attempt was made without material help (A0);
* `execution_owner` - the *person* made the attempt, not a tool or a pair.

and stores the derived `tier` those three imply. Classification is then delegated
to `foil_evidence.summarize`, the one estimator every FOIL layer shares, so the
profile, the onboarding screen, Layer 2, and deep calibration cannot disagree
about what a given pile of evidence means.

v1 profiles are migrated on `load()`, conservatively: only mechanically
key-scored onboarding sources are recoverable as verified, everything else
becomes non-load-bearing, and the aggregate counters are recomputed from the
observations rather than trusted.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import foil_evidence
from foil_assistance import ExecutionOwner, parse_assistance, parse_execution_owner
from private_io import ensure_private_dir, write_private_text

SCHEMA = "egrt.foil-profile.v2"
LEGACY_SCHEMAS = ("egrt.foil-profile.v1",)

#: Sources whose scoring is a mechanical answer key rather than a judgement.
#: They are verified, but they are a *screen*: admissible evidence that can
#: never on its own reach a load-bearing verdict.
SCREEN_SOURCES: dict[str, str] = {
    "assessment": "mechanical_assessment_key",
    "layer2_screen": "layer2_key",
}
CORRECT_OUTCOMES = {"correct", "success", "pass"}
INCORRECT_OUTCOMES = {"incorrect", "failure", "fail"}
CORE_DOMAINS = [
    "formal_reasoning",
    "quantitative_reasoning",
    "probability_statistics",
    "causal_inference",
    "research_evidence",
    "scientific_method",
    "software_engineering",
    "systems_reliability",
    "security_privacy",
    "data_ml",
    "design_ux",
    "creativity_ideation",
    "communication_writing",
    "teaching_explanation",
    "planning_decision_making",
]
OPTIONAL_DOMAINS = [
    "physics",
    "chemistry_materials",
    "biology_life_sciences",
    "economics_finance",
    "law_policy",
    "hardware_embedded",
    "product_management",
    "human_factors",
    "operations_logistics",
]
DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "formal_reasoning": ("proof", "theorem", "formal logic", "valid inference", "counterexample"),
    "quantitative_reasoning": ("algebra", "calculus", "equation", "quantitative", "arithmetic"),
    "probability_statistics": ("probability", "statistics", "statistical", "bayes", "confidence interval"),
    "causal_inference": ("causal", "causality", "confound", "intervention", "counterfactual", "dag"),
    "research_evidence": ("literature", "citation", "prior art", "research paper", "source evidence"),
    "scientific_method": ("experiment", "hypothesis", "control group", "preregister", "replication"),
    "software_engineering": ("software", "programming", "python", "javascript", "typescript", "api", "github"),
    "systems_reliability": ("distributed", "database", "concurrency", "network", "reliability", "fault tolerance"),
    "security_privacy": ("security", "privacy", "vulnerability", "authentication", "authorization", "encryption"),
    "data_ml": ("machine learning", "data science", "model training", "neural", "embedding", "classifier"),
    "design_ux": ("user interface", "ui design", "ux", "accessibility", "interaction design", "wireframe"),
    "creativity_ideation": ("creative", "creativity", "brainstorm", "ideation", "fiction", "art concept"),
    "communication_writing": ("writing", "rewrite", "documentation", "presentation", "technical communication"),
    "teaching_explanation": ("teach", "tutor", "explain to me", "learning", "lesson"),
    "planning_decision_making": ("roadmap", "prioritize", "decision", "project plan", "strategy"),
    "physics": ("physics", "quantum", "relativity", "electromagnetism", "thermodynamics"),
    "chemistry_materials": ("chemistry", "materials science", "molecule", "catalyst", "polymer", "electrochemistry"),
    "biology_life_sciences": ("biology", "genomics", "protein", "cell biology", "ecology", "biochemistry"),
    "economics_finance": ("economics", "financial model", "valuation", "investment", "macroeconomic", "portfolio return"),
    "law_policy": ("legal", "law", "regulation", "statute", "case law", "public policy"),
    "hardware_embedded": ("hardware", "circuit", "embedded", "microcontroller", "fpga", "electronics"),
    "product_management": ("product management", "product strategy", "user research", "product requirements"),
    "human_factors": ("human factors", "ergonomics", "cognitive load", "usability study"),
    "operations_logistics": ("operations research", "logistics", "supply chain", "scheduling", "routing problem"),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def profile_home() -> Path:
    override = os.environ.get("EGR_FOIL_PROFILE_DIR")
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt" and os.environ.get("APPDATA"):
        root = Path(os.environ["APPDATA"]) / "egrt" / "foil"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        root = Path(xdg).expanduser() if xdg else Path.home() / ".config"
        root = root / "egrt" / "foil"
    root = ensure_private_dir(root)
    ensure_private_dir(root / "profiles")
    return root


def slug(value: str) -> str:
    out = re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower()).strip("-")
    if not out:
        raise ValueError("profile name must contain at least one letter or digit")
    return out


def normalize_domain(value: str) -> str:
    return slug(value).replace("-", "_")


def infer_domains(text: str) -> list[str]:
    low = text.lower()
    return [domain for domain, keywords in DOMAIN_KEYWORDS.items() if any(keyword in low for keyword in keywords)]


def path_for(name: str) -> Path:
    return profile_home() / "profiles" / f"{slug(name)}.json"


def new_profile(name: str, display_name: str | None = None) -> dict[str, Any]:
    timestamp = now()
    return {
        "schema": SCHEMA,
        "id": slug(name),
        "display_name": display_name or name,
        "created_at": timestamp,
        "updated_at": timestamp,
        "profile_status": "PROVISIONAL",
        "goals": [],
        "preferences": {},
        "domains": {},
        "calibration": {"observations": 0, "brier_terms": []},
        "events": [],
        "privacy": {"raw_prompts_stored": False},
    }


def save(profile: dict[str, Any]) -> Path:
    profile["updated_at"] = now()
    path = path_for(str(profile["id"]))
    write_private_text(path, json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    return path


def migrate_v1_to_v2(profile: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Bring a v1 profile onto the v2 verification/ownership contract.

    Conservative by construction. Only mechanically key-scored onboarding
    sources are recoverable as verified, because only those have an objective
    answer key; every other legacy observation becomes UNVERIFIED and therefore
    non-load-bearing. Aggregate counters are recomputed from the observations
    rather than trusted, since the v1 counters were produced by the rule this
    migration exists to retire. The original rows are kept.
    """
    origin = profile.get("schema")
    changed = origin != SCHEMA
    for row in profile.setdefault("domains", {}).values():
        independent_correct = independent_incorrect = 0
        assisted_correct = assisted_incorrect = 0
        for event in row.setdefault("observations", []):
            source = str(event.get("source") or "")
            if "verified" in event:
                verified = bool(event.get("verified"))
                verifier = event.get("verifier")
            elif source in SCREEN_SOURCES:
                verified, verifier = True, SCREEN_SOURCES[source]
            else:
                verified, verifier = False, None
            owner = event.get("execution_owner") or ExecutionOwner.USER.value
            tier = derive_tier(
                source=source,
                verified=verified,
                assistance=event.get("assistance"),
                execution_owner=owner,
            )
            for key, value in (
                ("verified", verified),
                ("verifier", verifier),
                ("execution_owner", owner),
                ("tier", tier),
            ):
                # `key not in event` matters: a legacy row has no "verifier" at
                # all, and the derived value is often None, so an equality-only
                # check would leave the key absent and produce migrated events
                # with a different shape from freshly written ones.
                if key not in event or event[key] != value:
                    event[key] = value
                    changed = True

            outcome = str(event.get("outcome") or "")
            admissible = (
                verified
                and is_independent(event.get("assistance"))
                and is_user_owned(owner)
            )
            if admissible and outcome in CORRECT_OUTCOMES:
                independent_correct += 1
            elif admissible and outcome in INCORRECT_OUTCOMES:
                independent_incorrect += 1
            elif outcome in CORRECT_OUTCOMES:
                assisted_correct += 1
            elif outcome in INCORRECT_OUTCOMES:
                assisted_incorrect += 1

        desired = {
            "independent_correct": independent_correct,
            "independent_incorrect": independent_incorrect,
            "assisted_correct": assisted_correct,
            "assisted_incorrect": assisted_incorrect,
            "classification": classify(row),
        }
        for key, value in desired.items():
            if row.get(key) != value:
                row[key] = value
                changed = True

    if changed:
        profile.setdefault("migrations", []).append(
            {
                "time": now(),
                "kind": "foil-profile-v1-to-v2-verification-gate",
                "migrated_from": profile.get("schema"),
                "rule": (
                    "mechanically key-scored onboarding sources become verified SCREEN "
                    "evidence; every other legacy observation is UNVERIFIED and "
                    "non-load-bearing; counters and classification are recomputed from "
                    "the observations, not inherited"
                ),
            }
        )
    # Provenance records where the profile *came from*. Re-running the migration
    # on an already-migrated profile must not overwrite that with "v2", which
    # would erase the only record that it was ever a v1 profile.
    if origin != SCHEMA:
        profile["migrated_from"] = origin
    profile["schema"] = SCHEMA
    return profile, changed


def load(name: str | None = None) -> dict[str, Any]:
    target = name or active_name()
    if not target:
        raise FileNotFoundError("no active FOIL profile")
    profile = json.loads(path_for(target).read_text(encoding="utf-8"))
    if profile.get("schema") != SCHEMA:
        profile, _ = migrate_v1_to_v2(profile)
    return profile


def activate(name: str) -> None:
    if not path_for(name).exists():
        raise FileNotFoundError(f"profile does not exist: {name}")
    write_private_text(profile_home() / "active_profile", slug(name) + "\n")


def active_name() -> str | None:
    path = profile_home() / "active_profile"
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def bootstrap_active() -> dict[str, Any]:
    active = active_name()
    if active:
        return load(active)
    profile = new_profile("default", "Local default")
    save(profile)
    activate("default")
    return profile


def ensure_domain(profile: dict[str, Any], domain: str, *, declared: bool = False) -> dict[str, Any]:
    name = normalize_domain(domain)
    domains = profile.setdefault("domains", {})
    row = domains.setdefault(
        name,
        {
            "state": "DECLARED_RELEVANT" if declared else "CANDIDATE",
            "declared": bool(declared),
            "relevance_mentions": 0,
            "observations": [],
            "independent_correct": 0,
            "independent_incorrect": 0,
            "assisted_correct": 0,
            "assisted_incorrect": 0,
            "last_seen": None,
            "last_relevant": None,
        },
    )
    if declared:
        row["declared"] = True
        if row.get("state") == "CANDIDATE":
            row["state"] = "DECLARED_RELEVANT"
    return row


def mark_relevance(profile: dict[str, Any], domains: list[str], *, source: str = "prompt") -> None:
    for domain in domains:
        row = ensure_domain(profile, domain)
        row["relevance_mentions"] = int(row.get("relevance_mentions", 0)) + 1
        row["last_relevant"] = now()
        if row.get("state") == "CANDIDATE":
            row["state"] = "ACTIVE_RELEVANT"
        profile.setdefault("events", []).append(
            {"time": now(), "domain": normalize_domain(domain), "kind": "relevance", "source": source}
        )
    profile["events"] = profile.get("events", [])[-200:]


def is_independent(assistance: Any) -> bool:
    """A0 test that fails closed.

    An unparseable assistance label is treated as *assisted*, never as
    independent: the conservative direction is to withhold a competence claim,
    and `foil_assistance.parse_assistance` already rejects unknown labels at
    every write path that can afford to raise.
    """
    try:
        return parse_assistance(assistance).is_independent
    except (ValueError, TypeError):
        return False


def is_user_owned(execution_owner: Any) -> bool:
    """USER-ownership test that fails closed, for the same reason."""
    try:
        return parse_execution_owner(execution_owner) is ExecutionOwner.USER
    except (ValueError, TypeError):
        return False


def derive_tier(
    *,
    source: str | None,
    verified: bool,
    assistance: Any,
    execution_owner: Any,
) -> str:
    """Evidence tier for one observation.

    Order matters. A mechanically key-scored screen is classified as SCREEN
    before anything else, because it is verified and independent yet still must
    not be able to manufacture a load-bearing verdict.
    """
    if str(source or "") in SCREEN_SOURCES:
        return foil_evidence.EvidenceTier.SCREEN.value
    if not verified:
        return foil_evidence.EvidenceTier.UNVERIFIED.value
    if not is_independent(assistance) or not is_user_owned(execution_owner):
        return foil_evidence.EvidenceTier.ASSISTED.value
    return foil_evidence.EvidenceTier.REAL_WORK.value


def _legacy_tier(event: dict[str, Any]) -> str:
    """Tier for a row written before the field existed."""
    if str(event.get("source") or "") in SCREEN_SOURCES:
        return foil_evidence.EvidenceTier.SCREEN.value
    return foil_evidence.EvidenceTier.UNVERIFIED.value


def _event_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def observations_for(row: dict[str, Any]) -> list[foil_evidence.Observation]:
    """Adapt stored events into the shared estimator's input type."""
    out: list[foil_evidence.Observation] = []
    for event in row.get("observations", []):
        outcome = str(event.get("outcome") or "")
        if outcome in CORRECT_OUTCOMES:
            correct = True
        elif outcome in INCORRECT_OUTCOMES:
            correct = False
        else:
            continue  # neither a pass nor a miss carries no competence signal
        tier_value = str(event.get("tier") or "") or _legacy_tier(event)
        try:
            tier = foil_evidence.EvidenceTier(tier_value)
        except ValueError:
            tier = foil_evidence.EvidenceTier.UNVERIFIED
        out.append(
            foil_evidence.Observation(
                correct=correct,
                tier=tier,
                time=_event_time(event.get("time")),
                representation=event.get("representation"),
                verifier=event.get("verifier"),
            )
        )
    return out


def classify(row: dict[str, Any]) -> str:
    """Competence classification for one domain row.

    Delegates to `foil_evidence.summarize` rather than counting, so this layer
    uses the same estimator, tiers, and recency decay as the onboarding screen,
    Layer 2, and deep calibration. The returned strings are unchanged.
    """
    return foil_evidence.summarize(observations_for(row)).classification.value


def observe(
    profile: dict[str, Any],
    domain: str,
    outcome: str,
    assistance: str,
    *,
    verified: bool = False,
    verifier: str | None = None,
    execution_owner: str = ExecutionOwner.USER.value,
    confidence: float | None = None,
    source: str = "usage",
    representation: str | None = None,
    note: str | None = None,
) -> None:
    """Record one performance observation.

    `verified` defaults to False on purpose. An unverified outcome is still
    worth recording as context, but it carries zero weight in the estimator, so
    ordinary usage can no longer accumulate into a competence claim without
    something having actually checked it.
    """
    name = normalize_domain(domain)
    row = ensure_domain(profile, name)
    tier = derive_tier(
        source=source,
        verified=bool(verified),
        assistance=assistance,
        execution_owner=execution_owner,
    )
    if not verifier and tier == foil_evidence.EvidenceTier.SCREEN.value:
        verifier = SCREEN_SOURCES[str(source)]
    event: dict[str, Any] = {
        "time": now(),
        "domain": name,
        "kind": "performance",
        "outcome": outcome,
        "assistance": assistance,
        "verified": bool(verified),
        "verifier": verifier,
        "execution_owner": str(execution_owner),
        "tier": tier,
        "source": source,
        "representation": representation,
        "confidence": confidence,
    }
    if note:
        event["note"] = note[:400]
    row["observations"].append(event)
    row["observations"] = row["observations"][-40:]
    row["last_seen"] = event["time"]

    correct = outcome in CORRECT_OUTCOMES
    incorrect = outcome in INCORRECT_OUTCOMES
    admissible = (
        bool(verified)
        and is_independent(assistance)
        and is_user_owned(execution_owner)
    )
    if admissible and correct:
        row["independent_correct"] += 1
    elif admissible and incorrect:
        row["independent_incorrect"] += 1
    elif correct:
        row["assisted_correct"] = int(row.get("assisted_correct", 0)) + 1
    elif incorrect:
        row["assisted_incorrect"] = int(row.get("assisted_incorrect", 0)) + 1

    row["classification"] = classify(row)
    if len(row["observations"]) >= 2 and row.get("state") in {"CANDIDATE", "ACTIVE_RELEVANT"}:
        row["state"] = "ACTIVE"

    if confidence is not None and (correct or incorrect):
        probability = max(0.0, min(100.0, float(confidence))) / 100.0
        term = (probability - (1.0 if correct else 0.0)) ** 2
        calibration = profile.setdefault("calibration", {"observations": 0, "brier_terms": []})
        calibration["observations"] = int(calibration.get("observations", 0)) + 1
        calibration.setdefault("brier_terms", []).append(term)
        calibration["brier_terms"] = calibration["brier_terms"][-100:]
        calibration["brier"] = sum(calibration["brier_terms"]) / len(calibration["brier_terms"])

    profile.setdefault("events", []).append(event)
    profile["events"] = profile["events"][-200:]


def compact_context(profile: dict[str, Any]) -> str:
    domain_summaries: list[str] = []
    for name, row in sorted(profile.get("domains", {}).items()):
        classification = row.get("classification") or classify(row)
        relevant = bool(row.get("declared")) or int(row.get("relevance_mentions", 0)) > 0
        if relevant or classification != "INSUFFICIENT_EVIDENCE":
            domain_summaries.append(f"{name}:{classification};state={row.get('state', 'CANDIDATE')}")
    goals = "; ".join(str(item) for item in profile.get("goals", [])[:3]) or "none recorded"
    preferences = ", ".join(
        f"{key}={value}"
        for key, value in sorted(profile.get("preferences", {}).items())
        if value is not None
    ) or "none recorded"
    domains = ", ".join(domain_summaries) or "none"
    return (
        f"<FOIL_PROFILE id={profile['id']!r} status={profile.get('profile_status', 'PROVISIONAL')!r}>\n"
        f"goals: {goals}\npreferences: {preferences}\ndomain evidence: {domains}\n"
        "Treat these as provisional priors. Domain relevance is not competence. "
        "Current task evidence overrides stale profile evidence; one miss never creates a stable weakness.\n"
        "</FOIL_PROFILE>"
    )


def parse_kv(text: str) -> tuple[str, str]:
    if "=" not in text:
        raise ValueError("expected key=value")
    key, value = text.split("=", 1)
    return key, value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init")
    init.add_argument("name")
    init.add_argument("--display-name")
    init.add_argument("--activate", action="store_true")

    sub.add_parser("list")

    activate_cmd = sub.add_parser("activate")
    activate_cmd.add_argument("name")

    show = sub.add_parser("show")
    show.add_argument("name", nargs="?")

    context = sub.add_parser("context")
    context.add_argument("name", nargs="?")
    context.add_argument("--hook", action="store_true")

    set_cmd = sub.add_parser("set")
    set_cmd.add_argument("name")
    set_cmd.add_argument("--goal", action="append")
    set_cmd.add_argument("--preference", action="append", default=[])
    set_cmd.add_argument("--domain", action="append", default=[])

    observe_cmd = sub.add_parser("observe")
    observe_cmd.add_argument("name")
    observe_cmd.add_argument("--domain", required=True)
    observe_cmd.add_argument("--outcome", required=True)
    observe_cmd.add_argument("--assistance", default="none")
    observe_cmd.add_argument("--verified", action="store_true")
    observe_cmd.add_argument("--verifier")
    observe_cmd.add_argument("--execution-owner", default=ExecutionOwner.USER.value,
                             choices=[owner.value for owner in ExecutionOwner])
    observe_cmd.add_argument("--confidence", type=float)
    observe_cmd.add_argument("--source", default="usage")
    observe_cmd.add_argument("--representation")
    observe_cmd.add_argument("--note")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "init":
            profile = new_profile(args.name, args.display_name)
            path = save(profile)
            if args.activate:
                activate(args.name)
            print(path)
            return 0
        if args.cmd == "list":
            active = active_name()
            for file in sorted((profile_home() / "profiles").glob("*.json")):
                print(("* " if file.stem == active else "  ") + file.stem)
            return 0
        if args.cmd == "activate":
            activate(args.name)
            return 0
        if args.cmd == "show":
            print(json.dumps(load(args.name), indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "context":
            profile = bootstrap_active() if args.hook else load(args.name)
            print(compact_context(profile))
            return 0

        profile = load(args.name)
        if args.cmd == "set":
            if args.goal:
                profile["goals"] = list(dict.fromkeys([*profile.get("goals", []), *args.goal]))
            for item in args.preference:
                key, value = parse_kv(item)
                profile.setdefault("preferences", {})[key] = value
            for domain in args.domain:
                ensure_domain(profile, domain, declared=True)
            save(profile)
            return 0
        if args.cmd == "observe":
            observe(
                profile,
                args.domain,
                args.outcome,
                args.assistance,
                verified=args.verified,
                verifier=args.verifier,
                execution_owner=args.execution_owner,
                confidence=args.confidence,
                source=args.source,
                representation=args.representation,
                note=args.note,
            )
            save(profile)
            return 0
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        if getattr(args, "cmd", None) == "context" and getattr(args, "hook", False):
            return 0
        print(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
