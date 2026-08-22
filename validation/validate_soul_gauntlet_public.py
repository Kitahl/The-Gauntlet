#!/usr/bin/env python3
"""Validate public Research Orchestrator and Process Assurance invariants.

These are source/package checks. They do not claim behavioral efficacy of an
executing language model or the complete research workflow.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def read_required(path: str) -> str:
    file_path = ROOT / path
    if not file_path.is_file():
        fail(f"missing required file: {path}")
    return file_path.read_text(encoding="utf-8")


orchestrator = read_required("skills/soul/SKILL.md")
assurance = read_required("skills/infinity-gauntlet/SKILL.md")
readme = read_required("README.md")
showcase = read_required("docs/index.html")

# Technical identifiers remain stable for backwards compatibility.
for token in ("name: soul", "/soul", "Portable runtime", "Infinity Gauntlet"):
    if token not in orchestrator:
        fail(f"Research Orchestrator missing compatibility invariant: {token}")

operations = [
    "frame",
    "audit",
    "costume",
    "derive",
    "self",
    "redirect",
    "refresh",
    "boundary",
    "explain",
    "oob",
]
for operation in operations:
    if f"`{operation}`" not in assurance:
        fail(f"Process Assurance missing operation: {operation}")

pattern = (
    r"^\|\s*\d+\s*\|\s*`(frame|audit|costume|derive|self|redirect|refresh|"
    r"boundary|explain|oob)`\s*\|"
)
table_rows = re.findall(pattern, assurance, re.MULTILINE)
if table_rows != operations:
    fail(f"canonical Process Assurance operation table mismatch: {table_rows}")

for required in (
    "PUBLIC RUNTIME CONTRACT",
    "Feature-detect",
    "UNAVAILABLE",
    "A verification must not define its own scope",
):
    if required not in assurance:
        fail(f"Process Assurance missing portability/safety invariant: {required}")

# Historical private integrations must not become public runtime dependencies.
dead_private_paths = (
    "tools/gauntlet_monitor.py",
    "tools/gauntlet_boundary.py",
    "tools/fsa_bots.py",
    "tools/scout.py",
    "tools/verify_ledger.py",
    ".claude/settings.json",
    "repo CLAUDE.md",
)
for token in dead_private_paths:
    if token in assurance:
        fail(f"private runtime dependency leaked into public assurance spec: {token}")

# Portfolio terminology and technical aliases must remain synchronized.
for token in (
    "Evidence-Governed Research Toolkit",
    "Research Orchestrator",
    "Process Assurance Framework",
    "FOIL — Adaptive Reasoning Complement",
):
    if token not in readme:
        fail(f"README missing professional public terminology: {token}")

if "<strong>10</strong>" not in showcase:
    fail("showcase module count is not 10")
for token in ("Research Orchestrator", "Process Assurance Framework", "/soul"):
    if token not in showcase:
        fail(f"showcase missing public architecture token: {token}")
if "skills/soul/SKILL.md" not in showcase:
    fail("showcase does not link the Research Orchestrator specification")

print("PASS: Research Orchestrator public package invariants")
print("PASS: 10 canonical Process Assurance operations")
print("PASS: no required private runtime paths")
print("PASS: professional naming and compatibility aliases synchronized")
