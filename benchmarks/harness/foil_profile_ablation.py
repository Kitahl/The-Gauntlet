"""Offline, three-arm P0 profile-routing reproducibility harness.

This module exercises deterministic requirement routing only.  It has no model,
provider, transport, key, network, tool-execution, or runtime-host integration.
Profile payloads reach only the router and public records retain only digests and
receipt-safe traces.  Its structural proxy is never task-efficacy evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import foil_costs as costs  # noqa: E402
import foil_evidence as evidence  # noqa: E402
import foil_requirements as requirements  # noqa: E402
from foil_policy import TaskContext  # noqa: E402

SCHEMA = "egrt.foil-profile-ablation.v1"
FIXTURE_SCHEMA = "egrt.foil-profile-ablation-fixture.v1"
FIXTURE_KIND = "STRUCTURAL_SMOKE_ONLY"
CONDITIONS = ("CORRECT_PROFILE", "WRONG_PROFILE", "NO_PROFILE")
ORDER_SEED = 20260823
P0_STATUS = "P0_NOT_PROMOTED"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EFFECTS = frozenset(
    {
        "useful_complement",
        "necessary_complement",
        "redundant_assistance",
        "harmful_assistance",
        "takeover_event",
        "insufficient_assistance",
        "missed_gap",
        "independent_after_assistance",
        "later_transfer",
    }
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _require_fields(raw: Mapping[str, Any], allowed: set[str], *, label: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"{label} has unknown fields: {sorted(unknown)}")


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("observation time must be ISO-8601 text or null")
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _observation(raw: Mapping[str, Any]) -> evidence.Observation:
    _require_fields(
        raw,
        {"correct", "tier", "time", "representation", "verifier", "capability"},
        label="profile observation",
    )
    if not isinstance(raw.get("correct"), bool):
        raise ValueError("profile observation correct must be boolean")
    return evidence.Observation(
        correct=raw["correct"],
        tier=evidence.EvidenceTier(raw.get("tier", evidence.EvidenceTier.REAL_WORK.value)),
        time=_parse_time(raw.get("time")),
        representation=raw.get("representation"),
        verifier=raw.get("verifier"),
        capability=raw.get("capability"),
    )


def _profile_evidence(
    payload: Mapping[str, Any] | None,
) -> dict[str, requirements.CapabilityEvidence]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("profile arm must be an object")
    result: dict[str, requirements.CapabilityEvidence] = {}
    for capability, raw in payload.items():
        if (
            not isinstance(capability, str)
            or not capability.strip()
            or not isinstance(raw, Mapping)
        ):
            raise ValueError("profile capability entries must be named objects")
        _require_fields(
            raw,
            {"observations", "transfer_confirmations", "context", "stale"},
            label="profile capability",
        )
        observations = raw.get("observations", [])
        transfers = raw.get("transfer_confirmations", 0)
        if not isinstance(observations, list):
            raise ValueError("profile observations must be a list")
        if isinstance(transfers, bool) or not isinstance(transfers, int) or transfers < 0:
            raise ValueError("transfer_confirmations must be a non-negative integer")
        if "stale" in raw and not isinstance(raw["stale"], bool):
            raise ValueError("profile stale must be boolean")
        result[capability] = requirements.CapabilityEvidence(
            observations=tuple(_observation(row) for row in observations),
            transfer_confirmations=transfers,
            context=raw.get("context"),
            stale=bool(raw.get("stale", False)),
        )
    return result


def _requirement(raw: Mapping[str, Any]) -> requirements.TaskCapabilityRequirement:
    _require_fields(
        raw,
        {
            "requirement_id",
            "capability",
            "importance",
            "required_level",
            "evidence_obligation",
            "representation",
            "context",
        },
        label="task requirement",
    )
    if not isinstance(raw.get("requirement_id"), str) or not isinstance(raw.get("capability"), str):
        raise ValueError("task requirement needs text requirement_id and capability")
    return requirements.TaskCapabilityRequirement(
        requirement_id=raw["requirement_id"],
        capability=raw["capability"],
        importance=requirements.RequirementImportance(raw.get("importance", "MEDIUM")),
        required_level=requirements.RequiredLevel(raw.get("required_level", "WORKING")),
        evidence_obligation=raw.get("evidence_obligation"),
        representation=raw.get("representation"),
        context=raw.get("context"),
    )


def _task(raw: Mapping[str, Any] | None) -> TaskContext:
    if raw is None:
        return TaskContext()
    if not isinstance(raw, Mapping):
        raise ValueError("task must be an object")
    allowed = {field.name for field in fields(TaskContext)}
    _require_fields(raw, allowed, label="task")
    return TaskContext(**dict(raw))


def validate_items(items: Sequence[Mapping[str, Any]]) -> None:
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise ValueError("items must be a non-empty list")
    identifiers: list[str] = []
    has_gap = False
    has_no_gap_control = False
    known = {kind.value for kind in requirements.CAPABILITY_COMPLEMENTS.values()}
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("every ablation item must be an object")
        _require_fields(
            item,
            {"item_id", "task", "requirements", "expected_complement", "profiles"},
            label="ablation item",
        )
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("every ablation item needs a nonempty item_id")
        identifiers.append(item_id)
        rows = item.get("requirements")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{item_id}: at least one requirement is required")
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError(f"{item_id}: requirements must be objects")
            _requirement(row)
        _task(item.get("task"))
        expected = item.get("expected_complement")
        if expected is not None and (not isinstance(expected, str) or expected not in known):
            raise ValueError(f"{item_id}: unknown expected complement {expected}")
        has_gap = has_gap or expected is not None
        has_no_gap_control = has_no_gap_control or expected is None
        profiles = item.get("profiles")
        if not isinstance(profiles, Mapping) or set(profiles) != {
            "CORRECT_PROFILE",
            "WRONG_PROFILE",
        }:
            raise ValueError(f"{item_id}: exact correct/wrong profile arms required")
        _profile_evidence(profiles["CORRECT_PROFILE"])
        _profile_evidence(profiles["WRONG_PROFILE"])
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("ablation item_id values must be unique")
    if not has_gap or not has_no_gap_control:
        raise ValueError("ablation needs both gap and no-complement controls")


def validate_fixture(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        raise ValueError("fixture must be an object")
    _require_fields(payload, {"schema", "fixture_kind", "boundary", "items"}, label="fixture")
    if payload.get("schema") != FIXTURE_SCHEMA or payload.get("fixture_kind") != FIXTURE_KIND:
        raise ValueError("fixture must declare the closed structural-smoke schema and kind")
    if not isinstance(payload.get("boundary"), str) or not payload["boundary"].strip():
        raise ValueError("fixture boundary must be non-empty text")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("fixture items must be a list")
    validate_items(items)
    return items


def build_manifest(items: Sequence[Mapping[str, Any]], *, seed: int = ORDER_SEED) -> dict[str, Any]:
    """Build deterministic, item-isolated units without retaining profile payloads."""

    validate_items(items)
    rng = random.Random(seed)
    units: list[dict[str, Any]] = []
    for item in items:
        order = list(CONDITIONS)
        rng.shuffle(order)
        requirement_hash = digest(item["requirements"])
        for position, condition in enumerate(order):
            profile = (item["profiles"] or {}).get(condition, {})
            units.append(
                {
                    "unit_id": f"{item['item_id']}::{condition}",
                    "item_id": item["item_id"],
                    "condition": condition,
                    "order_position": position,
                    "isolation_session_id": digest([seed, item["item_id"], condition])[:24],
                    "requirement_sha256": requirement_hash,
                    "profile_payload_sha256": digest(profile),
                }
            )
    return {
        "schema": SCHEMA,
        "kind": "routing-proxy-manifest",
        "seed": seed,
        "conditions": list(CONDITIONS),
        "profile_visible_to": "router_only",
        "solver_profile_access": False,
        "units": units,
    }


def _route_item(item: Mapping[str, Any], condition: str) -> dict[str, Any]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    profile_payload = item["profiles"].get(condition, {})
    profile = None if condition == "NO_PROFILE" else _profile_evidence(profile_payload)
    routed = requirements.route_requirements(
        _task(item.get("task")),
        tuple(_requirement(row) for row in item["requirements"]),
        profile_evidence=profile,
    )
    selected = routed.selected_complement.value if routed.selected_complement else None
    expected = item["expected_complement"]
    return {
        "item_id": item["item_id"],
        "condition": condition,
        "selected_complement": selected,
        "expected_complement": expected,
        "route_match": selected == expected,
        "complement_hit": expected is not None and selected == expected,
        "correct_no_assistance": expected is None and selected is None,
        "redundant_assistance": selected is not None and expected is None,
        "missed_gap": expected is not None and selected != expected,
        "harmful_route": selected is not None and selected != expected,
        "profile_payload_sha256": digest(profile_payload),
        "route_receipt": routed.trace(),
    }


def _condition_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    gaps = [row for row in rows if row["expected_complement"] is not None]
    controls = [row for row in rows if row["expected_complement"] is None]

    def rate(name: str, values: Sequence[Mapping[str, Any]]) -> float | None:
        return sum(bool(row[name]) for row in values) / len(values) if values else None

    return {
        "items": len(rows),
        "complement_opportunities": len(gaps),
        "no_complement_controls": len(controls),
        "route_accuracy": rate("route_match", rows),
        "complement_hit_rate": rate("complement_hit", gaps),
        "redundant_assistance_rate": rate("redundant_assistance", controls),
        "harmful_route_rate": rate("harmful_route", rows),
        "missed_gap_rate": rate("missed_gap", gaps),
    }


def run_routing_proxy(
    items: Sequence[Mapping[str, Any]], *, seed: int = ORDER_SEED
) -> dict[str, Any]:
    """Run only the deterministic routing control; never score task success."""

    manifest = build_manifest(items, seed=seed)
    by_item = {item["item_id"]: item for item in items}
    rows = [_route_item(by_item[unit["item_id"]], unit["condition"]) for unit in manifest["units"]]
    metrics = {
        condition: _condition_metrics([row for row in rows if row["condition"] == condition])
        for condition in CONDITIONS
    }
    return {
        "schema": SCHEMA,
        "kind": "routing-personalization-proxy",
        "candidate_version": requirements.CANDIDATE_VERSION,
        "manifest": manifest,
        "metrics": metrics,
        "profile_value": (
            metrics["CORRECT_PROFILE"]["complement_hit_rate"]
            - metrics["NO_PROFILE"]["complement_hit_rate"]
        ),
        "wrong_profile_excess_harm": (
            metrics["WRONG_PROFILE"]["harmful_route_rate"]
            - metrics["NO_PROFILE"]["harmful_route_rate"]
        ),
        "rows": rows,
        "promotion_status": P0_STATUS,
        "p1_release_allowed": False,
        "behavioral_efficacy_measured": False,
        "boundary": "Routing-control behavior only; not task efficacy or human-learning evidence.",
    }


def _validate_record(row: Mapping[str, Any]) -> costs.RunCostReceipt:
    allowed = {
        "item_id",
        "condition",
        "task_success",
        "effect",
        "model",
        "allowed_tools",
        "budget",
        "usage",
        "run_cost_receipt",
        "prompt_sha256",
        "scorer_sha256",
        "profile_visible_to",
        "solver_profile_access",
        "prediction_frozen",
        "gold_access_before_freeze",
        "isolation_session_id",
    }
    _require_fields(row, allowed, label="behavioral record")
    required = allowed - {"effect"}
    if set(row) != required and set(row) != allowed:
        raise ValueError("behavioral record has missing required fields")
    if (
        row.get("condition") not in CONDITIONS
        or not isinstance(row.get("item_id"), str)
        or not row["item_id"].strip()
    ):
        raise ValueError("behavioral record needs a known condition and non-empty item_id")
    if not isinstance(row.get("task_success"), bool):
        raise ValueError("task_success must be boolean")
    if row.get("effect") is not None and row["effect"] not in _EFFECTS:
        raise ValueError("behavioral record effect is not closed")
    if not isinstance(row.get("model"), str) or not row["model"].strip():
        raise ValueError("behavioral record needs an actual model label")
    if not isinstance(row.get("allowed_tools"), list) or any(
        not isinstance(x, str) or not x for x in row["allowed_tools"]
    ):
        raise ValueError("allowed_tools must be a string list")
    if len(row["allowed_tools"]) != len(set(row["allowed_tools"])) or not isinstance(
        row.get("budget"), Mapping
    ):
        raise ValueError("allowed_tools must be unique and budget must be an object")
    usage = row.get("usage")
    if not isinstance(usage, Mapping) or set(usage) != {
        "model_calls",
        "tool_calls",
        "latency_ms",
        "tokens",
    }:
        raise ValueError(
            "usage must contain exactly model_calls, tool_calls, latency_ms, and tokens"
        )
    for name, value in usage.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"usage.{name} must be non-negative numeric")
    if any(not isinstance(usage[name], int) for name in ("model_calls", "tool_calls", "tokens")):
        raise ValueError("usage call and token counts must be integers")
    for name in ("prompt_sha256", "scorer_sha256"):
        _require_digest(name, row.get(name))
    if (
        row.get("profile_visible_to") != "router_only"
        or row.get("solver_profile_access") is not False
    ):
        raise ValueError("profile must remain router-only")
    if (
        row.get("prediction_frozen") is not True
        or row.get("gold_access_before_freeze") is not False
    ):
        raise ValueError("prediction must freeze before gold access")
    if not isinstance(row.get("isolation_session_id"), str) or not row["isolation_session_id"]:
        raise ValueError("isolation_session_id is required")
    raw_receipt = row.get("run_cost_receipt")
    if not isinstance(raw_receipt, Mapping):
        raise ValueError("run_cost_receipt is required")
    receipt = costs.RunCostReceipt.from_mapping(raw_receipt)
    if receipt.task_id != row["item_id"] or receipt.condition != row["condition"]:
        raise ValueError("run-cost receipt must bind item and condition")
    if receipt.prompt_sha256 != row["prompt_sha256"]:
        raise ValueError("run-cost prompt digest mismatch")
    for usage_name, receipt_name in (
        ("model_calls", "model_calls"),
        ("tool_calls", "tool_calls"),
        ("latency_ms", "wall_time_ms"),
    ):
        value = getattr(receipt, receipt_name)
        if value is not None and value != usage[usage_name]:
            raise ValueError(f"run-cost {receipt_name} disagrees with usage.{usage_name}")
    if (
        receipt.tokens_in is not None
        and receipt.tokens_out is not None
        and receipt.tokens_in + receipt.tokens_out != usage["tokens"]
    ):
        raise ValueError("run-cost tokens disagree with usage.tokens")
    if row["condition"] == "NO_PROFILE":
        if receipt.profile_payload_sha256 is not None or receipt.profile_lookup_count not in (
            None,
            0,
        ):
            raise ValueError("NO_PROFILE must not record profile access")
    elif receipt.profile_payload_sha256 is None:
        raise ValueError("profile arms require only a sealed profile digest")
    return receipt


def score_behavioral_records(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Describe externally supplied records without promoting proxy output to efficacy."""

    if not records:
        raise ValueError("at least one complete condition triple is required")
    grouped: dict[str, dict[str, Mapping[str, Any]]] = {}
    receipts: dict[tuple[str, str], costs.RunCostReceipt] = {}
    sessions: set[str] = set()
    for row in records:
        receipt = _validate_record(row)
        item_id, condition = row["item_id"], row["condition"]
        if condition in grouped.setdefault(item_id, {}) or row["isolation_session_id"] in sessions:
            raise ValueError("item/condition and isolation sessions must be unique")
        sessions.add(row["isolation_session_id"])
        grouped[item_id][condition] = row
        receipts[(item_id, condition)] = receipt
    matched = ("model", "allowed_tools", "budget", "prompt_sha256", "scorer_sha256")
    for item_id, arms in grouped.items():
        if set(arms) != set(CONDITIONS):
            raise ValueError(f"{item_id}: incomplete condition triple")
        for field in matched:
            if len({_canonical(arms[condition][field]) for condition in CONDITIONS}) != 1:
                raise ValueError(f"{item_id}: unmatched condition {field}")

    metrics: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        rows = [arms[condition] for arms in grouped.values()]
        arm_receipts = [receipts[(item_id, condition)] for item_id in grouped]
        successes = sum(row["task_success"] for row in rows)
        count = len(rows)
        metrics[condition] = {
            "items": count,
            "task_success_rate": successes / count,
            "total_cost": costs.aggregate_costs(arm_receipts),
            "mean_cost": costs.mean_costs(arm_receipts),
            "cost_per_correct": costs.cost_per_correct(arm_receipts, successes),
            "harmful_or_takeover_rate": sum(
                row.get("effect") in {"harmful_assistance", "takeover_event"} for row in rows
            )
            / count,
        }
    exact_cost_match = all(
        costs.matched_total_cost([receipts[(item_id, condition)] for condition in CONDITIONS])
        for item_id in grouped
    )
    return {
        "schema": SCHEMA,
        "kind": "external-behavioral-record-description",
        "metrics": metrics,
        "profile_value_task_success": metrics["CORRECT_PROFILE"]["task_success_rate"]
        - metrics["NO_PROFILE"]["task_success_rate"],
        "wrong_profile_task_success_delta": metrics["WRONG_PROFILE"]["task_success_rate"]
        - metrics["NO_PROFILE"]["task_success_rate"],
        "actual_cost_matched": exact_cost_match,
        "promotion_status": P0_STATUS,
        "behavioral_efficacy_measured": False,
        "boundary": "Descriptive external records only; no efficacy, promotion, or causal claim is issued.",
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="offline FOIL three-arm profile ablation")
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=ORDER_SEED)
    args = parser.parse_args(argv)
    report = run_routing_proxy(validate_fixture(_load_json(args.fixture)), seed=args.seed)
    _write_json(args.out, report)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
