#!/usr/bin/env python3
"""Mechanical public-package checks for Soul + Infinity Gauntlet.

This validator is deliberately source-level. It checks release invariants that
can be established without pretending to have executed an LLM behavior study.
"""
from __future__ import annotations

from pathlib import Path
import re

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
readme = need("README.md")
docs = need("docs/index.html")

# Soul must exist as an invocable public control plane.
for token in ("name: soul", "SOUL GEM", "/soul", "Portable runtime", "Infinity Gauntlet"):
    if token not in soul:
        fail(f"Soul missing invariant token: {token}")

# The portable Gauntlet has exactly the canonical ten ops and may not require
# historical private paths as runtime dependencies.
ops = ["frame","audit","costume","derive","self","redirect","refresh","boundary","explain","oob"]
for op in ops:
    if f"`{op}`" not in gauntlet:
        fail(f"Gauntlet missing operation: {op}")

table_rows = re.findall(r"^\|\s*\d+\s*\|\s*`(frame|audit|costume|derive|self|redirect|refresh|boundary|explain|oob)`\s*\|", gauntlet, re.M)
if table_rows != ops:
    fail(f"canonical operation table mismatch: {table_rows}")

for required in ("PUBLIC RUNTIME CONTRACT", "Feature-detect", "UNAVAILABLE", "A verification must not define its own scope"):
    if required not in gauntlet:
        fail(f"Gauntlet missing portability/safety invariant: {required}")

# Dead required-path regression: these historical private integrations may be
# discussed only as non-required/optional behavior. The portable skill should
# not contain them at all.
dead = (
    "tools/gauntlet_monitor.py",
    "tools/gauntlet_boundary.py",
    "tools/fsa_bots.py",
    "tools/scout.py",
    "tools/verify_ledger.py",
    ".claude/settings.json",
    "repo CLAUDE.md",
)
for token in dead:
    if token in gauntlet:
        fail(f"dead private runtime dependency leaked into portable skill: {token}")

# Public documentation must expose Soul and keep module count synchronized.
if "**SOUL / orchestrator**" not in readme:
    fail("README does not expose Soul")
if "<strong>10</strong><span>skill modules in this repository</span>" not in docs:
    fail("showcase module count is not 10")
if "/soul" not in docs:
    fail("showcase does not expose /soul")
if "skills/soul/SKILL.md" not in docs:
    fail("showcase does not link Soul skill")

print("PASS: Soul + Infinity Gauntlet public package invariants")
print("PASS: 10 canonical Gauntlet operations")
print("PASS: no required private runtime paths")
print("PASS: README/showcase Soul exposure synchronized")
