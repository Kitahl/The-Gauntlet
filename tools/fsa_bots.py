"""Portable independent red-team panel for Process Assurance.

This is deliberately smaller than the original project-specific implementation:
it keeps independent first passes, cross-critique, canary support, and a final
synthesis while removing private imports, keystores, project paths, and names.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from openrouter_bot import OpenRouterError, ask

REDTEAM_SYSTEM = """You are an independent technical red-team reviewer. Attack the candidate, not the person. Identify concrete failure modes, unsupported assumptions, hidden scope changes, and the cheapest discriminating test. Do not invent facts. If evidence is missing, say UNKNOWN."""
CROSS_SYSTEM = """You are cross-auditing another review. Find what it got wrong or missed. Preserve only attacks that survive the supplied candidate and evidence. Do not vote or average."""
SYNTH_SYSTEM = """Synthesize independent technical reviews. Return JSON with verdict (KILL|AMEND|SURVIVES_TO_GATE|UNKNOWN), decisive_reason, surviving_attacks, cheapest_test, unresolved. Agreement is not evidence; use the candidate/evidence."""
DEFAULT_CANARY = "Candidate claims a renamed ordinary cache invalidation strategy is a novel synchronization algorithm."


def run_review(brief: str, *, model_a: str, model_b: str, canary: str | None = None) -> dict[str, Any]:
    canary = canary if canary is not None else DEFAULT_CANARY
    canary_a = ask(REDTEAM_SYSTEM, canary, model=model_a, max_tokens=350)["text"]
    canary_b = ask(REDTEAM_SYSTEM, canary, model=model_b, max_tokens=350)["text"]
    p1a = ask(REDTEAM_SYSTEM, brief, model=model_a, max_tokens=900)["text"]
    p1b = ask(REDTEAM_SYSTEM, brief, model=model_b, max_tokens=900)["text"]
    cross_a = ask(CROSS_SYSTEM, f"CANDIDATE:\n{brief}\n\nOTHER REVIEW:\n{p1b}", model=model_a, max_tokens=700)["text"]
    cross_b = ask(CROSS_SYSTEM, f"CANDIDATE:\n{brief}\n\nOTHER REVIEW:\n{p1a}", model=model_b, max_tokens=700)["text"]
    synth_input = json.dumps({"candidate": brief, "review_a": p1a, "review_b": p1b, "cross_a": cross_a, "cross_b": cross_b})
    final = ask(SYNTH_SYSTEM, synth_input, model=model_a, json_mode=True, max_tokens=900)["text"]
    try:
        verdict = json.loads(final)
    except json.JSONDecodeError:
        verdict = {"verdict": "UNKNOWN", "raw": final}
    return {
        "canary": {"a": canary_a, "b": canary_b},
        "first_pass": {"a": p1a, "b": p1b},
        "cross_audit": {"a": cross_a, "b": cross_b},
        "final": verdict,
        "models": {"a": model_a, "b": model_b},
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--brief-file", required=True)
    p.add_argument("--out")
    p.add_argument("--model-a", required=True)
    p.add_argument("--model-b", required=True)
    args = p.parse_args(argv)
    brief = Path(args.brief_file).read_text(encoding="utf-8")
    try:
        result = run_review(brief, model_a=args.model_a, model_b=args.model_b)
    except OpenRouterError as exc:
        print(str(exc))
        return 2
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
