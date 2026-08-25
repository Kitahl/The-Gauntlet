#!/usr/bin/env python3
"""Build Session 2R / Test 2R with pre-certified gold and isolated arm projections."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

EXPERIMENT_ID = "SESSION2R_TEST2R_MIND"
SEED = 2026082502
ROOT = Path(__file__).resolve().parent
BASE_DIR = ROOT / "base"
MIND_DIR = ROOT / "mind"
GOLD_DIR = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT"
SCORING_DIR = ROOT / "scoring"

MIND_BLOB_SHA = "8c27111809e390910a74b1380b9fbce12b016999"
OMNI_COMMIT = "4793415ef37d31c9cdb4e5b82dbe172f76f8cf08"
BBEH_COMMIT = "80d12ca916b7158f22293fcf3144f4d3d854d4be"
OMNI_URL = f"https://raw.githubusercontent.com/KbsdJames/omni-math-rule/{OMNI_COMMIT}/omni_math_rule.jsonl"
OMNI_GRADER_URL = f"https://raw.githubusercontent.com/KbsdJames/omni-math-rule/{OMNI_COMMIT}/evaluation/grader.py"
BBEH_URL = f"https://raw.githubusercontent.com/google-deepmind/bbeh/{BBEH_COMMIT}/bbeh/benchmark_tasks/{{family}}/task.json"
BBEH_EVAL_URL = f"https://raw.githubusercontent.com/google-deepmind/bbeh/{BBEH_COMMIT}/bbeh/evaluate.py"

FORMAL_FAMILIES = [
    "bbeh_boolean_expressions",
    "bbeh_boardgame_qa",
    "bbeh_causal_understanding",
    "bbeh_dyck_languages",
    "bbeh_multistep_arithmetic",
    "bbeh_temporal_sequences",
    "bbeh_web_of_lies",
    "bbeh_zebra_puzzles",
    "bbeh_buggy_tables",
    "bbeh_spatial_reasoning",
]
EXPLORATORY_FAMILIES = [
    "bbeh_object_properties",
    "bbeh_shuffled_objects",
    "bbeh_object_counting",
]
DIFFICULTY_BANDS = [
    ("d6", 6.0, 6.49, 10),
    ("d6_5", 6.5, 6.99, 10),
    ("d7", 7.0, 7.49, 10),
    ("d7_5", 7.5, 7.99, 10),
    ("d8plus", 8.0, 10.0, 10),
]

# All 40 IDs from the invalid Session 2 / Test 2 package are permanently excluded.
CONTAMINATED_IDS = {
    "omni_rule_0725","omni_rule_0907","omni_rule_2754","omni_rule_0439","omni_rule_2572",
    "omni_rule_2583","omni_rule_2820","omni_rule_0286","omni_rule_1033","omni_rule_2727",
    "omni_rule_0332","omni_rule_0930","omni_rule_2755","omni_rule_1036","omni_rule_2811",
    "omni_rule_0882","omni_rule_2752","omni_rule_0014","omni_rule_0977","omni_rule_1057",
    "bbeh_boolean_expressions_0187","bbeh_causal_understanding_0029","bbeh_disambiguation_qa_0027",
    "bbeh_dyck_languages_0127","bbeh_multistep_arithmetic_0056","bbeh_object_properties_0073",
    "bbeh_shuffled_objects_0131","bbeh_movie_recommendation_0093","bbeh_time_arithmetic_0105",
    "bbeh_web_of_lies_0164","bbeh_boolean_expressions_0152","bbeh_causal_understanding_0132",
    "bbeh_disambiguation_qa_0017","bbeh_dyck_languages_0142","bbeh_multistep_arithmetic_0084",
    "bbeh_object_properties_0005","bbeh_shuffled_objects_0182","bbeh_movie_recommendation_0005",
    "bbeh_time_arithmetic_0091","bbeh_web_of_lies_0146",
}
CONTAMINATED_IDS |= {"omni_rule_1036", "omni_rule_0882", "omni_rule_0014", "omni_rule_1057"}

IMAGE_MARKERS = (
    "\\includegraphics", "[asy]", "the figure below", "shown in the figure",
    "refer to the figure", "as shown in the diagram", "see the diagram",
)
HIGH_RISK_PROMPT = re.compile(
    r"\b(construct|construction|give an example|exhibit|draw|sketch|prove|show that|"
    r"find all|determine all|classify all|describe all|solution set|set of all|"
    r"range of|interval|region|locus|all possible)\b",
    re.I,
)
ENDPOINT_PROMPT = re.compile(
    r"(\\le|\\ge|≤|≥|<|>|strictly|at most|at least|inequalit|endpoint|open interval|closed interval)",
    re.I,
)


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Gauntlet-Test2R-Builder/1.0"})
    with urllib.request.urlopen(req, timeout=180) as response:
        return response.read()


def load_jsonl(raw: bytes) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"line {line_no}: expected object")
        row["_source_index"] = line_no
        rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def domain_text(value: Any) -> str:
    if isinstance(value, list):
        return " | ".join(str(x).strip() for x in value if str(x).strip()) or "unknown"
    return str(value or "unknown").strip() or "unknown"


def extract_last_boxed(text: str) -> str | None:
    starts = [m.start() for m in re.finditer(r"\\boxed\{", text)]
    for start in reversed(starts):
        pos = start + len(r"\boxed{")
        depth = 1
        out = []
        i = pos
        while i < len(text):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return "".join(out).strip()
            out.append(ch)
            i += 1
    return None


def normalize_answer(answer: str) -> str:
    s = answer.strip()
    if s.startswith("$") and s.endswith("$") and len(s) >= 2:
        s = s[1:-1].strip()
    if s.startswith(r"\boxed{") and s.endswith("}"):
        boxed = extract_last_boxed(s)
        if boxed:
            s = boxed
    return s.strip()


def is_simple_scalar(answer: str) -> bool:
    s = normalize_answer(answer)
    if not s or len(s) > 180:
        return False
    if s.lower() in {"yes", "no", r"\text{yes}", r"\text{no}"}:
        return True
    banned = (
        r"\begin{cases}", r"\cup", r"\cap", r"\le", r"\ge", r"\infty",
        "[", "]", ";", "≤", "≥", "<", ">", " iff ", " if ", "\\text{if",
    )
    if any(token in s for token in banned):
        return False
    if "," in s or "=" in s:
        return False
    scrub = re.sub(
        r"\\(frac|sqrt|dfrac|tfrac|pi|cdot|times|left|right|operatorname|text|mathrm|overline|"
        r"sin|cos|tan|log|ln|exp|floor|ceil)\b",
        "",
        s,
        flags=re.I,
    )
    scrub = re.sub(r"\b(pi|e)\b", "", scrub, flags=re.I)
    scrub = re.sub(r"\\[A-Za-z]+", "", scrub)
    if re.search(r"[A-Za-z]", scrub):
        return False
    return True


def equivalent_variants(answer: str) -> list[str]:
    s = normalize_answer(answer)
    variants = []
    simplified = s.replace(r"\left", "").replace(r"\right", "")
    if simplified != s:
        variants.append(simplified)
    if re.fullmatch(r"-?\d+", s):
        n = int(s)
        variants.extend([f"{n}.0", rf"\frac{{{n}}}{{1}}"])
    m = re.fullmatch(r"\\(?:dfrac|tfrac|frac)\{(-?\d+)\}\{(\d+)\}", s)
    if m:
        frac = Fraction(int(m.group(1)), int(m.group(2)))
        variants.append(f"{float(frac):.12g}")
    if s.lower() in {"yes", "no"}:
        variants.append(s.upper())
    return list(dict.fromkeys(v for v in variants if v != s))


def request_type_ok(problem: str, answer: str) -> bool:
    low = problem.lower()
    a = normalize_answer(answer).lower()
    if re.search(r"\b(does there exist|is there|is it possible|can there|can one)\b", low):
        return a in {"yes", "no", r"\text{yes}", r"\text{no}"}
    return is_simple_scalar(answer)


def validate_omni(row: dict[str, Any], grader) -> tuple[bool, list[str], dict[str, Any] | None]:
    reasons: list[str] = []
    idx = int(row["_source_index"])
    item_id = f"omni_rule_{idx:04d}"
    problem = str(row.get("problem") or row.get("question") or "").strip()
    answer = normalize_answer(str(row.get("answer") or ""))
    solution = str(row.get("solution") or "").strip()
    try:
        difficulty = float(row.get("difficulty"))
    except (TypeError, ValueError):
        difficulty = -1.0

    if item_id in CONTAMINATED_IDS:
        reasons.append("prior_contamination")
    if not problem or not answer or not solution:
        reasons.append("missing_problem_answer_or_solution")
    if difficulty < 6.0 or difficulty > 10.0:
        reasons.append("difficulty_outside_6_10")
    if len(problem) > 10000:
        reasons.append("prompt_too_long")
    low = problem.lower()
    if any(marker.lower() in low for marker in IMAGE_MARKERS):
        reasons.append("image_dependent")
    if HIGH_RISK_PROMPT.search(problem):
        reasons.append("high_risk_request_form")
    if ENDPOINT_PROMPT.search(problem):
        reasons.append("endpoint_sensitive")
    if not is_simple_scalar(answer):
        reasons.append("non_scalar_or_noncanonical_answer")
    if not request_type_ok(problem, answer):
        reasons.append("request_answer_type_mismatch")

    boxed = extract_last_boxed(solution)
    if boxed is None:
        reasons.append("no_boxed_reference_in_solution")
    else:
        boxed = normalize_answer(boxed)
        try:
            if not grader.math_equal(answer, boxed, timeout=True):
                reasons.append("answer_solution_mismatch")
        except Exception:
            reasons.append("answer_solution_compare_error")

    try:
        if not grader.math_equal(answer, answer, timeout=True):
            reasons.append("canonical_self_score_failed")
    except Exception:
        reasons.append("canonical_self_score_error")

    variants = equivalent_variants(answer)
    for variant in variants:
        try:
            if not grader.math_equal(variant, answer, timeout=True):
                reasons.append("equivalent_variant_failed")
                break
        except Exception:
            reasons.append("equivalent_variant_error")
            break

    if answer.lower() in {"yes", "no", r"\text{yes}", r"\text{no}"}:
        negative = "No" if "yes" in answer.lower() else "Yes"
    else:
        negative = f"({answer})+1"
    try:
        if grader.math_equal(negative, answer, timeout=True):
            reasons.append("negative_control_false_accept")
    except Exception:
        reasons.append("negative_control_error")

    if reasons:
        return False, reasons, None

    return True, [], {
        "id": item_id,
        "benchmark": "omni_math_rule",
        "prompt": problem,
        "difficulty": difficulty,
        "domain": domain_text(row.get("domain")),
        "source": row.get("source"),
        "reference_answer": answer,
        "reference_solution": solution,
        "source_index": idx,
        "equivalent_variants_tested": variants,
        "negative_control": negative,
    }


def select_omni(certified: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for label, lo, hi, quota in DIFFICULTY_BANDS:
        pool = [r for r in certified if lo <= r["difficulty"] <= hi and r["id"] not in used_ids]
        by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in pool:
            by_domain[r["domain"]].append(r)
        for vals in by_domain.values():
            rng.shuffle(vals)
        domains = list(by_domain)
        rng.shuffle(domains)
        band: list[dict[str, Any]] = []
        for d in domains:
            if by_domain[d] and len(band) < quota:
                band.append(by_domain[d].pop())
        while len(band) < quota:
            progressed = False
            for d in domains:
                if by_domain[d] and len(band) < quota:
                    band.append(by_domain[d].pop())
                    progressed = True
            if not progressed:
                break
        if len(band) != quota:
            raise RuntimeError(
                f"Certified Omni pool insufficient in {label}: need {quota}, have {len(band)}; total eligible in band={len(pool)}"
            )
        selected.extend(band)
        used_ids.update(r["id"] for r in band)
    rng.shuffle(selected)
    return selected


def clean_bbeh_examples(payload: dict[str, Any], family: str) -> list[tuple[int, dict[str, Any]]]:
    examples = payload.get("examples")
    if not isinstance(examples, list):
        raise ValueError(f"{family}: missing examples")
    seen_inputs: set[str] = set()
    out = []
    prefix = family.removeprefix("bbeh_")
    for idx, ex in enumerate(examples):
        if not isinstance(ex, dict):
            continue
        prompt = str(ex.get("input") or "").strip()
        target = str(ex.get("target") or "").strip()
        item_id = f"bbeh_{prefix}_{idx:04d}"
        if not prompt or not target or len(prompt) > 50000:
            continue
        if item_id in CONTAMINATED_IDS:
            continue
        normalized_input = re.sub(r"\s+", " ", prompt).strip()
        if normalized_input in seen_inputs:
            continue
        seen_inputs.add(normalized_input)
        out.append((idx, ex))
    return out


def choose_bbeh_family(family: str, count: int, rng: random.Random, bbeh_eval) -> list[dict[str, Any]]:
    payload = json.loads(fetch_bytes(BBEH_URL.format(family=family)).decode("utf-8"))
    candidates = clean_bbeh_examples(payload, family)
    certified = []
    for idx, ex in candidates:
        prompt = str(ex["input"]).strip()
        target = str(ex["target"]).strip()
        if not bbeh_eval.evaluate_correctness(f"The final answer is: {target}", target):
            continue
        negative = "__gauntlet_deliberately_wrong__"
        if bbeh_eval.evaluate_correctness(f"The final answer is: {negative}", target):
            continue
        certified.append({
            "id": f"bbeh_{family.removeprefix('bbeh_')}_{idx:04d}",
            "benchmark": "bbeh",
            "family": family,
            "prompt": prompt,
            "target": target,
            "source_index": idx,
            "negative_control": negative,
        })
    if len(certified) < count:
        raise RuntimeError(f"{family}: need {count} certified examples, found {len(certified)}")
    rng.shuffle(certified)
    return certified[:count]


def projection(record: dict[str, Any], section: str, order: int) -> dict[str, Any]:
    out = {
        "id": record["id"],
        "benchmark": record["benchmark"],
        "section": section,
        "order": order,
        "prompt": record["prompt"],
    }
    for key in ("difficulty", "domain", "source", "family"):
        if key in record:
            out[key] = record[key]
    return out


def gold_record(record: dict[str, Any], section: str) -> dict[str, Any]:
    if record["benchmark"] == "omni_math_rule":
        return {
            "id": record["id"], "benchmark": record["benchmark"], "section": section,
            "reference_answer": record["reference_answer"], "reference_solution": record["reference_solution"],
            "difficulty": record["difficulty"], "domain": record["domain"], "source_index": record["source_index"],
            "gold_validation": {
                "canonical_self_score": True, "solution_crosscheck": True,
                "equivalent_variants": record["equivalent_variants_tested"],
                "negative_control": record["negative_control"], "answer_type": "simple_scalar",
            },
        }
    return {
        "id": record["id"], "benchmark": "bbeh", "section": section, "family": record["family"],
        "target": record["target"], "source_index": record["source_index"],
        "gold_validation": {"canonical_self_score": True, "negative_control": record["negative_control"]},
    }


def main() -> None:
    rng = random.Random(SEED)
    for p in (BASE_DIR, MIND_DIR, GOLD_DIR, SCORING_DIR):
        p.mkdir(parents=True, exist_ok=True)

    omni_grader_raw = fetch_bytes(OMNI_GRADER_URL)
    bbeh_eval_raw = fetch_bytes(BBEH_EVAL_URL)
    (SCORING_DIR / "omni_grader.py").write_bytes(omni_grader_raw)
    (SCORING_DIR / "bbeh_evaluate.py").write_bytes(bbeh_eval_raw)
    grader = load_module(SCORING_DIR / "omni_grader.py", "omni_grader")
    bbeh_eval = load_module(SCORING_DIR / "bbeh_evaluate.py", "bbeh_evaluate")

    omni_raw = fetch_bytes(OMNI_URL)
    omni_rows = load_jsonl(omni_raw)
    certified_omni = []
    rejection_counts: Counter[str] = Counter()
    for row in omni_rows:
        ok, reasons, rec = validate_omni(row, grader)
        if ok and rec:
            certified_omni.append(rec)
        else:
            rejection_counts.update(reasons)
    omni_selected = select_omni(certified_omni, rng)

    formal: list[dict[str, Any]] = []
    for family in FORMAL_FAMILIES:
        formal.extend(choose_bbeh_family(family, 3, rng, bbeh_eval))

    exploratory: list[dict[str, Any]] = []
    for family, count in zip(EXPLORATORY_FAMILIES, (4, 3, 3), strict=True):
        exploratory.extend(choose_bbeh_family(family, count, rng, bbeh_eval))

    rng.shuffle(formal)
    rng.shuffle(exploratory)
    items: list[tuple[str, dict[str, Any]]] = []
    items += [("primary_omni", r) for r in omni_selected]
    items += [("secondary_bbeh_formal", r) for r in formal]
    items += [("exploratory_bbeh_state_tracking", r) for r in exploratory]

    ids = [r["id"] for _, r in items]
    if len(ids) != 90 or len(set(ids)) != 90:
        raise RuntimeError(f"expected 90 unique IDs, got {len(ids)} total/{len(set(ids))} unique")
    if CONTAMINATED_IDS.intersection(ids):
        raise RuntimeError(f"contaminated IDs selected: {sorted(CONTAMINATED_IDS.intersection(ids))}")

    questions = [projection(r, section, i + 1) for i, (section, r) in enumerate(items)]
    gold = [gold_record(r, section) for section, r in items]
    write_jsonl(BASE_DIR / "questions.jsonl", questions)
    write_jsonl(MIND_DIR / "questions.jsonl", questions)
    write_jsonl(GOLD_DIR / "gold.jsonl", gold)
    (GOLD_DIR / "README.md").write_text(
        "# SEALED GOLD\n\nDo not access during BASE or MIND inference. Open only in the independent SCORE session after both immutable receipts exist.\n",
        encoding="utf-8",
    )

    assignment_manifest = {
        "experiment_id": EXPERIMENT_ID,
        "seed": SEED,
        "design": "same-item paired; independent BASE and MIND sessions; third-session scoring",
        "counts": {
            "unique_questions": 90, "primary_omni": 50, "secondary_bbeh_formal": 30,
            "exploratory_bbeh_state_tracking": 10, "base_predictions_required": 90, "mind_predictions_required": 90,
        },
        "ordered_ids": ids,
        "formal_families": FORMAL_FAMILIES,
        "exploratory_families": EXPLORATORY_FAMILIES,
        "visible_output_token_ceiling_per_item": 700,
    }
    write_json(ROOT / "assignment_manifest.json", assignment_manifest)

    difficulty_counts = Counter(str(r["difficulty"]) for r in omni_selected)
    domain_counts = Counter(r["domain"] for r in omni_selected)
    validation_report = {
        "experiment_id": EXPERIMENT_ID,
        "GOLD_VALIDATED": True,
        "gold_validation_scope": "mechanical/structural certification plus reference-solution cross-check; not an independent re-solution of every Olympiad problem",
        "omni_candidate_count": len(omni_rows),
        "omni_certified_pool_count": len(certified_omni),
        "omni_selected_count": 50,
        "omni_rejection_counts": dict(sorted(rejection_counts.items())),
        "selected_difficulty_counts": dict(sorted(difficulty_counts.items())),
        "selected_domain_count": len(domain_counts),
        "selected_ids_unique": len(set(ids)) == 90,
        "prior_test2_ids_excluded": not bool(CONTAMINATED_IDS.intersection(ids)),
        "question_projection_has_no_gold_fields": True,
        "base_mind_id_sets_identical": True,
        "base_mind_question_order_identical": True,
        "canonical_gold_self_tests_passed": True,
        "reference_solution_crosschecks_passed": True,
        "equivalent_answer_tests_passed_where_applicable": True,
        "negative_controls_passed": True,
        "request_answer_type_checks_passed": True,
        "high_risk_omni_forms_rejected_before_sampling": True,
        "bbeh_exact_duplicate_inputs_removed_before_sampling": True,
        "scorers_frozen_before_sampling": True,
    }
    write_json(ROOT / "VALIDATION_REPORT.json", validation_report)

    generated = [
        BASE_DIR / "questions.jsonl", MIND_DIR / "questions.jsonl", GOLD_DIR / "gold.jsonl", GOLD_DIR / "README.md",
        SCORING_DIR / "omni_grader.py", SCORING_DIR / "bbeh_evaluate.py", ROOT / "assignment_manifest.json", ROOT / "VALIDATION_REPORT.json",
    ]
    manifest = {
        "schema": "gauntlet.session2r.test2r.mind-package.v1",
        "experiment_id": EXPERIMENT_ID,
        "seed": SEED,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "GOLD_VALIDATED": True,
        "mind": {"repository": "Kitahl/The-Gauntlet", "path": "skills/mathbot/SKILL.md", "blob_sha": MIND_BLOB_SHA},
        "sources": {
            "omni_math_rule": {"repository": "KbsdJames/omni-math-rule", "commit": OMNI_COMMIT, "path": "omni_math_rule.jsonl", "download_sha256": sha256_bytes(omni_raw)},
            "omni_scorer": {"repository": "KbsdJames/omni-math-rule", "commit": OMNI_COMMIT, "path": "evaluation/grader.py", "sha256": sha256_bytes(omni_grader_raw)},
            "bbeh": {"repository": "google-deepmind/bbeh", "commit": BBEH_COMMIT, "formal_families": FORMAL_FAMILIES, "exploratory_families": EXPLORATORY_FAMILIES},
            "bbeh_scorer": {"repository": "google-deepmind/bbeh", "commit": BBEH_COMMIT, "path": "bbeh/evaluate.py", "sha256": sha256_bytes(bbeh_eval_raw)},
        },
        "counts": assignment_manifest["counts"],
        "visible_output_token_ceiling_per_item": 700,
        "files": {str(path.relative_to(ROOT)): {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in generated},
    }
    write_json(ROOT / "MANIFEST.json", manifest)
    (ROOT / "requirements-score.txt").write_text(
        "sympy\nregex\nlatex2sympy2\nantlr4-python3-runtime==4.11.*\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "GOLD_VALIDATED": True,
        "unique_questions": len(ids),
        "omni": len(omni_selected),
        "formal_bbeh": len(formal),
        "exploratory_bbeh": len(exploratory),
        "certified_omni_pool": len(certified_omni),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
