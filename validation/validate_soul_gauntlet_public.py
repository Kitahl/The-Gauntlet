#!/usr/bin/env python3
"""Mechanical public-package checks for Research Orchestrator + Process Assurance.

These checks establish source/package invariants only. They do not establish
behavioral efficacy of an executing language model.
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
readme = need("README.md")
showcase = need("docs/index.html")
settings = json.loads(need(".claude/settings.json"))
config = json.loads(need(".gauntlet.json"))

for token in ("name: soul", "Research Orchestrator", "/soul", "Portable runtime", "Process Assurance"):
    if token not in soul:
        fail(f"Research Orchestrator missing invariant token: {token}")

ops = ["frame", "audit", "costume", "derive", "self", "redirect", "refresh", "boundary", "explain", "oob"]
for op in ops:
    if f"`{op}`" not in gauntlet:
        fail(f"Process Assurance missing operation: {op}")

rows = re.findall(
    r"^\|\s*`(frame|audit|costume|derive|self|redirect|refresh|boundary|explain|oob)`\s*\|",
    gauntlet,
    re.MULTILINE,
)
if rows != ops:
    fail(f"canonical operation table mismatch: {rows}")

for token in (
    "tools/gauntlet_boundary.py",
    "tools/gauntlet_monitor.py",
    "tools/gauntlet_hook.py",
    "UNAVAILABLE",
    "stop_hook_active",
):
    if token not in gauntlet:
        fail(f"Process Assurance missing runtime invariant: {token}")

for path in (
    "tools/gauntlet_boundary.py",
    "tools/gauntlet_monitor.py",
    "tools/gauntlet_hook.py",
    "tools/gauntlet_config.py",
    "tools/verify_ledger.py",
    "tools/foil_profile.py",
    "tools/foil_assessment.py",
    "docs/RUNTIME_SETUP.md",
):
    need(path)

# Skill directories are specification-only.
for directory in (ROOT / "skills").iterdir():
    if directory.is_dir():
        names = sorted(p.name for p in directory.iterdir() if not p.name.startswith("."))
        if names != ["SKILL.md"]:
            fail(f"{directory}: expected SKILL.md only, found {names}")

# Hook wiring must be shareable and current-schema shaped.
raw_settings = json.dumps(settings)
if "${CLAUDE_PROJECT_DIR}" not in raw_settings:
    fail("hook settings do not use CLAUDE_PROJECT_DIR")
for event in ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"):
    if event not in settings.get("hooks", {}):
        fail(f"missing hook event: {event}")

state_path = str(config.get("state_dir") or "")
if not state_path or state_path.startswith(".git") or "/.git" in state_path:
    fail("runtime state must not live under .git")

# No person-specific learner prior belongs in the public FOIL specification.
for forbidden in ("Initial assessment priors remain", "Relative strengths observed so far"):
    if forbidden in foil:
        fail(f"person-specific FOIL prior leaked into public skill: {forbidden}")

for token in (
    "Evidence-Governed Research Toolkit",
    "Research Orchestrator",
    "Process Assurance Framework",
    "FOIL — Adaptive Reasoning Complement",
):
    if token not in readme:
        fail(f"README missing professional public terminology: {token}")
if "<strong>10</strong>" not in showcase or "Research Orchestrator" not in showcase:
    fail("showcase architecture/module count is not synchronized")

print("PASS: Research Orchestrator + Process Assurance public invariants")
print("PASS: 10 canonical Process Assurance operations")
print("PASS: portable hook/runtime wiring")
print("PASS: SKILL.md-only module directories")
print("PASS: public FOIL contains no embedded user profile")
