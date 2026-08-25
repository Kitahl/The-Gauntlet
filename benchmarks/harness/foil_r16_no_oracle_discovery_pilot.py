#!/usr/bin/env python3
"""Run the preregistered FOIL R1.6 no-oracle discovery smoke pilot."""

from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import math
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from statistics import NormalDist
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_host_finalizer import answer_digest  # noqa: E402
from egrt_types import canonical_json, digest  # noqa: E402
from foil_obligation_compiler import compile_task_spec  # noqa: E402
from foil_residual_scanner import scan  # noqa: E402
from foil_v5_metrics import ScanStatus  # noqa: E402

try:  # Added by the R1.6 implementation seam; import stays loud when absent.
    from foil_obligation_discovery import (  # type: ignore[import-not-found]  # noqa: E402
        DISCOVERY_REQUEST_SCHEMA,
        DISCOVERY_ROUTE_ID,
        discover_obligations,
    )
except ImportError:  # pragma: no cover - exercised only before the seam exists.
    DISCOVERY_REQUEST_SCHEMA = "foil.discovery-request.v1"
    DISCOVERY_ROUTE_ID = "gsm8k.annotated-arithmetic.v1"
    discover_obligations = None


RUNTIME_BASE_COMMIT = "a584602c0bb976429b3c8fe309bfeeeb604a9090"
SOURCE_COMMIT = "3101c7d5072418e28b9008a6636bde82a006892c"
SOURCE_URL = (
    "https://raw.githubusercontent.com/openai/grade-school-math/"
    f"{SOURCE_COMMIT}/grade_school_math/data/example_model_solutions.jsonl"
)
SOURCE_SHA256 = "4bc62db838f8418365d51c627bd66294cbdca9fb7f01519cb13f0dce8c51580b"
SELECTION_SEED = 20260824
MODEL_VARIANTS = (
    "6b_finetuning",
    "6b_verification",
    "175b_finetuning",
    "175b_verification",
)
NATURAL_LABELS = (
    "RESULT",
    "FINAL",
    "OPERAND",
    "DROPSTEP",
    "SWAPOP",
    "CONSISTENT_LOCAL",
    "CONSISTENT_GLOBAL",
)
OPERATOR_TO_LABEL = {
    "M1_RESULT": "RESULT",
    "M2_FINAL": "FINAL",
    "M3_OPERAND": "OPERAND",
    "M4_DROPSTEP": "DROPSTEP",
    "M5_SWAPOP": "SWAPOP",
    "M7_CONSISTENT": "CONSISTENT_LOCAL",
    "M9_CONSISTENT_BIG": "CONSISTENT_GLOBAL",
}
OPERATORS = tuple(OPERATOR_TO_LABEL)
ATTEMPT_STATUSES = ("EXECUTED", "EQUIVALENT", "INVALID", "UNSUPPORTED")
LABEL_SCHEMA = "foil.r16-natural-labels.v1"
REPORT_SCHEMA = "foil.r16-no-oracle-discovery-report.v1"

PROTOCOL = {
    "schema": "foil.r16-no-oracle-discovery-pilot.v1",
    "runtime_base_commit": RUNTIME_BASE_COMMIT,
    "route_id": DISCOVERY_ROUTE_ID,
    "source_commit": SOURCE_COMMIT,
    "source_sha256": SOURCE_SHA256,
    "selection_seed": SELECTION_SEED,
    "mutation_base_rows": 8,
    "operators": OPERATOR_TO_LABEL,
    "natural_per_class": 2,
    "correct_controls": 14,
    "max_reviewed_candidates": 60,
    "minimum_common_classes": 3,
    "association": "exact-permutation-spearman-primary;pearson-descriptive",
    "interval": "two-sided-wilson-95",
    "provider_calls_allowed": 0,
    "external_bots_allowed": 0,
    "runtime_model_calls_allowed": 0,
    "token_spend_allowed": 0,
    "answer_mutations_by_foil_allowed": 0,
    "profile_writes_allowed": 0,
    "execution_authorizations_allowed": 0,
    "promotion_changes_allowed": 0,
    "source_network_calls": 1,
}
PROTOCOL_SHA256 = digest(PROTOCOL)

NUMBER_PATTERN = r"[-+]?(?:\d[\d,]*(?:\.\d+)?|\d+/\d+)"
ANNOTATION_RE = re.compile(
    rf"<<(?P<expr>[^<>\r\n]{{1,256}})=(?P<result>{NUMBER_PATTERN})>>"
    rf"(?P<echo>\$?{NUMBER_PATTERN})?"
)
FINAL_RE = re.compile(rf"(?im)^\s*A:\s*\$?(?P<value>{NUMBER_PATTERN})\s*$")
EXPR_NUMBER_RE = re.compile(NUMBER_PATTERN)
MAX_SOURCE_BYTES = 8_000_000
MAX_SOURCE_ROWS = 2_000
MAX_EXPRESSION_CHARS = 256
MAX_AST_NODES = 128


@dataclass(frozen=True)
class SourceResponse:
    question_sha256: str
    response_sha256: str
    question: str
    ground_truth: str
    model_variant: str
    solution: str
    is_correct: bool

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.question_sha256, self.model_variant, self.response_sha256


