#!/usr/bin/env python3
"""Frozen selection contract for the FOIL R1.7 provenance-repair pilot."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import foil_r16_no_oracle_discovery_pilot as r16  # noqa: E402

SOURCE_COMMIT = r16.SOURCE_COMMIT
SOURCE_URL = r16.SOURCE_URL
SOURCE_SHA256 = r16.SOURCE_SHA256
MODEL_VARIANTS = r16.MODEL_VARIANTS
NATURAL_LABELS = r16.NATURAL_LABELS
OPERATOR_TO_LABEL = r16.OPERATOR_TO_LABEL
OPERATORS = r16.OPERATORS
SourceResponse = r16.SourceResponse
Prediction = r16.Prediction
MutationAttempt = r16.MutationAttempt

SELECTION_SEED = 2026082402
LABEL_SCHEMA = "foil.r17-natural-labels.v1"
REPORT_SCHEMA = "foil.r17-provenance-repair-report.v1"
R16_LABEL_FILE_SHA256 = "60ed6f3ad4c3eefcd4b983b7d41d63c96a188cdad8d7a9a133ab520acae3dc6e"
R16_REPORT_FILE_SHA256 = "42285c9e520b6c26d00e289b3e5f1033fed4e19585633f6a74dd473cfd197dde"

PROTOCOL = {
    "schema": "foil.r17-provenance-repair-pilot.v1",
    "route_id": "gsm8k.annotated-arithmetic.v2",
    "source_commit": SOURCE_COMMIT,
    "source_sha256": SOURCE_SHA256,
    "selection_seed": SELECTION_SEED,
    "r16_is_development_evidence": True,
    "r16_label_file_sha256": R16_LABEL_FILE_SHA256,
    "r16_report_file_sha256": R16_REPORT_FILE_SHA256,
    "mutation_base_rows": 4,
    "operators": OPERATOR_TO_LABEL,
    "natural_per_class": 1,
    "correct_controls": 20,
    "max_reviewed_candidates": 30,
    "minimum_common_classes": 3,
    "association": "exact-permutation-spearman-primary;pearson-descriptive",
    "interval": "two-sided-wilson-95",
    "decision_rule": {
        "FAIL_NOISY": "control_false_fires >= 4",
        "FAIL_RECALL": "natural_support >= 5 and natural_detection_rate <= 0.5",
        "SMOKE_PROMISING": "control_false_fires <= 1 and natural_support >= 5 and natural_misses <= 1",
        "otherwise": "INCONCLUSIVE",
    },
    "provider_calls_allowed": 0,
    "external_bots_allowed": 0,
    "runtime_model_calls_allowed": 0,
    "token_spend_allowed": 0,
    "answer_mutations_by_foil_allowed": 0,
    "profile_writes_allowed": 0,
    "execution_authorizations_allowed": 0,
    "promotion_changes_allowed": 0,
}
PROTOCOL_SHA256 = r16.digest(PROTOCOL)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def _rank_key(*parts: str) -> str:
    return sha256_text("\0".join((str(SELECTION_SEED), *parts)))


def load_source(source: bytes) -> list[SourceResponse]:
    return r16.load_source(source, expected_sha256=SOURCE_SHA256)


def load_r16_exclusions(label_bytes: bytes, report_bytes: bytes) -> set[str]:
    if sha256_bytes(label_bytes) != R16_LABEL_FILE_SHA256:
        raise RuntimeError("R1.6 label exclusion digest mismatch")
    if sha256_bytes(report_bytes) != R16_REPORT_FILE_SHA256:
        raise RuntimeError("R1.6 report exclusion digest mismatch")
    labels, report = json.loads(label_bytes), json.loads(report_bytes)
    if not isinstance(labels, dict) or not isinstance(labels.get("rows"), list):
        raise RuntimeError("R1.6 label exclusion schema mismatch")
    if not isinstance(report, dict) or not isinstance(report.get("raw_rows"), list):
        raise RuntimeError("R1.6 report exclusion schema mismatch")
    excluded = {str(row["question_sha256"]) for row in labels["rows"]}
    excluded.update(str(row["question_sha256"]) for row in report["raw_rows"])
    if len(excluded) < 60:
        raise RuntimeError("R1.6 exclusion universe is unexpectedly small")
    return excluded


def candidate_rows(
    records: Sequence[SourceResponse], excluded_questions: set[str]
) -> list[SourceResponse]:
    wrong = sorted(
        (row for row in records if not row.is_correct and row.question_sha256 not in excluded_questions),
        key=lambda item: _rank_key(item.question_sha256, item.model_variant, item.response_sha256),
    )
    selected: list[SourceResponse] = []
    seen = set(excluded_questions)
    for row in wrong:
        if row.question_sha256 in seen:
            continue
        selected.append(row)
        seen.add(row.question_sha256)
        if len(selected) == int(PROTOCOL["max_reviewed_candidates"]):
            break
    return selected


def candidate_pack(
    records: Sequence[SourceResponse], excluded_questions: set[str]
) -> dict[str, object]:
    rows = candidate_rows(records, excluded_questions)
    return {
        "schema": "foil.r17-natural-label-candidates.v1",
        "source_sha256": SOURCE_SHA256,
        "selection_seed": SELECTION_SEED,
        "excluded_question_count": len(excluded_questions),
        "rows": [
            {
                "question_sha256": row.question_sha256,
                "response_sha256": row.response_sha256,
                "model_variant": row.model_variant,
                "question": row.question,
                "ground_truth": row.ground_truth,
                "solution": row.solution,
            }
            for row in rows
        ],
    }


def load_label_manifest(
    raw: Mapping[str, object], candidates: Sequence[SourceResponse]
) -> dict[tuple[str, str, str], str]:
    required = {"schema", "source_sha256", "selection_seed", "rows"}
    if not isinstance(raw, Mapping) or set(raw) != required:
        raise RuntimeError("unexpected R1.7 natural-label manifest schema")
    if raw["schema"] != LABEL_SCHEMA or raw["source_sha256"] != SOURCE_SHA256:
        raise RuntimeError("R1.7 natural-label manifest binding mismatch")
    if raw["selection_seed"] != SELECTION_SEED or not isinstance(raw["rows"], list):
        raise RuntimeError("R1.7 natural-label manifest selection mismatch")
    candidate_ids = {row.identity for row in candidates}
    labels: dict[tuple[str, str, str], str] = {}
    manifest_ids: list[tuple[str, str, str]] = []
    allowed = {*NATURAL_LABELS, "UNMAPPED"}
    for row in raw["rows"]:
        if not isinstance(row, dict) or set(row) != {
            "question_sha256", "model_variant", "response_sha256", "primary_label"
        }:
            raise RuntimeError("invalid R1.7 natural-label row")
        identity = (row["question_sha256"], row["model_variant"], row["response_sha256"])
        if identity not in candidate_ids or identity in labels:
            raise RuntimeError("R1.7 label is outside the frozen candidate set or duplicated")
        label = row["primary_label"]
        if label not in allowed:
            raise RuntimeError("unknown R1.7 natural-miss label")
        manifest_ids.append(identity)
        labels[identity] = label
    if manifest_ids != [row.identity for row in candidates[: len(labels)]]:
        raise RuntimeError("R1.7 labels must be the exact candidate-order prefix")
    return labels


def select_natural_misses(
    candidates: Sequence[SourceResponse], labels: Mapping[tuple[str, str, str], str]
) -> list[tuple[SourceResponse, str]]:
    counts: Counter[str] = Counter()
    selected: list[tuple[SourceResponse, str]] = []
    quota = int(PROTOCOL["natural_per_class"])
    for row in candidates:
        label = labels.get(row.identity)
        if label is None:
            break
        if label in NATURAL_LABELS and counts[label] < quota:
            selected.append((row, label))
            counts[label] += 1
    return selected


def select_correct_controls(
    records: Sequence[SourceResponse], excluded_questions: set[str]
) -> list[SourceResponse]:
    target = int(PROTOCOL["correct_controls"])
    base, remainder = divmod(target, len(MODEL_VARIANTS))
    quotas = {
        variant: base + (1 if index < remainder else 0)
        for index, variant in enumerate(MODEL_VARIANTS)
    }
    selected: list[SourceResponse] = []
    seen = set(excluded_questions)
    for variant in MODEL_VARIANTS:
        eligible = sorted(
            (
                row
                for row in records
                if row.is_correct and row.model_variant == variant and row.question_sha256 not in seen
            ),
            key=lambda item: _rank_key("correct", item.question_sha256, item.model_variant, item.response_sha256),
        )
        for row in eligible[: quotas[variant]]:
            selected.append(row)
            seen.add(row.question_sha256)
    if len(selected) != target:
        raise RuntimeError("insufficient fresh distinct R1.7 controls")
    return sorted(selected, key=lambda item: _rank_key("correct-final", *item.identity))
