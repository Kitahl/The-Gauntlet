"""Fail-closed JSON codecs for FOIL v2 contracts and raw receipts."""

from __future__ import annotations

from typing import Mapping

from foil_tool_contract_v2 import (
    OperationSpecOrigin,
    PassageEvidenceV2,
    ResourceEnvelopeV2,
    RouteValueEstimate,
    TokenUsageV2,
    ToolContractV2,
    ToolOutcomeV2,
    ToolReceiptV2,
    BoundaryFailureCode,
)


def _closed(raw: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(raw)
    if actual != expected:
        raise ValueError(
            f"closed {label} schema mismatch: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _mapping(name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def parse_tool_contract_v2(raw: Mapping[str, object]) -> ToolContractV2:
    expected = {
        "schema", "task_id", "question_digest", "a0_digest", "family",
        "tool_id", "tool_version", "operation_input_digest", "spec_origin",
        "formalization_admission_sha256", "envelope", "value", "timeout_ms",
        "read_only", "production_authorized", "raw_question_stored",
        "raw_a0_stored", "contract_sha256",
    }
    _closed(raw, expected, "tool-contract-v2")
    if raw["raw_question_stored"] is not False or raw["raw_a0_stored"] is not False:
        raise ValueError("contract cannot contain raw question or A0")
    envelope_raw = _mapping("envelope", raw["envelope"])
    _closed(
        envelope_raw,
        {
            "maximum_input_tokens", "maximum_cached_input_tokens",
            "maximum_output_tokens", "maximum_total_tokens", "maximum_tool_calls",
            "maximum_model_passes", "maximum_latency_ms",
            "maximum_monetary_microunits", "maximum_evidence_characters",
        },
        "resource-envelope-v2",
    )
    envelope = ResourceEnvelopeV2(
        envelope_raw["maximum_input_tokens"],  # type: ignore[arg-type]
        envelope_raw["maximum_cached_input_tokens"],  # type: ignore[arg-type]
        envelope_raw["maximum_output_tokens"],  # type: ignore[arg-type]
        envelope_raw["maximum_tool_calls"],  # type: ignore[arg-type]
        envelope_raw["maximum_model_passes"],  # type: ignore[arg-type]
        envelope_raw["maximum_latency_ms"],  # type: ignore[arg-type]
        envelope_raw["maximum_monetary_microunits"],  # type: ignore[arg-type]
        envelope_raw["maximum_evidence_characters"],  # type: ignore[arg-type]
    )
    if envelope_raw["maximum_total_tokens"] != envelope.maximum_total_tokens:
        raise ValueError("maximum_total_tokens is not conserved")
    value_raw = _mapping("value", raw["value"])
    _closed(
        value_raw,
        {
            "probability_base_error_ppm", "probability_resolution_ppm",
            "probability_damage_ppm", "benefit_microunits", "damage_microunits",
            "token_cost_microunits", "fixed_cost_microunits",
            "expected_gain_microunits", "executes",
        },
        "route-value-v2",
    )
    value = RouteValueEstimate(
        value_raw["probability_base_error_ppm"],  # type: ignore[arg-type]
        value_raw["probability_resolution_ppm"],  # type: ignore[arg-type]
        value_raw["probability_damage_ppm"],  # type: ignore[arg-type]
        value_raw["benefit_microunits"],  # type: ignore[arg-type]
        value_raw["damage_microunits"],  # type: ignore[arg-type]
        value_raw["token_cost_microunits"],  # type: ignore[arg-type]
        value_raw["fixed_cost_microunits"],  # type: ignore[arg-type]
    )
    if value_raw["expected_gain_microunits"] != value.expected_gain_microunits or value_raw["executes"] is not value.executes:
        raise ValueError("route value derivation mismatch")
    contract = ToolContractV2(
        raw["task_id"],  # type: ignore[arg-type]
        raw["question_digest"],  # type: ignore[arg-type]
        raw["a0_digest"],  # type: ignore[arg-type]
        raw["family"],  # type: ignore[arg-type]
        raw["tool_id"],  # type: ignore[arg-type]
        raw["tool_version"],  # type: ignore[arg-type]
        raw["operation_input_digest"],  # type: ignore[arg-type]
        OperationSpecOrigin(raw["spec_origin"]),  # type: ignore[arg-type]
        envelope,
        value,
        raw["timeout_ms"],  # type: ignore[arg-type]
        raw["formalization_admission_sha256"],  # type: ignore[arg-type]
        raw["schema"],  # type: ignore[arg-type]
        raw["read_only"],  # type: ignore[arg-type]
        raw["production_authorized"],  # type: ignore[arg-type]
    )
    if raw["contract_sha256"] != contract.contract_digest:
        raise ValueError("tool contract digest mismatch")
    return contract


def parse_raw_tool_receipt_v2(raw: Mapping[str, object]) -> ToolReceiptV2:
    expected = {
        "schema", "call_id", "contract_sha256", "family", "outcome", "authority",
        "usage", "tool_calls", "latency_ms", "monetary_microunits",
        "candidate_sha256", "verification_expression_sha256", "passages",
        "boundary_failure", "error_detail", "raw_candidate_stored",
        "raw_evidence_stored", "production_authorized", "candidate_answer",
        "verification_expression", "receipt_sha256",
    }
    _closed(raw, expected, "raw-tool-receipt-v2")
    usage_raw = _mapping("usage", raw["usage"])
    _closed(usage_raw, {"input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"}, "token-usage-v2")
    usage = TokenUsageV2(
        usage_raw["input_tokens"],  # type: ignore[arg-type]
        usage_raw["cached_input_tokens"],  # type: ignore[arg-type]
        usage_raw["output_tokens"],  # type: ignore[arg-type]
    )
    if usage_raw["total_tokens"] != usage.total_tokens:
        raise ValueError("token usage is not conserved")
    passages_raw = raw["passages"]
    if not isinstance(passages_raw, list):
        raise TypeError("passages must be a list")
    passages: list[PassageEvidenceV2] = []
    for item in passages_raw:
        value = _mapping("passage", item)
        _closed(
            value,
            {
                "document_id", "source_url", "title_sha256", "content_sha256",
                "retrieved_at", "start_offset", "end_offset", "passage_sha256",
                "source_class", "independent_group", "raw_content_stored",
                "title", "content", "passage",
            },
            "raw-passage-v2",
        )
        passage = PassageEvidenceV2(
            value["document_id"],  # type: ignore[arg-type]
            value["source_url"],  # type: ignore[arg-type]
            value["title"],  # type: ignore[arg-type]
            value["content"],  # type: ignore[arg-type]
            value["retrieved_at"],  # type: ignore[arg-type]
            value["start_offset"],  # type: ignore[arg-type]
            value["end_offset"],  # type: ignore[arg-type]
            value["source_class"],  # type: ignore[arg-type]
            value["independent_group"],  # type: ignore[arg-type]
        )
        if value["passage"] != passage.passage or value["content_sha256"] != passage.content_digest or value["passage_sha256"] != passage.passage_digest:
            raise ValueError("raw passage digest or offset mismatch")
        passages.append(passage)
    failure = None if raw["boundary_failure"] is None else BoundaryFailureCode(raw["boundary_failure"])  # type: ignore[arg-type]
    receipt = ToolReceiptV2(
        raw["call_id"],  # type: ignore[arg-type]
        raw["contract_sha256"],  # type: ignore[arg-type]
        raw["family"],  # type: ignore[arg-type]
        ToolOutcomeV2(raw["outcome"]),  # type: ignore[arg-type]
        usage,
        raw["tool_calls"],  # type: ignore[arg-type]
        raw["latency_ms"],  # type: ignore[arg-type]
        raw["monetary_microunits"],  # type: ignore[arg-type]
        raw["candidate_answer"],  # type: ignore[arg-type]
        raw["verification_expression"],  # type: ignore[arg-type]
        tuple(passages),
        failure,
        raw["error_detail"],  # type: ignore[arg-type]
    )
    if raw["receipt_sha256"] != receipt.trace(include_raw=True)["receipt_sha256"]:
        raise ValueError("raw tool receipt digest mismatch")
    return receipt