@dataclass(frozen=True)
class Annotation:
    expression: str
    result: str
    start: int
    end: int


@dataclass(frozen=True)
class MutationAttempt:
    question_sha256: str
    operator_id: str
    natural_label: str
    status: str
    original_answer_sha256: str
    mutant_answer_sha256: str | None
    mutant: str | None
    reason: str


@dataclass(frozen=True)
class Prediction:
    item_sha256: str
    detected: bool
    discovery_status: str
    envelope_sha256: str
    a0_preserved: bool
    reason: str


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def _require_commit(value: str) -> str:
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("protocol_commit must be a lowercase 40-hex Git commit")
    return value


def _rank_key(*parts: str) -> str:
    payload = "\0".join((str(SELECTION_SEED), *parts))
    return sha256_text(payload)


def _canonical_number(value: str | Fraction) -> str:
    fraction = value if isinstance(value, Fraction) else Fraction(str(value).replace(",", ""))
    return str(fraction.numerator) if fraction.denominator == 1 else str(fraction)


def _fraction_value(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(
        node.value, bool
    ):
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _fraction_value(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left, right = _fraction_value(node.left), _fraction_value(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0:
            raise ValueError("division by zero")
        return left / right
    raise ValueError("unsupported arithmetic syntax")


def evaluate_expression(expression: str) -> str:
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("expression must be non-empty text")
    if len(expression) > MAX_EXPRESSION_CHARS:
        raise ValueError("expression exceeds the bounded parser limit")
    tree = ast.parse(expression.replace(",", ""), mode="eval")
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise ValueError("expression exceeds the bounded AST limit")
    return _canonical_number(_fraction_value(tree.body))


def expression_numbers(expression: str) -> tuple[str, ...]:
    tree = ast.parse(expression.replace(",", ""), mode="eval")
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(
            node.value, bool
        ):
            values.append(_canonical_number(Fraction(str(node.value))))
    return tuple(values)


def parse_annotations(solution: str) -> tuple[Annotation, ...]:
    if not isinstance(solution, str):
        raise TypeError("solution must be str")
    return tuple(
        Annotation(match.group("expr"), _canonical_number(match.group("result")), *match.span())
        for match in ANNOTATION_RE.finditer(solution)
    )


def final_value(solution: str) -> str | None:
    matches = list(FINAL_RE.finditer(solution))
    return _canonical_number(matches[-1].group("value")) if matches else None


def _replace_final(solution: str, value: str) -> str:
    matches = list(FINAL_RE.finditer(solution))
    if not matches:
        raise ValueError("final A: value is absent")
    match = matches[-1]
    return solution[: match.start("value")] + value + solution[match.end("value") :]


def _replace_annotation(solution: str, index: int, expression: str, result: str) -> str:
    matches = list(ANNOTATION_RE.finditer(solution))
    if index < 0 or index >= len(matches):
        raise IndexError("annotation index is outside the solution")
    match = matches[index]
    rendered = f"<<{expression}={result}>>{result}"
    return solution[: match.start()] + rendered + solution[match.end() :]


def _replace_number_token(expression: str, old: str, new: str, *, first_only: bool) -> str:
    replaced = False

    def callback(match: re.Match[str]) -> str:
        nonlocal replaced
        try:
            same = _canonical_number(match.group(0)) == old
        except (ValueError, ZeroDivisionError):
            same = False
        if same and (not first_only or not replaced):
            replaced = True
            return new
        return match.group(0)

    result = EXPR_NUMBER_RE.sub(callback, expression)
    if not replaced:
        raise ValueError("number token was not found")
    return result


def _first_binary_operator(expression: str) -> tuple[int, str] | None:
    for index, char in enumerate(expression):
        if char in "+-*/" and not (index == 0 and char in "+-"):
            return index, char
    return None


def _different_operator(expression: str) -> tuple[str, str] | None:
    located = _first_binary_operator(expression)
    if located is None:
        return None
    index, current = located
    for candidate in "+-*/":
        if candidate == current:
            continue
        changed = expression[:index] + candidate + expression[index + 1 :]
        try:
            evaluate_expression(changed)
        except (SyntaxError, ValueError, ZeroDivisionError):
            continue
        return changed, candidate
    return None


def load_source(source: bytes, *, expected_sha256: str = SOURCE_SHA256) -> list[SourceResponse]:
    if not isinstance(source, bytes):
        raise TypeError("source must be bytes")
    if len(source) > MAX_SOURCE_BYTES:
        raise RuntimeError("source exceeds the bounded byte limit")
    if sha256_bytes(source) != expected_sha256:
        raise RuntimeError("GSM8K model-solution source digest mismatch")
    records: list[SourceResponse] = []
    seen: set[tuple[str, str, str]] = set()
    lines = source.decode("utf-8").splitlines()
    if not lines or len(lines) > MAX_SOURCE_ROWS:
        raise RuntimeError("unexpected GSM8K source row count")
    for line in lines:
        row = json.loads(line)
        required = {"question", "ground_truth", *MODEL_VARIANTS}
        if not isinstance(row, dict) or set(row) != required:
            raise RuntimeError("unexpected GSM8K source schema")
        question, ground_truth = row["question"], row["ground_truth"]
        if not isinstance(question, str) or not question.strip():
            raise RuntimeError("GSM8K question is missing")
        if not isinstance(ground_truth, str) or not ground_truth.strip():
            raise RuntimeError("GSM8K ground truth is missing")
        question_sha256 = sha256_text(question)
        for model_variant in MODEL_VARIANTS:
            response = row[model_variant]
            if not isinstance(response, dict) or set(response) != {"is_correct", "solution"}:
                raise RuntimeError("unexpected GSM8K model-response schema")
            if not isinstance(response["is_correct"], bool) or not isinstance(
                response["solution"], str
            ):
                raise RuntimeError("invalid GSM8K model response")
            solution = response["solution"]
            response_sha256 = sha256_text(solution)
            identity = (question_sha256, model_variant, response_sha256)
            if identity in seen:
                raise RuntimeError("duplicate GSM8K response identity")
            seen.add(identity)
            records.append(
                SourceResponse(
                    question_sha256,
                    response_sha256,
                    question,
                    ground_truth,
                    model_variant,
                    solution,
                    response["is_correct"],
                )
            )
    return records


def fetch_source() -> bytes:
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "foil-r16/1"})
    with urllib.request.urlopen(request, timeout=90) as response:
        source = response.read(MAX_SOURCE_BYTES + 1)
    if len(source) > MAX_SOURCE_BYTES:
        raise RuntimeError("source download exceeded the bounded byte limit")
    return source


def candidate_rows(records: Sequence[SourceResponse]) -> list[SourceResponse]:
    wrong = [record for record in records if not record.is_correct]
    wrong.sort(
        key=lambda item: _rank_key(
            item.question_sha256, item.model_variant, item.response_sha256
        )
    )
    selected: list[SourceResponse] = []
    seen_questions: set[str] = set()
    for record in wrong:
        if record.question_sha256 in seen_questions:
            continue
        selected.append(record)
        seen_questions.add(record.question_sha256)
        if len(selected) == int(PROTOCOL["max_reviewed_candidates"]):
            break
    return selected


def candidate_pack(records: Sequence[SourceResponse]) -> dict[str, object]:
    rows = candidate_rows(records)
    return {
        "schema": "foil.r16-natural-label-candidates.v1",
        "source_sha256": SOURCE_SHA256,
        "selection_seed": SELECTION_SEED,
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
    if not isinstance(raw, Mapping) or set(raw) != {
        "schema",
        "source_sha256",
        "selection_seed",
        "rows",
    }:
        raise RuntimeError("unexpected natural-label manifest schema")
    if raw["schema"] != LABEL_SCHEMA or raw["source_sha256"] != SOURCE_SHA256:
        raise RuntimeError("natural-label manifest binding mismatch")
    if raw["selection_seed"] != SELECTION_SEED or not isinstance(raw["rows"], list):
        raise RuntimeError("natural-label manifest selection mismatch")
    candidate_identities = {record.identity for record in candidates}
    labels: dict[tuple[str, str, str], str] = {}
    allowed = {*NATURAL_LABELS, "UNMAPPED"}
    for row in raw["rows"]:
        if not isinstance(row, dict) or set(row) != {
            "question_sha256",
            "model_variant",
            "response_sha256",
            "primary_label",
        }:
            raise RuntimeError("invalid natural-label row")
        identity = (
            row["question_sha256"],
            row["model_variant"],
            row["response_sha256"],
        )
        if identity not in candidate_identities or identity in labels:
            raise RuntimeError("label row is outside the frozen candidate set or duplicated")
        label = row["primary_label"]
        if label not in allowed:
            raise RuntimeError("unknown natural-miss label")
        labels[identity] = label
    expected_prefix = [record.identity for record in candidates[: len(labels)]]
    if set(labels) != set(expected_prefix):
        raise RuntimeError("labelled rows must be an exact candidate-order prefix")
    return labels


def select_natural_misses(
    candidates: Sequence[SourceResponse], labels: Mapping[tuple[str, str, str], str]
) -> list[tuple[SourceResponse, str]]:
    quotas = {label: int(PROTOCOL["natural_per_class"]) for label in NATURAL_LABELS}
    counts: Counter[str] = Counter()
    selected: list[tuple[SourceResponse, str]] = []
    for record in candidates:
        label = labels.get(record.identity)
        if label is None:
            break
        if label in quotas and counts[label] < quotas[label]:
            selected.append((record, label))
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
                if row.is_correct
                and row.model_variant == variant
                and row.question_sha256 not in seen
            ),
            key=lambda item: _rank_key(
                "correct", item.question_sha256, item.model_variant, item.response_sha256
            ),
        )
        for row in eligible[: quotas[variant]]:
            selected.append(row)
            seen.add(row.question_sha256)
    if len(selected) != target:
        raise RuntimeError("insufficient distinct correct controls")
    return sorted(selected, key=lambda item: _rank_key("correct-final", *item.identity))
