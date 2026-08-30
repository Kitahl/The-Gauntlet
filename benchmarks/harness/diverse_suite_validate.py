from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "benchmark_runs" / "2026-08-22"
OUT.mkdir(parents=True, exist_ok=True)

MANIFEST_PATH = ROOT / "benchmarks" / "DIVERSE_PAIRED_SUITE_MANIFEST.json"
PROTOCOL_PATH = ROOT / "benchmarks" / "PAIRED_DIVERSE_SUITE_PROTOCOL.md"
GENERAL_PROFILE_PATH = ROOT / "benchmarks" / "profiles" / "GENERAL_BENCHMARK_PROFILE_V1.json"
BROWSECOMP_PROFILE_PATH = ROOT / "benchmarks" / "profiles" / "BROWSECOMP_BENCHMARK_PROFILE.json"

GENERAL_PROFILE_FREEZE = "124c06b173ba6eff2fe0d23660a1ced8b7b975c2"
BROWSECOMP_PROFILE_FREEZE = "013a728bfd6f57a8592fc3fc6e098ea52da357d5"

EXPECTED_BENCHMARKS = (
    "browsecomp",
    "frames",
    "webwalkerqa",
    "freshqa",
    "hle",
    "gpqa_diamond",
    "arc_agi_2",
    "hotpotqa",
    "musique",
    "drop",
)
EXPECTED_CONDITIONS = (
    "BASE",
    "FOIL",
    "FOIL_GENERAL_PROFILE",
    "FOIL_MM",
)
OPEN_WEB_REGIMES = {"open_web"}
CLOSED_REGIMES = {"closed_book_text", "closed_book_multiple_choice", "closed_context_grid", "closed_context"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    general_profile = json.loads(GENERAL_PROFILE_PATH.read_text(encoding="utf-8"))
    json.loads(BROWSECOMP_PROFILE_PATH.read_text(encoding="utf-8"))

    require(manifest.get("schema") == "foil-diverse-paired-suite-manifest/v1", "unexpected manifest schema")
    require(manifest.get("status") == "prospective_unscored", "suite must remain prospective_unscored until predictions exist")
    require(manifest.get("model") == "GPT-5.6 Sol", "model drift from preregistered target")
    require(tuple(manifest.get("conditions", [])) == EXPECTED_CONDITIONS, "condition set/order drift")
    require(int(manifest.get("items_per_benchmark", -1)) == 10, "diversity screen must use 10 items per benchmark")
    require(int(manifest.get("benchmark_count", -1)) == 10, "diversity screen must contain 10 benchmarks")

    general = manifest.get("general_profile", {})
    browsecomp = manifest.get("browsecomp_profile", {})
    require(general.get("freeze_commit") == GENERAL_PROFILE_FREEZE, "general-profile freeze SHA drift")
    require(browsecomp.get("freeze_commit") == BROWSECOMP_PROFILE_FREEZE, "BrowseComp-profile freeze SHA drift")
    require(general.get("path") == "benchmarks/profiles/GENERAL_BENCHMARK_PROFILE_V1.json", "general-profile path drift")
    require(browsecomp.get("path") == "benchmarks/profiles/BROWSECOMP_BENCHMARK_PROFILE.json", "BrowseComp-profile path drift")
    require(general_profile.get("created_before_new_suite_item_exposure") is True, "general profile is not marked pre-exposure")
    require(general_profile.get("schema") == "foil-general-benchmark-profile/v1", "unexpected general-profile schema")

    benchmarks = list(manifest.get("benchmarks", []))
    ids = tuple(str(row.get("id")) for row in benchmarks)
    require(ids == EXPECTED_BENCHMARKS, f"benchmark registry drift: {ids!r}")
    require(len(set(ids)) == 10, "benchmark IDs must be unique")
    families = [str(row.get("task_family", "")).strip() for row in benchmarks]
    require(all(families), "every benchmark needs a task-family rationale")
    require(len(set(families)) == 10, "task-family descriptions must remain distinct")

    for row in benchmarks:
        benchmark_id = str(row["id"])
        source = str(row.get("source", ""))
        require(source.startswith("https://"), f"{benchmark_id}: source must be an HTTPS provenance URL")
        require(str(row.get("source_authority", "")).strip() != "", f"{benchmark_id}: missing source authority")
        require(str(row.get("license_or_terms", "")).strip() != "", f"{benchmark_id}: missing license/terms note")
        require(str(row.get("scoring", "")).strip() != "", f"{benchmark_id}: missing scoring contract")
        require(row.get("adapter_status") in {"planned", "implemented_in_browsecomp_paired40_prepare_score"}, f"{benchmark_id}: invalid adapter status")

        regime = str(row.get("regime", ""))
        budget = row.get("budget", {})
        searches = int(budget.get("max_search_queries", -1))
        followups = int(budget.get("max_source_followups", -1))
        if regime in OPEN_WEB_REGIMES:
            require(searches == 12 and followups == 12, f"{benchmark_id}: open-web budget must remain 12/12")
        elif regime in CLOSED_REGIMES:
            require(searches == 0 and followups == 0, f"{benchmark_id}: closed regime must not receive web budget")
        else:
            raise RuntimeError(f"{benchmark_id}: unknown regime {regime!r}")

    browsecomp_row = benchmarks[0]
    require("reuse items 0-9" in str(browsecomp_row.get("selection", "")), "BrowseComp diversity reuse contract drift")

    diversity_units = len(benchmarks) * int(manifest["items_per_benchmark"]) * len(EXPECTED_CONDITIONS)
    require(diversity_units == 400, f"diversity execution count should be 400, got {diversity_units}")
    require(int(manifest.get("diversity_execution_units", -1)) == diversity_units, "manifest diversity unit count drift")
    require(int(manifest.get("browsecomp_paired40_execution_units", -1)) == 200, "paired BrowseComp-40 must be 200 units")
    require(int(manifest.get("browsecomp_reused_execution_units", -1)) == 40, "BrowseComp reuse must account for 40 units")
    unique_units = 200 + diversity_units - 40
    require(unique_units == 560, f"unique execution count should be 560, got {unique_units}")
    require(int(manifest.get("total_unique_execution_units", -1)) == unique_units, "manifest unique execution count drift")

    for required_phrase in (
        "fresh isolated model context",
        "unique `isolation_session_id`",
        "No gold is revealed until",
        "not official leaderboard submissions",
    ):
        require(required_phrase.casefold() in protocol.casefold(), f"protocol missing release-critical phrase: {required_phrase}")

    adapter_status = {row["id"]: row["adapter_status"] for row in benchmarks}
    planned = sorted(key for key, value in adapter_status.items() if value == "planned")
    implemented = sorted(key for key, value in adapter_status.items() if value != "planned")

    plan = {
        "schema": "foil-diverse-paired-suite-plan/v1",
        "status": "prospective_unscored",
        "model": manifest["model"],
        "general_profile_freeze_commit": GENERAL_PROFILE_FREEZE,
        "browsecomp_profile_freeze_commit": BROWSECOMP_PROFILE_FREEZE,
        "benchmark_count": len(benchmarks),
        "items_per_benchmark": manifest["items_per_benchmark"],
        "conditions": list(EXPECTED_CONDITIONS),
        "diversity_execution_units": diversity_units,
        "browsecomp_paired40_execution_units": 200,
        "browsecomp_reused_execution_units": 40,
        "total_unique_execution_units": unique_units,
        "implemented_adapters": implemented,
        "planned_adapters": planned,
        "execution_ready": len(planned) == 0,
        "score_ready": False,
        "blocking_boundary": (
            "A result cannot be produced until all adapters are frozen and all 560 unique units are executed in isolated contexts. "
            "This validator intentionally does not fabricate or partially score prospective outputs."
        ),
    }
    (OUT / "diverse_suite_plan.json").write_text(
        json.dumps(plan, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
