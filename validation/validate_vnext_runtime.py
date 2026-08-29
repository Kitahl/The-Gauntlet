#!/usr/bin/env python3
"""Mechanical validator for the typed vNext runtime candidate.

This validates architecture/wiring/privacy/source invariants only. It does not
establish behavioral efficacy or semantic correctness of future task receipts.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks: dict[str, bool] = {}

RUNTIME_FILES = [
    "tools/egrt_types.py", "tools/egrt_store.py", "tools/egrt_hook.py", "tools/egrt_runtime.py",
    "tools/egrt_challenge_types.py", "tools/egrt_challenge.py", "tools/egrt_candidate_gate.py",
    "tools/soul_runtime.py", "tools/gauntlet_runtime.py", "tools/gauntlet_automatic.py",
    "tools/meditate_runtime.py", "tools/council_runtime.py", "tools/mind_runtime.py",
    "tools/space_runtime.py", "tools/reality_runtime.py", "tools/power_runtime.py",
    "tools/time_runtime.py", "tools/foil_runtime_bridge.py", "tools/blackgem_runtime.py",
]
SPEC_FILES = [
    "docs/specs/COMMON_RUNTIME_CONTRACT.md", "docs/specs/CHALLENGE_ENGINEERING_SPEC.md",
    "docs/specs/SOUL_ENGINEERING_SPEC.md", "docs/specs/GAUNTLET_ENGINEERING_SPEC.md",
    "docs/specs/GAUNTLET_AUTOMATIC_SPEC.md", "docs/specs/MEDITATE_ENGINEERING_SPEC.md",
    "docs/specs/COUNCIL_ENGINEERING_SPEC.md", "docs/specs/MIND_ENGINEERING_SPEC.md",
    "docs/specs/SPACE_ENGINEERING_SPEC.md", "docs/specs/REALITY_ENGINEERING_SPEC.md",
    "docs/specs/POWER_ENGINEERING_SPEC.md", "docs/specs/TIME_ENGINEERING_SPEC.md",
    "docs/specs/FOIL_INTEGRATION_SPEC.md", "docs/specs/BLACKGEM_ENGINEERING_SPEC.md",
]
SKILLS = [
    "soul", "mathbot", "scoutbot", "novelbot", "codebot", "benchbot",
    "infinity-gauntlet", "meditate", "council-of-elders",
]

checks["runtime_files_present"] = all((ROOT / path).is_file() for path in RUNTIME_FILES)
checks["engineering_specs_present"] = all((ROOT / path).is_file() for path in SPEC_FILES)
checks["pipeline_present"] = (ROOT / "docs/VNEXT_RUNTIME_PIPELINE.md").is_file()

config = json.loads((ROOT / ".gauntlet.json").read_text(encoding="utf-8"))
runtime = config.get("runtime", {})
challenge = config.get("challenge", {})
checks["runtime_schema"] = runtime.get("schema") == "egrt.runtime.v1"
checks["raw_prompt_persistence_disabled"] = runtime.get("persist_raw_prompts") is False
checks["raw_tool_output_persistence_disabled"] = runtime.get("persist_raw_tool_output") is False
checks["release_gate_enabled"] = runtime.get("release_gate") is True
checks["challenge_shadow_default"] = challenge.get("mode") == "shadow"
checks["challenge_raw_text_disabled"] = challenge.get("persist_raw_text") is False
checks["challenge_budgets_bounded"] = (
    0 <= int(challenge.get("max_load_bearing_per_obligation", -1))
    <= int(challenge.get("max_total_per_obligation", -1))
    and int(challenge.get("max_selected_discriminators", -1)) >= 0
)
checks["incident_refractory_configured"] = int(config.get("boundary", {}).get("incident_refractory_turns", 0)) >= 1
checks["legacy_lifetime_budgets_removed"] = not any(key in config.get("boundary", {}) for key in ("frame_budget", "costume_budget"))

settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
raw_settings = json.dumps(settings)
checks["typed_hook_wired"] = "tools/egrt_hook.py" in raw_settings
checks["foil_hook_preserved"] = "tools/foil_hook.py" in raw_settings
checks["gauntlet_hooks_preserved"] = "tools/gauntlet_hook.py" in raw_settings and "tools/gauntlet_boundary.py" in raw_settings
checks["project_relative_hooks"] = "${CLAUDE_PROJECT_DIR}" in raw_settings

checks["skill_spec_only"] = all(
    (ROOT / "skills" / skill / "SKILL.md").is_file()
    and {p.name for p in (ROOT / "skills" / skill).iterdir() if not p.name.startswith(".")} == {"SKILL.md"}
    for skill in SKILLS
)
checks["skill_runtime_trace"] = all(
    "Typed runtime contract" in (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    for skill in SKILLS
)

forbidden = re.compile(r"(?:^|[\\/])mastermind(?:[\\/]|\.|$)|\b(?:from|import)\s+mastermind\b", re.I)
runtime_text = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in RUNTIME_FILES)
checks["no_mastermind_runtime_control"] = forbidden.search(runtime_text) is None

violations: list[str] = []
for path in (ROOT / "tools").glob("*.py"):
    if path.name.startswith("foil_"):
        continue
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            if name == "foil" or name.startswith("foil_") or name.startswith("foil."):
                violations.append(f"{path.name}:{node.lineno}:{name}")
checks["no_nonfoil_imports_foil"] = not violations

common = (ROOT / "docs/specs/COMMON_RUNTIME_CONTRACT.md").read_text(encoding="utf-8")
checks["five_layer_contract"] = all(token in common for token in ("SPEC", "STATE", "ACTION", "RECEIPT", "VERDICT"))
checks["four_verdicts"] = all(token in common for token in ("CLEARED", "ISSUE", "UNKNOWN", "UNAVAILABLE"))
checks["integrity_not_entailment"] = "integrity" in common.lower() and "semantic entailment" in common.lower()

challenge_types = (ROOT / "tools/egrt_challenge_types.py").read_text(encoding="utf-8")
challenge_runtime = (ROOT / "tools/egrt_challenge.py").read_text(encoding="utf-8")
checks["challenge_additive_schema"] = 'SCHEMA_VERSION = "egrt.challenge.v1"' in challenge_types
checks["challenge_fail_closed_states"] = all(
    token in challenge_types for token in ("UNRESOLVED", "UNAVAILABLE", "REFUTES_BASE", "SCOPE_SPLIT")
)
checks["challenge_never_domain_receipt"] = "never substitutes" in challenge_runtime.lower()

portability = (ROOT / ".github/workflows/portability.yml").read_text(encoding="utf-8")
checks["portability_always_runs"] = "    paths:\n" not in portability
checks["portability_stable_gate"] = "name: Runtime portability gate" in portability and "needs: [runtime]" in portability and "if: ${{ always() }}" in portability

checks["space_retrieval_not_warrant"] = "CANDIDATES_RETRIEVED_REVIEW_REQUIRED" in (ROOT / "tools/space_runtime.py").read_text(encoding="utf-8") and "source-assessment" in (ROOT / "tools/space_runtime.py").read_text(encoding="utf-8")
checks["council_control_matching"] = all(token in (ROOT / "tools/council_runtime.py").read_text(encoding="utf-8") for token in ("artifact_hash", "budget_hash", "CrossCritique", "DIRECT"))
checks["meditate_common_utility"] = "current_best_eu" in (ROOT / "tools/meditate_runtime.py").read_text(encoding="utf-8")
checks["power_no_shell"] = "shell=False" in (ROOT / "tools/power_runtime.py").read_text(encoding="utf-8") and "EGR_POWER_ALLOW_CUSTOM_COMMANDS" in (ROOT / "tools/power_runtime.py").read_text(encoding="utf-8")
checks["time_fixed_n_boundary"] = "not provided by this fixed-n implementation" in (ROOT / "tools/time_runtime.py").read_text(encoding="utf-8")
checks["foil_factual_boundary"] = "cannot clear non-ADAPTATION obligations" in (ROOT / "tools/foil_runtime_bridge.py").read_text(encoding="utf-8")

mind_src = (ROOT / "tools/mind_runtime.py").read_text(encoding="utf-8")
checks["mind_native_challenge"] = all(
    token in mind_src for token in (
        "FormalizationCandidate", "ProofChallengeBundle", "symbolic_equivalence_receipt",
        "exact_enumeration_receipt", "finalize_proof_bundle",
    )
)
checks["mind_scope_separate"] = "natural-formal-scope" in mind_src

blackgem_src = (ROOT / "tools/blackgem_runtime.py").read_text(encoding="utf-8")
checks["blackgem_never_clears"] = (
    'assert verdict != Verdict.CLEARED' in blackgem_src
    and blackgem_src.count("Verdict.CLEARED") == 1
)
checks["blackgem_probe_trust_separated"] = "probe_trusted" in blackgem_src and "trusted" in blackgem_src
checks["blackgem_adversary_kind_registered"] = (
    'ADVERSARY = "ADVERSARY"' in (ROOT / "tools/egrt_types.py").read_text(encoding="utf-8")
    and 'ObligationKind.ADVERSARY: "blackgem"' in (ROOT / "tools/soul_runtime.py").read_text(encoding="utf-8")
)
checks["blackgem_redteam_routing_boundary"] = (
    "routing metadata on the Black Gem receipt; never a verdict input"
    in (ROOT / "tools/foil_runtime_bridge.py").read_text(encoding="utf-8")
)

status = "PASS" if all(checks.values()) else "FAIL"
output = {"status": status, "checks": checks, "total": len(checks), "passed": sum(checks.values())}
print(json.dumps(output, indent=2))
raise SystemExit(0 if status == "PASS" else 1)
