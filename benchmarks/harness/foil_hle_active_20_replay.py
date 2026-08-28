"""Deterministic cost/damage replays over the sealed HLE active pilot.

These scenarios do not create new efficacy evidence.  They expose what the
recorded rows would have done under safer publication laws or impossible
post-hoc oracle routing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Callable


RowChoice = tuple[bool, bool, int]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scenario(
    rows: list[dict[str, object]],
    chooser: Callable[[dict[str, object]], RowChoice],
    *,
    classification: str,
) -> dict[str, object]:
    correct = valid = rescues = damages = withheld = tokens = 0
    base_tokens = sum(int(row["base_tokens"]) for row in rows)
    for row in rows:
        final_correct, final_valid, row_tokens = chooser(row)
        base_correct = bool(row["base_correct"])
        base_valid = bool(row["base_valid"])
        correct += int(final_correct)
        valid += int(final_valid)
        tokens += row_tokens
        rescues += int(final_valid and final_correct and not base_correct)
        damages += int(final_valid and not final_correct and base_correct)
        withheld += int(not final_valid and base_valid and base_correct)
    return {
        "classification": classification,
        "n": len(rows),
        "correct": correct,
        "accuracy": correct / len(rows),
        "valid": valid,
        "rescues": rescues,
        "published_damages": damages,
        "correct_a0_withheld": withheld,
        "total_provider_tokens": tokens,
        "base_provider_tokens": base_tokens,
        "aggregate_token_multiplier_vs_a0": tokens / base_tokens,
    }


def build_replay(audit: dict[str, object]) -> dict[str, object]:
    rows = list(audit["rows"])

    def historical(row: dict[str, object]) -> RowChoice:
        return bool(row["final_correct"]), bool(row["final_valid"]), int(
            row["combined_tokens"]
        )

    def direct(row: dict[str, object]) -> RowChoice:
        return bool(row["base_correct"]), bool(row["base_valid"]), int(
            row["base_tokens"]
        )

    def safe_after_route(row: dict[str, object]) -> RowChoice:
        return bool(row["base_correct"]), bool(row["base_valid"]), int(
            row["combined_tokens"]
        )

    def contract_fallback(row: dict[str, object]) -> RowChoice:
        if bool(row["final_valid"]):
            return historical(row)
        return bool(row["base_correct"]), bool(row["base_valid"]), int(
            row["combined_tokens"]
        )

    def hybrid(row: dict[str, object]) -> RowChoice:
        if row["arm"] == "FOIL":
            return direct(row)
        return contract_fallback(row)

    def oracle_tool_rescues(row: dict[str, object]) -> RowChoice:
        if row["arm"] == "FOIL_TOOLS" and bool(row["rescued"]):
            return (
                bool(row["final_correct"]),
                bool(row["final_valid"]),
                int(row["base_tokens"]) + int(row["route_tokens"]),
            )
        return direct(row)

    def oracle_terra_rescues(row: dict[str, object]) -> RowChoice:
        if (
            row["arm"] == "FOIL_TOOLS"
            and row["config_id"] == "TERRA_HIGH"
            and bool(row["rescued"])
        ):
            return (
                bool(row["final_correct"]),
                bool(row["final_valid"]),
                int(row["base_tokens"]) + int(row["route_tokens"]),
            )
        return direct(row)

    foil = [row for row in rows if row["arm"] == "FOIL"]
    tools = [row for row in rows if row["arm"] == "FOIL_TOOLS"]
    tool_rescue_rows = [
        {
            "unit_id": row["unit_id"],
            "config_id": row["config_id"],
            "route_tokens": row["route_tokens"],
            "tool_calls": row["tool_calls"],
        }
        for row in tools
        if bool(row["rescued"])
    ]
    return {
        "schema": "foil.hle-active-cost-damage-replay.v1",
        "classification": "POSTHOC_DETERMINISTIC_REPLAY_NOT_EFFICACY_EVIDENCE",
        "source_results_sha256": audit["results_sha256"],
        "audited_facts": {
            "rows": len(rows),
            "base_correct": sum(int(row["base_correct"]) for row in rows),
            "historical_final_correct": sum(
                int(row["final_correct"]) for row in rows
            ),
            "historical_rescues": sum(int(row["rescued"]) for row in rows),
            "historical_published_damages": sum(
                int(row["damaged"]) for row in rows
            ),
            "historical_invalid_rows": sum(
                int(not bool(row["final_valid"])) for row in rows
            ),
            "historical_correct_a0_withheld": sum(
                int(row["withheld_correct"]) for row in rows
            ),
            "no_tools": _scenario(
                foil, historical, classification="SEALED_OBSERVATION"
            ),
            "tools": _scenario(
                tools, historical, classification="SEALED_OBSERVATION"
            ),
            "tool_calls": sum(int(row["tool_calls"]) for row in rows),
            "web_search_calls": sum(int(row["web_search_calls"]) for row in rows),
            "command_calls": sum(int(row["command_calls"]) for row in rows),
        },
        "scenarios": {
            "historical": _scenario(
                rows, historical, classification="SEALED_OBSERVATION"
            ),
            "contract_fallback_only": _scenario(
                rows,
                contract_fallback,
                classification="VALID_A0_FALLBACK_REPLAY",
            ),
            "safe_admission_after_route": _scenario(
                rows,
                safe_after_route,
                classification="UNVERIFIED_CANDIDATES_REJECTED_POST_ROUTE",
            )
            | {"cost_note": "Safety changes publication, not tokens already spent."},
            "direct_preflight": _scenario(
                rows,
                direct,
                classification="NO_ADMITTED_ROUTE_CALL_LAUNCHED",
            ),
            "observed_arm_hybrid": _scenario(
                rows,
                hybrid,
                classification="POSTHOC_ARM_POLICY_NOT_CAUSAL",
            ),
            "oracle_all_tool_rescues": _scenario(
                rows,
                oracle_tool_rescues,
                classification="IMPOSSIBLE_POSTHOC_ORACLE_LOWER_BOUND",
            ),
            "oracle_terra_tool_rescues": _scenario(
                rows,
                oracle_terra_rescues,
                classification="IMPOSSIBLE_POSTHOC_CONFIG_AND_GOLD_ORACLE",
            ),
        },
        "tool_rescue_rows": tool_rescue_rows,
        "non_claims": [
            "deployable task router",
            "same-item tool effect",
            "HLE population accuracy",
            "10-percent tool-route feasibility",
            "production promotion",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    replay = build_replay(audit)
    replay["source_audit_sha256"] = _sha256(args.audit)
    text = json.dumps(replay, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
