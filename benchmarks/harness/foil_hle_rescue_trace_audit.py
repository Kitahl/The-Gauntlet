"""Zero-token audit of the four historical HLE tool-arm rescue traces.

This audit asks a narrower question than the original score report: can a
specific saved tool call be credited with the answer change?  It fails closed
when web result passages were not retained, when the query contains the gold
answer or benchmark identifier, or when a claimed computation never executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402


REPORT_SCHEMA = "foil.hle-rescue-trace-audit.v1"
SOURCE_ROOT = Path("benchmark_runs/2026-08-26/hle_active_20")


@dataclass(frozen=True)
class RescueSpec:
    unit_id: str
    item_id: str
    gold: str
    mechanism: str


RESCUES = (
    RescueSpec(
        "luna_high-foil_tools-hle-66ea7d2cc321286a5288ef06",
        "hle-66ea7d2cc321286a5288ef06",
        "624",
        "SCHOLARLY_RETRIEVAL",
    ),
    RescueSpec(
        "terra_high-foil_tools-hle-66ea7d2cc321286a5288ef06",
        "hle-66ea7d2cc321286a5288ef06",
        "624",
        "SCHOLARLY_RETRIEVAL",
    ),
    RescueSpec(
        "luna_high-foil_tools-hle-672a80a432cd57d8762583e9",
        "hle-672a80a432cd57d8762583e9",
        "3.8",
        "RETRIEVE_THEN_COMPUTE",
    ),
    RescueSpec(
        "terra_high-foil_tools-hle-672a80a432cd57d8762583e9",
        "hle-672a80a432cd57d8762583e9",
        "3.8",
        "RETRIEVE_THEN_COMPUTE",
    ),
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_events(path: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        events.append(value)
    return events


def _completed_items(events: list[dict[str, object]], kind: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for event in events:
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == kind
        ):
            rows.append(item)
    return rows


def _query_strings(items: list[dict[str, object]]) -> list[str]:
    values: list[str] = []
    for item in items:
        query = item.get("query")
        if isinstance(query, str) and query.strip():
            values.append(query)
        action = item.get("action")
        if isinstance(action, dict):
            action_query = action.get("query")
            if isinstance(action_query, str) and action_query.strip() and action_query not in values:
                values.append(action_query)
            action_queries = action.get("queries")
            if isinstance(action_queries, list):
                values.extend(
                    value
                    for value in action_queries
                    if isinstance(value, str) and value.strip() and value not in values
                )
    return values


def _contains_token(text: str, token: str) -> bool:
    return re.search(rf"(?<![0-9A-Za-z.]){re.escape(token)}(?![0-9A-Za-z.])", text) is not None


def _successful_compute_calls(commands: list[dict[str, object]]) -> int:
    total = 0
    for item in commands:
        command = str(item.get("command", ""))
        if item.get("exit_code") == 0 and "SKILL.md" not in command and "Get-Content" not in command:
            total += 1
    return total


def build_report(root: Path = ROOT) -> dict[str, object]:
    source = root / SOURCE_ROOT
    audit = _read_object(source / "independent_audit.json")
    raw_rows = audit.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("independent audit rows are missing")
    row_by_unit = {
        str(row["unit_id"]): row for row in raw_rows if isinstance(row, dict)
    }
    if len(row_by_unit) != len(raw_rows):
        raise ValueError("independent audit unit ids are invalid or duplicated")

    routes: list[dict[str, object]] = []
    for spec in RESCUES:
        if spec.unit_id not in row_by_unit:
            raise ValueError(f"missing independent-audit row: {spec.unit_id}")
        base = source / "private" / spec.unit_id / "route"
        events_path = base / "events.jsonl"
        last_path = base / "last.json"
        events = _read_events(events_path)
        last = _read_object(last_path)
        if str(last.get("answer")) != spec.gold:
            raise ValueError(f"saved final answer drift for {spec.unit_id}")
        web_items = _completed_items(events, "web_search")
        commands = _completed_items(events, "command_execution")
        queries = _query_strings(web_items)
        urls = last.get("evidence_urls")
        if not isinstance(urls, list) or not all(isinstance(url, str) for url in urls):
            raise ValueError("evidence_urls must be a text list")
        item_id_in_query = any(spec.item_id.removeprefix("hle-") in query for query in queries)
        gold_in_query = any(_contains_token(query, spec.gold) for query in queries)
        benchmark_source_cited = any(
            "huggingface.co/datasets/" in url or "humanitys_last_exam" in url.lower()
            for url in urls
        )
        successful_compute = _successful_compute_calls(commands)
        search_outputs_preserved = all(
            any(key in item for key in ("results", "output", "content", "snippets"))
            for item in web_items
        ) if web_items else False
        if item_id_in_query or gold_in_query or benchmark_source_cited:
            classification = "LEAKAGE_CONTAMINATED"
            reason = "query_or_citation_contains_benchmark_identifier_or_gold"
        elif spec.mechanism == "RETRIEVE_THEN_COMPUTE" and successful_compute == 0:
            classification = "UNVERIFIED_COMPUTATION"
            reason = "final_claims_numeric_solve_but_no_compute_call_succeeded"
        elif not search_outputs_preserved:
            classification = "NOT_IDENTIFIABLE"
            reason = "search_result_passages_not_preserved"
        else:
            classification = "TRACEABLE"
            reason = "saved_call_output_mechanically_supports_attribution"
        source_row = row_by_unit[spec.unit_id]
        routes.append(
            {
                "unit_id": spec.unit_id,
                "item_id": spec.item_id,
                "mechanism": spec.mechanism,
                "tool_calls": len(web_items) + len(commands),
                "web_search_calls": len(web_items),
                "command_calls": len(commands),
                "successful_compute_calls": successful_compute,
                "route_tokens": int(source_row["route_tokens"]),
                "item_id_in_query": item_id_in_query,
                "gold_in_query": gold_in_query,
                "benchmark_source_cited": benchmark_source_cited,
                "search_outputs_preserved": search_outputs_preserved,
                "classification": classification,
                "classification_reason": reason,
                "admissible_rescue_evidence": classification == "TRACEABLE",
                "single_target_call_supported": classification == "TRACEABLE" and len(web_items) + len(commands) == 1,
                "events_sha256": _sha256_file(events_path),
                "last_sha256": _sha256_file(last_path),
            }
        )
    total_calls = sum(int(row["tool_calls"]) for row in routes)
    web_calls = sum(int(row["web_search_calls"]) for row in routes)
    command_calls = sum(int(row["command_calls"]) for row in routes)
    if (total_calls, web_calls, command_calls) != (29, 20, 9):
        raise ValueError("frozen rescue-call conservation failed")
    admissible = sum(bool(row["admissible_rescue_evidence"]) for row in routes)
    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "classification": "POSTHOC_ZERO_TOKEN_TRACE_AUDIT",
        "source_independent_audit_sha256": _sha256_file(source / "independent_audit.json"),
        "routes": routes,
        "distinct_questions": len({spec.item_id for spec in RESCUES}),
        "reported_rescue_rows": len(routes),
        "admissible_rescue_rows": admissible,
        "tool_calls": total_calls,
        "web_search_calls": web_calls,
        "command_calls": command_calls,
        "provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "new_token_spend": 0,
        "single_target_retrieval_supported": any(
            bool(row["single_target_call_supported"]) for row in routes
        ),
        "calibration_gate": "FAIL" if admissible == 0 else "REVIEW",
        "non_claims": [
            "not an arm-blind efficacy estimate",
            "not proof that the final answers were wrong",
            "not proof that retrieval can never help HLE",
            "not a source-passage entailment judgment",
        ],
    }
    report["report_sha256"] = digest(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(report["report_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
