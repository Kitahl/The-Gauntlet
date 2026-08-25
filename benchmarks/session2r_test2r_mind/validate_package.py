#!/usr/bin/env python3
"""Independent CI certification for the generated Session 2R / Test 2R package."""
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

import build_package as bp

ROOT = Path(__file__).resolve().parent
BASE_Q = ROOT / "base" / "questions.jsonl"
MIND_Q = ROOT / "mind" / "questions.jsonl"
GOLD = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT" / "gold.jsonl"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    base = read_jsonl(BASE_Q)
    mind = read_jsonl(MIND_Q)
    gold = read_jsonl(GOLD)
    if len(base) != 90 or len(mind) != 90 or len(gold) != 90:
        raise AssertionError(f"count mismatch base={len(base)} mind={len(mind)} gold={len(gold)}")
    if BASE_Q.read_bytes() != MIND_Q.read_bytes():
        raise AssertionError("BASE and MIND question projections are not byte-identical")

    base_ids = [r["id"] for r in base]
    mind_ids = [r["id"] for r in mind]
    gold_ids = [r["id"] for r in gold]
    if base_ids != mind_ids or base_ids != gold_ids:
        raise AssertionError("ID/order mismatch across arm projections and gold")
    if len(set(base_ids)) != 90:
        raise AssertionError("duplicate selected IDs")
    contaminated = bp.CONTAMINATED_IDS.intersection(base_ids)
    if contaminated:
        raise AssertionError(f"prior contaminated IDs selected: {sorted(contaminated)}")

    forbidden_keys = {"answer", "target", "solution", "reference_answer", "reference_solution", "gold", "negative_control", "equivalent_variants"}
    for row in base + mind:
        overlap = forbidden_keys.intersection(row.keys())
        if overlap:
            raise AssertionError(f"question projection leaks forbidden keys for {row['id']}: {sorted(overlap)}")
        if row.get("section") == "primary_omni":
            if bp.HIGH_RISK_PROMPT.search(row["prompt"]):
                raise AssertionError(f"high-risk Omni request admitted: {row['id']}")
            if bp.ENDPOINT_PROMPT.search(row["prompt"]):
                raise AssertionError(f"endpoint-sensitive Omni request admitted: {row['id']}")

    sections = Counter(r["section"] for r in base)
    expected_sections = {
        "primary_omni": 50,
        "secondary_bbeh_formal": 30,
        "exploratory_bbeh_state_tracking": 10,
    }
    if dict(sections) != expected_sections:
        raise AssertionError(f"section counts wrong: {dict(sections)}")

    formal = Counter(r.get("family") for r in base if r["section"] == "secondary_bbeh_formal")
    if set(formal) != set(bp.FORMAL_FAMILIES) or any(formal[f] != 3 for f in bp.FORMAL_FAMILIES):
        raise AssertionError(f"formal BBEH stratification wrong: {dict(formal)}")
    exploratory = Counter(r.get("family") for r in base if r["section"] == "exploratory_bbeh_state_tracking")
    expected_expl = dict(zip(bp.EXPLORATORY_FAMILIES, (4, 3, 3), strict=True))
    if dict(exploratory) != expected_expl:
        raise AssertionError(f"exploratory BBEH stratification wrong: {dict(exploratory)}")

    grader = load_module(ROOT / "scoring" / "omni_grader.py", "omni_grader_cert")
    bbeh_eval = load_module(ROOT / "scoring" / "bbeh_evaluate.py", "bbeh_eval_cert")
    gold_by_id = {r["id"]: r for r in gold}

    omni_checked = 0
    bbeh_checked = 0
    for q in base:
        g = gold_by_id[q["id"]]
        if q["benchmark"] == "omni_math_rule":
            omni_checked += 1
            answer = str(g["reference_answer"])
            if not bp.is_simple_scalar(answer):
                raise AssertionError(f"non-scalar Omni gold admitted: {q['id']}")
            if not bp.request_type_ok(q["prompt"], answer):
                raise AssertionError(f"request/answer type mismatch: {q['id']}")
            if not grader.math_equal(answer, answer, timeout=True):
                raise AssertionError(f"canonical self-score failed: {q['id']}")
            boxed = bp.extract_last_boxed(str(g["reference_solution"]))
            if boxed is None or not grader.math_equal(answer, bp.normalize_answer(boxed), timeout=True):
                raise AssertionError(f"reference-solution crosscheck failed: {q['id']}")
            validation = g.get("gold_validation", {})
            for variant in validation.get("equivalent_variants", []):
                if not grader.math_equal(str(variant), answer, timeout=True):
                    raise AssertionError(f"equivalent variant failed: {q['id']}")
            negative = str(validation.get("negative_control", ""))
            if not negative or grader.math_equal(negative, answer, timeout=True):
                raise AssertionError(f"negative-control check failed: {q['id']}")
        else:
            bbeh_checked += 1
            target = str(g["target"])
            if not bbeh_eval.evaluate_correctness(f"The final answer is: {target}", target):
                raise AssertionError(f"BBEH canonical target failed: {q['id']}")
            negative = str(g.get("gold_validation", {}).get("negative_control", ""))
            if not negative or bbeh_eval.evaluate_correctness(f"The final answer is: {negative}", target):
                raise AssertionError(f"BBEH negative control failed: {q['id']}")

    if omni_checked != 50 or bbeh_checked != 40:
        raise AssertionError(f"unexpected checked counts omni={omni_checked} bbeh={bbeh_checked}")

    manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
    report = json.loads((ROOT / "VALIDATION_REPORT.json").read_text(encoding="utf-8"))
    if manifest.get("GOLD_VALIDATED") is not True or report.get("GOLD_VALIDATED") is not True:
        raise AssertionError("public certification flag is not TRUE")

    certification = {
        "experiment_id": bp.EXPERIMENT_ID,
        "GOLD_VALIDATED": True,
        "certification_stage": "independent_post_generation_ci_validation",
        "base_mind_question_files_byte_identical": True,
        "selected_ids_unique": True,
        "prior_test2_ids_excluded": True,
        "question_projection_gold_leak_check": "PASS",
        "omni_records_revalidated": omni_checked,
        "bbeh_records_revalidated": bbeh_checked,
        "formal_bbeh_family_counts": dict(sorted(formal.items())),
        "exploratory_bbeh_family_counts": dict(sorted(exploratory.items())),
        "canonical_self_tests": "PASS",
        "reference_solution_crosschecks": "PASS",
        "equivalent_variant_tests": "PASS",
        "negative_control_tests": "PASS",
        "answer_type_checks": "PASS",
        "high_risk_omni_admission_checks": "PASS",
    }
    bp.write_json(ROOT / "CI_CERTIFICATION.json", certification)
    print(json.dumps({"GOLD_VALIDATED": True, "omni": omni_checked, "bbeh": bbeh_checked, "total": 90}, sort_keys=True))


if __name__ == "__main__":
    main()
