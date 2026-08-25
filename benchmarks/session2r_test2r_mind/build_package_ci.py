#!/usr/bin/env python3
"""CI adapter: reject unsafe Omni records before scoring and adapt only sampling quotas."""
from __future__ import annotations

from collections import defaultdict

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


def diverse_take(pool, count, rng):
    by_domain = defaultdict(list)
    for row in pool:
        by_domain[row["domain"]].append(row)
    for rows in by_domain.values():
        rng.shuffle(rows)
    domains = list(by_domain)
    rng.shuffle(domains)
    chosen = []
    while len(chosen) < count:
        progressed = False
        for domain in domains:
            if by_domain[domain] and len(chosen) < count:
                chosen.append(by_domain[domain].pop())
                progressed = True
        if not progressed:
            break
    if len(chosen) != count:
        raise RuntimeError(f"diverse sampler requested {count}, obtained {len(chosen)}")
    return chosen


def adaptive_select_omni(certified, rng):
    bands = []
    for label, lo, hi, desired in bp.DIFFICULTY_BANDS:
        pool = [r for r in certified if lo <= r["difficulty"] <= hi]
        bands.append({"label": label, "lo": lo, "hi": hi, "desired": desired, "pool": pool, "quota": min(desired, len(pool))})

    if sum(len(b["pool"]) for b in bands) < 50:
        raise RuntimeError(f"only {sum(len(b['pool']) for b in bands)} certified Omni records exist across target bands; need 50")

    remaining = 50 - sum(b["quota"] for b in bands)
    # Preserve the requested distribution as far as feasible, then place any shortfall
    # into harder certified bands first without changing the admission gate.
    priority = sorted(range(len(bands)), key=lambda i: (bands[i]["hi"], bands[i]["lo"]), reverse=True)
    while remaining > 0:
        progressed = False
        for i in priority:
            b = bands[i]
            if b["quota"] < len(b["pool"]) and remaining > 0:
                b["quota"] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            raise RuntimeError("unable to redistribute certified difficulty quota to reach 50")

    selected = []
    for b in bands:
        selected.extend(diverse_take(b["pool"], b["quota"], rng))
    if len({r["id"] for r in selected}) != 50:
        raise RuntimeError("adaptive Omni selection did not produce 50 unique items")
    rng.shuffle(selected)
    return selected


bp.validate_omni = fast_validate_omni
bp.select_omni = adaptive_select_omni

if __name__ == "__main__":
    bp.main()
