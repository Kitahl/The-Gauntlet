#!/usr/bin/env python3
"""CI adapter: reject structurally unsafe Omni records before invoking symbolic scoring."""
from __future__ import annotations

import re

import build_package as bp


def fast_validate_omni(row, grader):
    reasons = []
    idx = int(row["_source_index"])
    item_id = f"omni_rule_{idx:04d}"
    problem = str(row.get("problem") or row.get("question") or "").strip()
    answer = bp.normalize_answer(str(row.get("answer") or ""))
    solution = str(row.get("solution") or "").strip()
    try:
        difficulty = float(row.get("difficulty"))
    except (TypeError, ValueError):
        difficulty = -1.0

    if item_id in bp.CONTAMINATED_IDS:
        reasons.append("prior_contamination")
    if not problem or not answer or not solution:
        reasons.append("missing_problem_answer_or_solution")
    if difficulty < 6.0 or difficulty > 10.0:
        reasons.append("difficulty_outside_6_10")
    if len(problem) > 10000:
        reasons.append("prompt_too_long")
    low = problem.lower()
    if any(marker.lower() in low for marker in bp.IMAGE_MARKERS):
        reasons.append("image_dependent")
    if bp.HIGH_RISK_PROMPT.search(problem):
        reasons.append("high_risk_request_form")
    if bp.ENDPOINT_PROMPT.search(problem):
        reasons.append("endpoint_sensitive")
    if not bp.is_simple_scalar(answer):
        reasons.append("non_scalar_or_noncanonical_answer")
    if not bp.request_type_ok(problem, answer):
        reasons.append("request_answer_type_mismatch")
    if reasons:
        return False, reasons, None

    boxed = bp.extract_last_boxed(solution)
    if boxed is None:
        return False, ["no_boxed_reference_in_solution"], None
    boxed = bp.normalize_answer(boxed)
    try:
        if not grader.math_equal(answer, boxed, timeout=False):
            return False, ["answer_solution_mismatch"], None
        if not grader.math_equal(answer, answer, timeout=False):
            return False, ["canonical_self_score_failed"], None
    except Exception:
        return False, ["canonical_or_solution_compare_error"], None

    variants = bp.equivalent_variants(answer)
    try:
        for variant in variants:
            if not grader.math_equal(variant, answer, timeout=False):
                return False, ["equivalent_variant_failed"], None
    except Exception:
        return False, ["equivalent_variant_error"], None

    if answer.lower() in {"yes", "no", r"\text{yes}", r"\text{no}"}:
        negative = "No" if "yes" in answer.lower() else "Yes"
    else:
        negative = f"({answer})+1"
    try:
        if grader.math_equal(negative, answer, timeout=False):
            return False, ["negative_control_false_accept"], None
    except Exception:
        return False, ["negative_control_error"], None

    return True, [], {
        "id": item_id,
        "benchmark": "omni_math_rule",
        "prompt": problem,
        "difficulty": difficulty,
        "domain": bp.domain_text(row.get("domain")),
        "source": row.get("source"),
        "reference_answer": answer,
        "reference_solution": solution,
        "source_index": idx,
        "equivalent_variants_tested": variants,
        "negative_control": negative,
    }


bp.validate_omni = fast_validate_omni

if __name__ == "__main__":
    bp.main()
