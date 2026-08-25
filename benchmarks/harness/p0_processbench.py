"""P0.5 ProcessBench scorer for FOIL's certified arithmetic equality rule.

The scorer reads all four local parquet files, validates their content digests
and closed schema, and uses ``label == -1`` as the only clean/error boundary.
It performs no sampling, provider calls, profile writes, answer mutations, or
network access.  ``final_answer_correct`` is retained as source metadata but is
never used for scoring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from foil_evidence import regularized_incomplete_beta  # noqa: E402
from latex_eq import (  # noqa: E402
    ASSERTIVE_LANGUAGE,
    AUDIT_LANGUAGE,
    CERTIFIED_LANGUAGE,
    CERTIFIED_V1_LANGUAGE,
    DIVISION_SAFE_LANGUAGE,
    EqualityFinding,
    extract_steps,
)

REPORT_SCHEMA = "foil.p05-certified-arithmetic-report.v1"
AUDIT_SCHEMA = "foil.p05-false-fire-audit.v1"
SPLITS = ("gsm8k", "math", "olympiadbench", "omnimath")
STAGES = (
    AUDIT_LANGUAGE,
    CERTIFIED_V1_LANGUAGE,
    ASSERTIVE_LANGUAGE,
    DIVISION_SAFE_LANGUAGE,
    CERTIFIED_LANGUAGE,
)
MIN_CLEAN_CERTIFICATE = 299
MIN_GENERATOR_CLASS = 20

EXPECTED_FILES = {
    "gsm8k": {
        "rows": 400,
        "sha256": "9896315aff77fff8fe60361f05b612250598a4bd88a70ffba567b4d580d6d4a3",
    },
    "math": {
        "rows": 1_000,
        "sha256": "1874b72fb3c63fb7ea603910195f7efe577895bf5da8ae550b7000fac6322bdd",
    },
    "olympiadbench": {
        "rows": 1_000,
        "sha256": "7ce6eb318520c69e8f07ef3ceeaefd439dac7099a34fd72c8ab41dad0c03e830",
    },
    "omnimath": {
        "rows": 1_000,
        "sha256": "4243eb284456cf1a5c3c1d9e562cbc16d1d7827f4c342852455db8cb86cdedf2",
    },
}
EXPECTED_FIELDS = {
    "id",
    "generator",
    "problem",
    "steps",
    "final_answer_correct",
    "label",
}

MODEL_PARAMETERS_BILLIONS = {
    "Llama-3.1-70B-Instruct": 70.0,
    "Llama-3.1-8B-Instruct": 8.0,
    "Meta-Llama-3-70B-Instruct": 70.0,
    "Meta-Llama-3-8B-Instruct": 8.0,
    "Qwen2-1.5B-Instruct": 1.5,
    "Qwen2-72B-Instruct": 72.0,
    "Qwen2-7B-Instruct": 7.0,
    "Qwen2.5-1.5B-Instruct": 1.5,
    "Qwen2.5-72B-Instruct": 72.0,
    "Qwen2.5-7B-Instruct": 7.0,
    "Qwen2.5-Math-72B-Instruct": 72.0,
    "Qwen2.5-Math-7B-Instruct": 7.0,
}

# Manual classification of every false-fire row reproduced by audit-legacy-v0.
# The original extractor named by the brief was absent, so this map is bound to
# the rebuilt audit language and guarded by a completeness assertion.
AUDIT_FAILURE_MODES = {
    "gsm8k/gsm8k-278": "PERCENT_DIMENSION_COLLAPSE",
    "gsm8k/gsm8k-292": "SYMBOLIC_CHAIN_FRAGMENT",
    "gsm8k/gsm8k-311": "PERCENT_DIMENSION_COLLAPSE",
    "gsm8k/gsm8k-368": "CURRENCY_SPAN_CROSSED_DELIMITER",
    "gsm8k/gsm8k-375": "UNIT_CONVERSION_AS_EQUAL_MAGNITUDE",
    "gsm8k/gsm8k-378": "SYMBOLIC_CHAIN_FRAGMENT",
    "gsm8k/gsm8k-396": "UNIT_CONVERSION_AS_EQUAL_MAGNITUDE",
    "math/math-694": "UNIT_CONVERSION_AS_EQUAL_MAGNITUDE",
    "math/math-883": "DECIMAL_APPROXIMATION",
    "math/math-987": "UNIT_CONVERSION_AS_EQUAL_MAGNITUDE",
    "olympiadbench/olympiadbench-529": "CORPUS_LABEL_FALSE_NEGATIVE_GENUINE_ERROR",
    "olympiadbench/olympiadbench-753": "DECIMAL_APPROXIMATION",
    "olympiadbench/olympiadbench-755": "DECIMAL_APPROXIMATION",
    "olympiadbench/olympiadbench-783": "EXPLICIT_COUNTEREXAMPLE_OR_REJECTED_TRIAL",
    "olympiadbench/olympiadbench-892": "INTEGER_QUOTIENT_WITH_REMAINDER",
    "olympiadbench/olympiadbench-976": "PERCENT_DIMENSION_COLLAPSE",
    "olympiadbench/olympiadbench-987": "CURRENCY_PROSE_CONTEXT_DROPPED",
    "omnimath/omnimath-612": "DECIMAL_APPROXIMATION",
    "omnimath/omnimath-787": "EXPLICIT_COUNTEREXAMPLE_OR_REJECTED_TRIAL",
    "omnimath/omnimath-805": "CORPUS_LABEL_FALSE_NEGATIVE_GENUINE_ERROR",
    "omnimath/omnimath-965": "DECIMAL_APPROXIMATION",
}


@dataclass(frozen=True)
class ProcessRow:
    split: str
    row_id: str
    generator: str
    problem: str
    steps: tuple[str, ...]
    final_answer_correct: bool
    label: int

    @property
    def clean(self) -> bool:
        return self.label == -1


@dataclass(frozen=True)
class ScoredRow:
    row: ProcessRow
    findings: tuple[EqualityFinding, ...]

    @property
    def applicable(self) -> bool:
        return bool(self.findings)

    @property
    def violating(self) -> tuple[EqualityFinding, ...]:
        return tuple(finding for finding in self.findings if finding.violating)

    @property
    def detected(self) -> bool:
        return bool(self.violating)

    @property
    def earliest_firing_step(self) -> int | None:
        if not self.violating:
            return None
        return min(finding.step_index for finding in self.violating)

    def raw(self) -> dict[str, object]:
        return {
            "split": self.row.split,
            "id": self.row.row_id,
            "generator": self.row.generator,
            "label": self.row.label,
            "clean": self.row.clean,
            "applicable": self.applicable,
            "detected": self.detected,
            "earliest_firing_step": self.earliest_firing_step,
            "checkable_equalities": len(self.findings),
            "violating_findings": len(self.violating),
        }


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_rows(data_dir: Path) -> tuple[tuple[ProcessRow, ...], dict[str, object]]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:  # pragma: no cover - environment contract
        raise RuntimeError("ProcessBench parquet loading requires pyarrow==21.0.0") from exc

    rows: list[ProcessRow] = []
    manifest: dict[str, object] = {}
    seen_ids: set[str] = set()
    for split in SPLITS:
        path = data_dir / f"{split}.parquet"
        if not path.is_file():
            raise FileNotFoundError(path)
        observed_sha256 = _sha256(path)
        expected = EXPECTED_FILES[split]
        if observed_sha256 != expected["sha256"]:
            raise ValueError(f"{split} parquet digest mismatch")
        table = parquet.read_table(path)
        if set(table.column_names) != EXPECTED_FIELDS:
            raise ValueError(f"{split} parquet schema mismatch: {table.column_names!r}")
        source_rows = table.to_pylist()
        if len(source_rows) != expected["rows"]:
            raise ValueError(f"{split} row-count mismatch")
        for source in source_rows:
            if set(source) != EXPECTED_FIELDS:
                raise ValueError(f"{split} row contains unknown or missing fields")
            row_id = source["id"]
            generator = source["generator"]
            problem = source["problem"]
            steps = source["steps"]
            final_answer_correct = source["final_answer_correct"]
            label = source["label"]
            if not isinstance(row_id, str) or not row_id:
                raise ValueError("row id must be non-empty text")
            if row_id in seen_ids:
                raise ValueError(f"duplicate ProcessBench id: {row_id}")
            seen_ids.add(row_id)
            if generator not in MODEL_PARAMETERS_BILLIONS:
                raise ValueError(f"unmapped ProcessBench generator: {generator!r}")
            if not isinstance(problem, str) or not problem:
                raise ValueError(f"{row_id} problem must be non-empty text")
            if (
                not isinstance(steps, list)
                or not steps
                or not all(isinstance(step, str) and step for step in steps)
            ):
                raise ValueError(f"{row_id} steps must be a non-empty string list")
            if not isinstance(final_answer_correct, bool):
                raise ValueError(f"{row_id} final_answer_correct must be bool")
            if isinstance(label, bool) or not isinstance(label, int):
                raise ValueError(f"{row_id} label must be int")
            if label < -1 or label >= len(steps):
                raise ValueError(f"{row_id} label is outside the step list")
            rows.append(
                ProcessRow(
                    split,
                    row_id,
                    generator,
                    problem,
                    tuple(steps),
                    final_answer_correct,
                    label,
                )
            )
        manifest[split] = {
            "path": str(path.resolve()),
            "sha256": observed_sha256,
            "rows": len(source_rows),
        }
    return tuple(rows), manifest


def wilson_95(successes: int, total: int) -> dict[str, object]:
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("invalid binomial counts")
    if total == 0:
        return {
            "successes": successes,
            "total": total,
            "rate": None,
            "interval_name": "Wilson two-sided 95%",
            "lower": None,
            "upper": None,
        }
    z = NormalDist().inv_cdf(0.975)
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return {
        "successes": successes,
        "total": total,
        "rate": rate,
        "interval_name": "Wilson two-sided 95%",
        "lower": max(0.0, center - radius),
        "upper": min(1.0, center + radius),
    }


def zero_failure_upper_95(total: int) -> float | None:
    if total <= 0:
        return None
    return 1.0 - 0.05 ** (1.0 / total)


def _lift(alpha: Mapping[str, object], recall: Mapping[str, object]) -> dict[str, object]:
    alpha_rate = alpha["rate"]
    recall_rate = recall["rate"]
    if alpha_rate is None or recall_rate is None:
        return {"value": None, "status": "UNDEFINED_EMPTY_CLASS"}
    if alpha_rate == 0:
        if recall_rate == 0:
            return {"value": None, "status": "UNDEFINED_ZERO_OVER_ZERO"}
        return {"value": None, "status": "INFINITE_ZERO_FALSE_FIRE"}
    return {"value": recall_rate / alpha_rate, "status": "FINITE"}


def _localization(scored: Iterable[ScoredRow]) -> dict[str, object]:
    counts = Counter({"exact": 0, "earlier": 0, "later": 0})
    for item in scored:
        if item.row.clean or not item.detected:
            continue
        firing_step = item.earliest_firing_step
        if firing_step == item.row.label:
            counts["exact"] += 1
        elif firing_step is not None and firing_step < item.row.label:
            counts["earlier"] += 1
        else:
            counts["later"] += 1
    total = sum(counts.values())
    return {
        **counts,
        "total": total,
        "classification_rule": "earliest violating equality versus first-error label",
        "underpowered": total < 30,
    }


def summarize(scored: Sequence[ScoredRow]) -> dict[str, object]:
    clean = [item for item in scored if item.row.clean]
    error = [item for item in scored if not item.row.clean]
    false_fires = sum(item.detected for item in clean)
    detected = sum(item.detected for item in error)
    alpha = wilson_95(false_fires, len(clean))
    recall = wilson_95(detected, len(error))
    applicability = wilson_95(sum(item.applicable for item in scored), len(scored))
    zero_upper = zero_failure_upper_95(len(clean)) if false_fires == 0 else None
    if not any(item.detected for item in scored):
        certificate = "VACUOUS"
    elif false_fires:
        certificate = "REJECT_FALSE_FIRES"
    elif len(clean) < MIN_CLEAN_CERTIFICATE:
        certificate = "INSUFFICIENT_CLEAN_NEGATIVES"
    elif alpha["upper"] is None or float(alpha["upper"]) > 0.01:
        certificate = "REJECT_WILSON_UPPER_ABOVE_1_PERCENT"
    elif zero_upper is None or zero_upper > 0.01:
        certificate = "REJECT_ONE_SIDED_BOUND_ABOVE_1_PERCENT"
    else:
        certificate = "ADMIT"
    return {
        "rows": len(scored),
        "clean_rows": len(clean),
        "error_rows": len(error),
        "applicability": applicability,
        "alpha": alpha,
        "recall": recall,
        "lift": _lift(alpha, recall),
        "checkable_equalities": sum(len(item.findings) for item in scored),
        "firing_rows": sum(item.detected for item in scored),
        "violating_findings": sum(len(item.violating) for item in scored),
        "localization": _localization(scored),
        "certificate": {
            "status": certificate,
            "minimum_clean_negatives": MIN_CLEAN_CERTIFICATE,
            "one_sided_exact_95_upper": zero_upper,
            "uses_label_minus_one_only": True,
        },
    }


def _average_ranks(values: Sequence[float]) -> tuple[float, ...]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position + 1
        while end < len(order) and values[order[end]] == values[order[position]]:
            end += 1
        average = (position + 1 + end) / 2
        for index in order[position:end]:
            ranks[index] = average
        position = end
    return tuple(ranks)


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 3:
        raise ValueError("correlation needs equal vectors of length at least three")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True))
    left_mass = sum((x - left_mean) ** 2 for x in left)
    right_mass = sum((y - right_mean) ** 2 for y in right)
    if left_mass == 0 or right_mass == 0:
        raise ValueError("correlation is undefined for a constant vector")
    return numerator / math.sqrt(left_mass * right_mass)


def spearman_with_p(left: Sequence[float], right: Sequence[float]) -> dict[str, object]:
    if len(left) != len(right) or len(left) < 3:
        return {"status": "NOT_IDENTIFIABLE", "reason": "FEWER_THAN_THREE_GENERATORS"}
    try:
        rho = _pearson(_average_ranks(left), _average_ranks(right))
    except ValueError as exc:
        return {"status": "NOT_IDENTIFIABLE", "reason": str(exc)}
    degrees = len(left) - 2
    if abs(rho) >= 1.0:
        p_value = 0.0
    else:
        t_squared = rho * rho * degrees / (1.0 - rho * rho)
        x = degrees / (degrees + t_squared)
        p_value = regularized_incomplete_beta(degrees / 2.0, 0.5, x)
    return {
        "status": "ASYMPTOTIC_SPEARMAN",
        "n": len(left),
        "rho": rho,
        "two_sided_p": p_value,
        "p_method": "Student-t approximation with n-2 degrees of freedom",
    }


def generator_report(scored: Sequence[ScoredRow]) -> dict[str, object]:
    grouped: dict[str, list[ScoredRow]] = defaultdict(list)
    for item in scored:
        grouped[item.row.generator].append(item)
    generators: dict[str, object] = {}
    included: list[str] = []
    excluded: list[dict[str, object]] = []
    for generator in sorted(grouped):
        summary = summarize(grouped[generator])
        clean = int(summary["clean_rows"])
        error = int(summary["error_rows"])
        eligible = clean >= MIN_GENERATOR_CLASS and error >= MIN_GENERATOR_CLASS
        generators[generator] = {
            "parameter_billions": MODEL_PARAMETERS_BILLIONS[generator],
            "eligible_for_size_association": eligible,
            **summary,
        }
        if eligible:
            included.append(generator)
        else:
            reasons = []
            if clean < MIN_GENERATOR_CLASS:
                reasons.append(f"clean<{MIN_GENERATOR_CLASS}")
            if error < MIN_GENERATOR_CLASS:
                reasons.append(f"error<{MIN_GENERATOR_CLASS}")
            excluded.append({"generator": generator, "reasons": reasons})

    x = [math.log(MODEL_PARAMETERS_BILLIONS[name]) for name in included]
    associations: dict[str, object] = {}
    for metric, path in (
        ("applicability", ("applicability", "rate")),
        ("alpha", ("alpha", "rate")),
        ("recall", ("recall", "rate")),
    ):
        y = [float(generators[name][path[0]][path[1]]) for name in included]
        associations[metric] = spearman_with_p(x, y)
    finite_lifts = [name for name in included if generators[name]["lift"]["status"] == "FINITE"]
    if len(finite_lifts) == len(included):
        associations["lift"] = spearman_with_p(
            x,
            [float(generators[name]["lift"]["value"]) for name in included],
        )
    else:
        associations["lift"] = {
            "status": "NOT_IDENTIFIABLE",
            "reason": "ZERO_ALPHA_MAKES_LIFT_NONFINITE",
            "nonfinite_generators": sorted(set(included) - set(finite_lifts)),
        }
    return {
        "minimum_clean_and_error": MIN_GENERATOR_CLASS,
        "included_generators": included,
        "excluded_generators": excluded,
        "generators": generators,
        "spearman_against_log_parameter_size": associations,
    }


def _audit_rows(scored: Sequence[ScoredRow]) -> tuple[dict[str, object], ...]:
    audit: list[dict[str, object]] = []
    observed_keys: set[str] = set()
    for item in scored:
        if not item.row.clean or not item.detected:
            continue
        key = f"{item.row.split}/{item.row.row_id}"
        observed_keys.add(key)
        if key not in AUDIT_FAILURE_MODES:
            raise ValueError(f"unclassified audit false fire: {key}")
        audit.append(
            {
                "split": item.row.split,
                "id": item.row.row_id,
                "generator": item.row.generator,
                "failure_mode": AUDIT_FAILURE_MODES[key],
                "findings": [finding.to_dict() for finding in item.violating],
                "step_contexts": [
                    item.row.steps[index]
                    for index in sorted({f.step_index for f in item.violating})
                ],
            }
        )
    stale = set(AUDIT_FAILURE_MODES) - observed_keys
    if stale:
        raise ValueError(f"manual audit map has stale rows: {sorted(stale)!r}")
    return tuple(audit)


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_report(
    rows: Sequence[ProcessRow], source_manifest: Mapping[str, object]
) -> dict[str, object]:
    stage_scores: dict[str, tuple[ScoredRow, ...]] = {}
    stage_summaries: dict[str, object] = {}
    for language in STAGES:
        scored = tuple(ScoredRow(row, extract_steps(row.steps, language=language)) for row in rows)
        stage_scores[language] = scored
        stage_summaries[language] = {
            split: summarize([item for item in scored if item.row.split == split])
            for split in SPLITS
        }

    final = stage_scores[CERTIFIED_LANGUAGE]
    final_subsets = stage_summaries[CERTIFIED_LANGUAGE]
    max_exact_upper = max(
        float(final_subsets[split]["certificate"]["one_sided_exact_95_upper"]) for split in SPLITS
    )
    max_wilson_upper = max(float(final_subsets[split]["alpha"]["upper"]) for split in SPLITS)
    statuses = {final_subsets[split]["certificate"]["status"] for split in SPLITS}
    if "VACUOUS" in statuses:
        decision = "VACUOUS"
    elif statuses == {"ADMIT"}:
        decision = "ADMIT"
    elif "REJECT_FALSE_FIRES" in statuses:
        decision = "REJECT_FALSE_FIRES"
    else:
        decision = "NOT_ADMITTED_PER_SUBSET_CERTIFICATE"

    audit = _audit_rows(stage_scores[AUDIT_LANGUAGE])
    mode_counts = Counter(row["failure_mode"] for row in audit)
    mode_examples: dict[str, object] = {}
    for row in audit:
        mode_examples.setdefault(
            row["failure_mode"],
            {
                "id": row["id"],
                "source_span": row["findings"][0]["source_span"],
            },
        )
    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "classification": "PROCESSBENCH_P05_DETERMINISTIC_ARITHMETIC_SMOKE",
        "source_manifest": dict(source_manifest),
        "scoring_boundary": {
            "clean_definition": "label == -1",
            "final_answer_correct_used": False,
            "sampling": "NONE_FULL_CORPUS_SCAN",
            "subsets_pooled_for_admission": False,
        },
        "baseline_reproduction": {
            "brief_claimed_false_fire_rows": 27,
            "rebuilt_audit_false_fire_rows": len(audit),
            "status": (
                "REPRODUCED" if len(audit) == 27 else "NOT_REPRODUCED_ORIGINAL_EXTRACTOR_ABSENT"
            ),
        },
        "false_fire_audit": {
            "schema": AUDIT_SCHEMA,
            "rows": list(audit),
            "failure_modes": {
                mode: {"count": count, "example": mode_examples[mode]}
                for mode, count in sorted(mode_counts.items())
            },
        },
        "stage_metrics": stage_summaries,
        "final_language": CERTIFIED_LANGUAGE,
        "subsets": final_subsets,
        "generator_analysis": generator_report(final),
        "admission": {
            "decision": decision,
            "bar": (
                "zero false fires, at least 299 clean negatives, Wilson two-sided 95% upper "
                "<= 1%, and one-sided exact 95% upper <= 1%, independently per subset"
            ),
            "minimum_clean_negatives_per_subset": MIN_CLEAN_CERTIFICATE,
            "max_wilson_two_sided_95_upper": max_wilson_upper,
            "max_one_sided_exact_95_upper": max_exact_upper,
            "never_pooled": True,
            "brief_boundary_note": (
                "n>=299 is sufficient for the stated one-sided exact zero-failure bound, "
                "but not for the separately stated two-sided Wilson upper<=1% bar"
            ),
        },
        "cost_and_authority": {
            "network_calls_at_runtime": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "token_spend": 0,
            "profile_writes": 0,
            "answer_mutations": 0,
            "execution_authorizations": 0,
            "promotion_changes": 0,
        },
        "raw_rows": [item.raw() for item in final],
        "non_claims": [
            "not frontier-model evidence",
            "not cross-domain evidence",
            "not a promotion or production-authority receipt",
            "not a reproduction of the missing original 27-row extractor audit",
        ],
    }
    report["report_sha256"] = _canonical_digest(report)
    return report


def _pct(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{100 * float(value):.2f}%"


def render_markdown(report: Mapping[str, object]) -> str:
    lines = [
        "# FOIL P0.5 — Certified arithmetic on ProcessBench",
        "",
        f"**Classification:** `{report['classification']}`  ",
        f"**Admission:** `{report['admission']['decision']}`  ",
        f"**Final language:** `{report['final_language']}`",
        "",
        "## Baseline audit",
        "",
        "The original `latex_eq.py` and `p0_processbench.py` named by the brief were absent ",
        "from the checkout and reachable history. The rebuilt audit-compatible extractor ",
        f"found **{report['baseline_reproduction']['rebuilt_audit_false_fire_rows']}** false-fire rows, not the brief's 27; ",
        "therefore the 27-row baseline is not claimed as reproduced.",
        "",
        "| Failure mode | Rows | Example |",
        "|---|---:|---|",
    ]
    for mode, body in report["false_fire_audit"]["failure_modes"].items():
        example = body["example"]
        span = str(example["source_span"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{mode}` | {body['count']} | `{example['id']}`: `{span}` |")

    lines.extend(
        [
            "",
            "The complete per-row dump (source span, extracted sides, exact values, and step context) ",
            "is in the JSON report and the separate audit artifact.",
            "",
            "## Final per-subset results",
            "",
            "| Subset | Applicability | α (Wilson 95%) | Recall | Lift | Localisation | Certificate |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for split in SPLITS:
        body = report["subsets"][split]
        alpha = body["alpha"]
        recall = body["recall"]
        lift = body["lift"]
        lift_text = f"{lift['value']:.2f}x" if lift["status"] == "FINITE" else lift["status"]
        loc = body["localization"]
        loc_text = f"{loc['exact']}/{loc['earlier']}/{loc['later']}"
        if loc["underpowered"]:
            loc_text += " (underpowered)"
        lines.append(
            f"| {split} | {_pct(body['applicability']['rate'])} "
            f"({body['applicability']['successes']}/{body['applicability']['total']}) | "
            f"{_pct(alpha['rate'])} [{_pct(alpha['lower'])}, {_pct(alpha['upper'])}] | "
            f"{_pct(recall['rate'])} ({recall['successes']}/{recall['total']}) | "
            f"{lift_text} | {loc_text} | `{body['certificate']['status']}` |"
        )

    lines.extend(
        [
            "",
            "Localisation is `exact / earlier / later` for the earliest violating equality. ",
            "Every split has fewer than 30 detected error rows, so localisation is underpowered.",
            "",
            "## Coverage cost of cumulative narrowing",
            "",
            "| Stage | Subset | Applicable | False fires | Detected errors |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for stage in STAGES:
        for split in SPLITS:
            body = report["stage_metrics"][stage][split]
            lines.append(
                f"| `{stage}` | {split} | {body['applicability']['successes']} "
                f"({_pct(body['applicability']['rate'])}) | {body['alpha']['successes']} | "
                f"{body['recall']['successes']} ({_pct(body['recall']['rate'])}) |"
            )

    lines.extend(
        [
            "",
            "## Generator stratification",
            "",
            "| Generator | B | clean/error | Applicability | α | Recall | Lift | Included? |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    generators = report["generator_analysis"]["generators"]
    for name, body in generators.items():
        lift = body["lift"]
        lift_text = f"{lift['value']:.2f}x" if lift["status"] == "FINITE" else lift["status"]
        lines.append(
            f"| {name} | {body['parameter_billions']:g} | "
            f"{body['clean_rows']}/{body['error_rows']} | {_pct(body['applicability']['rate'])} | "
            f"{_pct(body['alpha']['rate'])} | {_pct(body['recall']['rate'])} | "
            f"{lift_text} | {'yes' if body['eligible_for_size_association'] else 'no'} |"
        )

    lines.extend(["", "Spearman association with log parameter size:", ""])
    for metric, body in report["generator_analysis"]["spearman_against_log_parameter_size"].items():
        if body["status"] == "ASYMPTOTIC_SPEARMAN":
            lines.append(
                f"- {metric}: ρ={body['rho']:.4f}, p={body['two_sided_p']:.4f}, n={body['n']} "
                f"({body['p_method']})."
            )
        else:
            lines.append(f"- {metric}: `{body['status']}` — {body['reason']}.")
    excluded = report["generator_analysis"]["excluded_generators"]
    if excluded:
        lines.extend(["", "Excluded generators:"])
        for item in excluded:
            lines.append(f"- {item['generator']}: {', '.join(item['reasons'])}.")
    else:
        lines.extend(
            ["", "No generator was excluded; all had at least 20 clean and 20 erroneous rows."]
        )

    lines.extend(
        [
            "",
            "## Verdict",
            "",
            f"The point estimate is zero false fires on all four subsets, but the rule is **not admissible**: "
            f"the maximum Wilson two-sided 95% upper bound is {_pct(report['admission']['max_wilson_two_sided_95_upper'])} "
            f"and the maximum one-sided exact 95% upper bound is {_pct(report['admission']['max_one_sided_exact_95_upper'])}. "
            "GSM8K and OmniMath have fewer than 299 clean negatives. OlympiadBench clears 299 ",
            "but its two-sided Wilson upper bound is still above 1%; the brief's 299-case rule is ",
            "sufficient for its one-sided exact formula, not for its separately stated two-sided Wilson bar. ",
            "No subsets were pooled.",
            "",
            "This is deterministic historical/open-model smoke evidence only. It spent zero model tokens ",
            "and granted no answer, execution, or promotion authority.",
            "",
            f"Report SHA-256: `{report['report_sha256']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "benchmark_runs" / "foil_p05_processbench" / "data",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "benchmark_runs" / "foil_p05_processbench" / "p05_report.json",
    )
    parser.add_argument(
        "--audit-out",
        type=Path,
        default=ROOT / "benchmark_runs" / "foil_p05_processbench" / "false_fire_audit.json",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=ROOT / "benchmarks" / "results" / "FOIL_P05_CERTIFIED_ARITHMETIC_RESULTS.md",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    rows, manifest = load_rows(args.data_dir)
    report = build_report(rows, manifest)
    _write_json(args.audit_out, report["false_fire_audit"])
    _write_json(args.json_out, report)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.write_text(render_markdown(report), encoding="utf-8")
    print(f"rows={len(rows)}")
    print(f"decision={report['admission']['decision']}")
    print(f"report_sha256={report['report_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
