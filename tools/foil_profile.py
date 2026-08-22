"""Persistent, privacy-preserving FOIL profiles.

Profiles are stored outside the repository by default. Raw prompts are never
stored by this tool; only explicit domain/evidence metadata is recorded.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "egrt.foil-profile.v1"
CORE_DOMAINS = [
    "formal_reasoning", "quantitative_reasoning", "probability_statistics",
    "causal_inference", "research_evidence", "scientific_method",
    "software_engineering", "systems_reliability", "security_privacy",
    "data_ml", "design_ux", "creativity_ideation", "communication_writing",
    "teaching_explanation", "planning_decision_making",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def profile_home() -> Path:
    override = os.environ.get("EGR_FOIL_PROFILE_DIR")
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt" and os.environ.get("APPDATA"):
        root = Path(os.environ["APPDATA"]) / "egrt" / "foil"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "egrt" / "foil"
    (root / "profiles").mkdir(parents=True, exist_ok=True)
    return root


def slug(value: str) -> str:
    out = re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower()).strip("-")
    if not out:
        raise ValueError("profile name must contain at least one letter or digit")
    return out


def path_for(name: str) -> Path:
    return profile_home() / "profiles" / f"{slug(name)}.json"


def new_profile(name: str, display_name: str | None = None) -> dict[str, Any]:
    ts = now()
    return {
        "schema": SCHEMA,
        "id": slug(name),
        "display_name": display_name or name,
        "created_at": ts,
        "updated_at": ts,
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
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load(name: str | None = None) -> dict[str, Any]:
    if name is None:
        name = active_name()
    if not name:
        raise FileNotFoundError("no active FOIL profile")
    path = path_for(name)
    return json.loads(path.read_text(encoding="utf-8"))


def activate(name: str) -> None:
    if not path_for(name).exists():
        raise FileNotFoundError(f"profile does not exist: {name}")
    (profile_home() / "active_profile").write_text(slug(name) + "\n", encoding="utf-8")


def active_name() -> str | None:
    p = profile_home() / "active_profile"
    if not p.exists():
        return None
    value = p.read_text(encoding="utf-8").strip()
    return value or None


def ensure_domain(profile: dict[str, Any], domain: str, *, declared: bool = False) -> dict[str, Any]:
    domain = slug(domain).replace("-", "_")
    row = profile.setdefault("domains", {}).setdefault(domain, {
        "state": "DECLARED_RELEVANT" if declared else "CANDIDATE",
        "declared": bool(declared),
        "observations": [],
        "independent_correct": 0,
        "independent_incorrect": 0,
        "assisted_correct": 0,
        "last_seen": None,
    })
    if declared:
        row["declared"] = True
        if row.get("state") == "CANDIDATE":
            row["state"] = "DECLARED_RELEVANT"
    return row


def classify(row: dict[str, Any]) -> str:
    n = len(row.get("observations", []))
    independent = int(row.get("independent_correct", 0)) + int(row.get("independent_incorrect", 0))
    if independent < 2:
        return "INSUFFICIENT_EVIDENCE" if n < 2 else "UNCERTAIN"
    c = int(row.get("independent_correct", 0))
    w = int(row.get("independent_incorrect", 0))
    if c >= 2 and w == 0:
        return "PROMISING_STRENGTH"
    if w >= 2 and c == 0:
        return "POSSIBLE_GAP"
    return "UNCERTAIN"


def observe(
    profile: dict[str, Any], domain: str, outcome: str, assistance: str,
    *, confidence: float | None = None, source: str = "usage", representation: str | None = None,
    note: str | None = None,
) -> None:
    row = ensure_domain(profile, domain)
    event = {
        "time": now(), "domain": domain, "outcome": outcome, "assistance": assistance,
        "source": source, "representation": representation, "confidence": confidence,
    }
    if note:
        event["note"] = note[:400]
    row["observations"].append(event)
    row["observations"] = row["observations"][-40:]
    row["last_seen"] = event["time"]
    independent = assistance in {"none", "independent"}
    correct = outcome in {"correct", "success", "pass"}
    incorrect = outcome in {"incorrect", "failure", "fail"}
    if independent and correct:
        row["independent_correct"] += 1
    elif independent and incorrect:
        row["independent_incorrect"] += 1
    elif correct:
        row["assisted_correct"] += 1
    row["classification"] = classify(row)
    if len(row["observations"]) >= 2 and row.get("state") == "CANDIDATE":
        row["state"] = "ACTIVE"
    if confidence is not None and (correct or incorrect):
        q = max(0.0, min(100.0, float(confidence))) / 100.0
        term = (q - (1.0 if correct else 0.0)) ** 2
        cal = profile.setdefault("calibration", {"observations": 0, "brier_terms": []})
        cal["observations"] = int(cal.get("observations", 0)) + 1
        cal.setdefault("brier_terms", []).append(term)
        cal["brier_terms"] = cal["brier_terms"][-100:]
        cal["brier"] = sum(cal["brier_terms"]) / len(cal["brier_terms"])
    profile.setdefault("events", []).append(event)
    profile["events"] = profile["events"][-200:]


def compact_context(profile: dict[str, Any]) -> str:
    domains = []
    for name, row in sorted(profile.get("domains", {}).items()):
        classification = row.get("classification") or classify(row)
        if row.get("declared") or classification != "INSUFFICIENT_EVIDENCE":
            domains.append(f"{name}:{classification}")
    goals = "; ".join(str(x) for x in profile.get("goals", [])[:3]) or "none recorded"
    prefs = ", ".join(f"{k}={v}" for k, v in sorted(profile.get("preferences", {}).items()) if v is not None) or "none recorded"
    return (
        f"<FOIL_PROFILE id={profile['id']!r} status={profile.get('profile_status','PROVISIONAL')!r}>\n"
        f"goals: {goals}\npreferences: {prefs}\ndomain evidence: {', '.join(domains) or 'none'}\n"
        "Treat these as provisional priors. Current task evidence overrides them; one miss never creates a stable weakness.\n"
        "</FOIL_PROFILE>"
    )


def parse_kv(text: str) -> tuple[str, str]:
    if "=" not in text:
        raise ValueError("expected key=value")
    return tuple(text.split("=", 1))  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("name"); s.add_argument("--display-name"); s.add_argument("--activate", action="store_true")
    sub.add_parser("list")
    a = sub.add_parser("activate"); a.add_argument("name")
    sh = sub.add_parser("show"); sh.add_argument("name", nargs="?")
    c = sub.add_parser("context"); c.add_argument("name", nargs="?"); c.add_argument("--hook", action="store_true")
    se = sub.add_parser("set"); se.add_argument("name"); se.add_argument("--goal", action="append"); se.add_argument("--preference", action="append", default=[]); se.add_argument("--domain", action="append", default=[])
    o = sub.add_parser("observe"); o.add_argument("name"); o.add_argument("--domain", required=True); o.add_argument("--outcome", required=True); o.add_argument("--assistance", default="none"); o.add_argument("--confidence", type=float); o.add_argument("--source", default="usage"); o.add_argument("--representation"); o.add_argument("--note")
    args = p.parse_args(argv)
    try:
        if args.cmd == "init":
            pr = new_profile(args.name, args.display_name); path = save(pr)
            if args.activate: activate(args.name)
            print(path); return 0
        if args.cmd == "list":
            active = active_name()
            for f in sorted((profile_home() / "profiles").glob("*.json")):
                print(("* " if f.stem == active else "  ") + f.stem)
            return 0
        if args.cmd == "activate": activate(args.name); return 0
        if args.cmd == "show": print(json.dumps(load(args.name), indent=2, ensure_ascii=False)); return 0
        if args.cmd == "context": print(compact_context(load(args.name))); return 0
        pr = load(args.name)
        if args.cmd == "set":
            if args.goal:
                pr["goals"] = list(dict.fromkeys([*pr.get("goals", []), *args.goal]))
            for item in args.preference:
                k, v = parse_kv(item); pr.setdefault("preferences", {})[k] = v
            for domain in args.domain:
                ensure_domain(pr, domain, declared=True)
            save(pr); return 0
        if args.cmd == "observe":
            observe(pr, args.domain, args.outcome, args.assistance, confidence=args.confidence, source=args.source, representation=args.representation, note=args.note)
            save(pr); return 0
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        if getattr(args, "cmd", None) == "context" and getattr(args, "hook", False):
            return 0
        print(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
