"""Portable intensive-solve engine used by Process Assurance SNAP mode.

The engine is bounded: independent proposals -> cross-review -> synthesis ->
verification-required verdict. It never claims SOLVED from agent agreement alone.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from openrouter_bot import OpenRouterError, ask

PROPOSE = "Generate one technically distinct solution to the target. State assumptions, mechanism, failure conditions, and a test. Do not claim success without verification."
CRITIQUE = "Attack the proposed solution. Find one concrete counterexample, unsupported premise, or verification gap. If it survives, say what external/mechanical verifier is still needed."
SYNTH = "Compare proposals and critiques. Return JSON with best_candidate, why, unresolved, verifier_needed, and status. status may be CANDIDATE or STALLED only; never SOLVED from LLM agreement."


def run(target: str, models: list[str], waves: int = 2) -> dict[str, Any]:
    if len(models) < 2:
        raise ValueError("SNAP requires at least two model entries for independent first passes")
    history: list[dict[str, Any]] = []
    context = target
    for wave in range(max(1, min(waves, 5))):
        proposals = [ask(PROPOSE, context, model=m, max_tokens=900)["text"] for m in models]
        critiques = []
        for i, proposal in enumerate(proposals):
            critic = models[(i + 1) % len(models)]
            critiques.append(ask(CRITIQUE, f"TARGET:\n{target}\n\nPROPOSAL:\n{proposal}", model=critic, max_tokens=700)["text"])
        bundle = json.dumps({"target": target, "proposals": proposals, "critiques": critiques})
        synthesis = ask(SYNTH, bundle, model=models[0], json_mode=True, max_tokens=800)["text"]
        try:
            parsed = json.loads(synthesis)
        except json.JSONDecodeError:
            parsed = {"status": "STALLED", "raw": synthesis}
        history.append({"wave": wave + 1, "proposals": proposals, "critiques": critiques, "synthesis": parsed})
        context = f"TARGET:\n{target}\n\nPREVIOUS SYNTHESIS:\n{json.dumps(parsed)}\nGenerate a different or improved candidate; do not recycle refuted mechanisms."
    final = history[-1]["synthesis"]
    return {"target": target, "models": models, "waves": history, "final": final, "claim_boundary": "SOLVED requires an external/mechanical verifier outside this engine."}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("target", nargs="?")
    p.add_argument("--target-file")
    p.add_argument("--model", action="append", dest="models", required=True)
    p.add_argument("--waves", type=int, default=2)
    p.add_argument("--out")
    args = p.parse_args(argv)
    target = Path(args.target_file).read_text(encoding="utf-8") if args.target_file else (args.target or "")
    if not target.strip():
        p.error("provide target text or --target-file")
    try:
        result = run(target, args.models, args.waves)
    except (OpenRouterError, ValueError) as exc:
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
