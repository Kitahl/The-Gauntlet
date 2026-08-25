#!/usr/bin/env python3
"""Mechanical public-package checks for Route + typed runtime + Assure.

These checks establish source/package/wiring invariants only. They do not establish
behavioral efficacy of an executing language model or semantic truth of receipts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def need(path: str) -> str:
    p = ROOT / path
    if not p.is_file():
        fail(f"missing required file: {path}")
    return p.read_text(encoding="utf-8")


soul = need("skills/soul/SKILL.md")
gauntlet = need("skills/infinity-gauntlet/SKILL.md")
foil = need("skills/foil/SKILL.md")
mirror = need("docs/MIRROR.md")
readme = need("README.md")
showcase = need("docs/index.html")
settings = json.loads(need(".claude/settings.json"))
config = json.loads(need(".gauntlet.json"))

# Stable technical package vocabulary remains unchanged under the public product names.
for token in ("name: soul", "Research Orchestrator", "/soul", "Portable runtime", "Process Assurance"):
    if token not in soul:
        fail(f"Route/soul compatibility source missing invariant token: {token}")

ops = ["frame", "audit", "costume", "derive", "self", "redirect", "refresh", "boundary", "explain", "oob"]
for op in ops:
    if f"`{op}`" not in gauntlet:
        fail(f"Assure/infinity-gauntlet missing operation: {op}")

rows = re.findall(
    r"^\|\s*`(frame|audit|costume|derive|self|redirect|refresh|boundary|explain|oob)`\s*\|",
    gauntlet,
    re.MULTILINE,
)
if rows != ops:
    fail(f"canonical operation table mismatch: {rows}")

for token in (
    "tools/gauntlet_boundary.py", "tools/gauntlet_monitor.py", "tools/gauntlet_hook.py",
    "UNAVAILABLE", "stop_hook_active",
):
    if token not in gauntlet:
        fail(f"Assure/infinity-gauntlet missing runtime invariant: {token}")

runtime_files = (
    "tools/egrt_types.py", "tools/egrt_store.py", "tools/egrt_hook.py", "tools/egrt_runtime.py",
    "tools/soul_runtime.py", "tools/gauntlet_runtime.py", "tools/meditate_runtime.py",
    "tools/council_runtime.py", "tools/mind_runtime.py", "tools/space_runtime.py",
    "tools/reality_runtime.py", "tools/power_runtime.py", "tools/time_runtime.py", "tools/foil_runtime_bridge.py",
    "tools/gauntlet_boundary.py", "tools/gauntlet_monitor.py", "tools/gauntlet_hook.py",
    "tools/gauntlet_config.py", "tools/verify_ledger.py", "tools/foil_profile.py",
    "tools/foil_assessment.py", "docs/RUNTIME_SETUP.md", "docs/VNEXT_RUNTIME_PIPELINE.md",
)
for path in runtime_files:
    need(path)

specs = (
    "COMMON_RUNTIME_CONTRACT.md", "SOUL_ENGINEERING_SPEC.md", "GAUNTLET_ENGINEERING_SPEC.md",
    "MEDITATE_ENGINEERING_SPEC.md", "COUNCIL_ENGINEERING_SPEC.md", "MIND_ENGINEERING_SPEC.md",
    "SPACE_ENGINEERING_SPEC.md", "REALITY_ENGINEERING_SPEC.md", "POWER_ENGINEERING_SPEC.md",
    "TIME_ENGINEERING_SPEC.md", "FOIL_INTEGRATION_SPEC.md",
)
for name in specs:
    need(f"docs/specs/{name}")

# Skill directories remain specification-only; runtime helpers never move into skills/.
for directory in (ROOT / "skills").iterdir():
    if directory.is_dir():
        names = sorted(p.name for p in directory.iterdir() if not p.name.startswith("."))
        if names != ["SKILL.md"]:
            fail(f"{directory}: expected SKILL.md only, found {names}")

raw_settings = json.dumps(settings)
if "${CLAUDE_PROJECT_DIR}" not in raw_settings:
    fail("hook settings do not use CLAUDE_PROJECT_DIR")
for event in ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"):
    if event not in settings.get("hooks", {}):
        fail(f"missing hook event: {event}")
for token in ("tools/egrt_hook.py", "tools/gauntlet_hook.py", "tools/gauntlet_boundary.py", "tools/foil_hook.py"):
    if token not in raw_settings:
        fail(f"hook settings missing typed/compatibility runtime: {token}")

state_path = str(config.get("state_dir") or "")
if not state_path or state_path.startswith(".git") or "/.git" in state_path:
    fail("runtime state must not live under .git")
runtime_cfg = config.get("runtime") or {}
if runtime_cfg.get("schema") != "egrt.runtime.v1":
    fail("typed runtime schema is not pinned to egrt.runtime.v1")
if runtime_cfg.get("persist_raw_prompts") is not False or runtime_cfg.get("persist_raw_tool_output") is not False:
    fail("generic typed runtime must not persist raw prompts/tool output")

# Mastermind must not become a runtime dependency. Historical prose may name it.
for path in runtime_files:
    text = need(path)
    if re.search(r"(^|\n)\s*(?:from|import)\s+mastermind\b", text, re.I):
        fail(f"Mastermind runtime import forbidden: {path}")

for forbidden in ("Initial assessment priors remain", "Relative strengths observed so far"):
    if forbidden in foil:
        fail(f"person-specific Adapt/legacy-foil prior leaked into public skill: {forbidden}")

# Public product names change while the legacy namespaces remain explicit so profiles,
# hooks, benchmarks, and existing integrations do not silently break.
for token in (
    "Rigilum — Instrument 01", "Route", "Assure", "Adapt",
    "technical ID / command", "working pre-product identity",
):
    if token not in readme:
        fail(f"README missing Instrument 01 public terminology or compatibility boundary: {token}")
for token in (
    "Mirror — Adaptive Reasoning Complement", "technical skill name: `foil`",
    "slash command: `/foil`", "runtime modules: `tools/foil_*`",
    "historical benchmark condition names",
):
    if token not in mirror:
        fail(f"Adapt/foil legacy compatibility contract missing token: {token}")
if showcase.count('class="tool-entry"') != 10:
    fail("showcase public module count is not synchronized")
for token in ("Rigilum", "Instrument 01", ">Route<", ">Prove<", ">Discover<", ">Synthesize<", ">Verify<", ">Measure<", ">Assure<", ">Preflight<", ">Review<", ">Adapt<"):
    if token not in showcase:
        fail(f"showcase missing Instrument 01 public name: {token}")

pipeline = need("docs/VNEXT_RUNTIME_PIPELINE.md")
for token in ("CLEARED", "ISSUE", "UNKNOWN", "UNAVAILABLE", "SPEC", "STATE", "RECEIPT", "FOIL", "Mastermind"):
    if token not in pipeline:
        fail(f"vNext pipeline missing contract token: {token}")

print("PASS: Route + typed runtime public invariants")
print("PASS: 10 canonical Assure operations + explicit support registry")
print("PASS: privacy-preserving typed hook/runtime wiring")
print("PASS: per-component engineering specifications present")
print("PASS: SKILL.md-only module directories preserved")
print("PASS: Mastermind absent from runtime imports")
print("PASS: Instrument 01 public identity + legacy runtime compatibility contract")
print("PASS: public Adapt/legacy-foil skill contains no embedded user profile")
