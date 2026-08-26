"""Closed, executable coverage audit for FOIL's normative SKILL contract."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "skills" / "foil" / "SKILL.md"
MAP_PATH = ROOT / "docs" / "FOIL_SPEC_CONTRACT_MAP.json"
MAP_SCHEMA = "foil.spec-contract-map.v1"
REPORT_SCHEMA = "foil.spec-contract-audit-report.v1"
ENTRY_FIELDS = {"id", "line", "section", "source_contains", "coverage", "evidence"}
COVERAGE = {"TESTED", "PARTIAL", "UNTESTABLE_AS_WRITTEN"}
MODAL_RE = re.compile(r"\b(?:must|never)\b", re.IGNORECASE)
HEADER_RE = re.compile(r"^##\s+(\d+)\.\s+(.+)$")


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _closed(row: Mapping[str, object], fields: set[str], label: str) -> None:
    if set(row) != fields:
        raise ValueError(f"{label} fields mismatch: expected {sorted(fields)}, got {sorted(row)}")


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    result: list[tuple[int, int, str]] = []
    for line_number, line in enumerate(lines, start=1):
        match = HEADER_RE.match(line)
        if match:
            result.append((line_number, int(match.group(1)), match.group(2)))
    return result


def _section_for(line_number: int, headings: list[tuple[int, int, str]]) -> int:
    eligible = [section for start, section, _ in headings if start <= line_number]
    if not eligible:
        raise ValueError(f"normative line {line_number} occurs before section 1")
    return eligible[-1]


def audit_document(
    skill_text: str,
    document: Mapping[str, object],
    *,
    root: Path = ROOT,
) -> dict[str, object]:
    _closed(document, {"schema", "source", "expected_sections", "entries"}, "map")
    if document["schema"] != MAP_SCHEMA or document["source"] != "skills/foil/SKILL.md":
        raise ValueError("unexpected contract-map identity")
    expected_sections = document["expected_sections"]
    if isinstance(expected_sections, bool) or not isinstance(expected_sections, int):
        raise TypeError("expected_sections must be int")
    lines = skill_text.splitlines()
    headings = _headings(lines)
    section_numbers = [section for _, section, _ in headings]
    if section_numbers != list(range(1, expected_sections + 1)):
        raise ValueError(f"section topology mismatch: {section_numbers}")
    modal_lines = {
        line_number
        for line_number, line in enumerate(lines, start=1)
        if MODAL_RE.search(line)
    }
    modal_occurrences = sum(
        len(MODAL_RE.findall(line)) for line in lines
    )
    entries = document["entries"]
    if not isinstance(entries, list):
        raise TypeError("entries must be a list")
    seen_ids: set[str] = set()
    seen_lines: set[int] = set()
    counts: Counter[str] = Counter()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise TypeError(f"entry {index} must be an object")
        _closed(entry, ENTRY_FIELDS, f"entry {index}")
        identifier = entry["id"]
        if not isinstance(identifier, str) or not identifier or identifier in seen_ids:
            raise ValueError("entry ids must be non-empty and unique")
        seen_ids.add(identifier)
        line_number = entry["line"]
        section = entry["section"]
        if (
            isinstance(line_number, bool) or not isinstance(line_number, int)
            or isinstance(section, bool) or not isinstance(section, int)
        ):
            raise TypeError(f"entry {identifier} line/section must be integers")
        if line_number in seen_lines:
            raise ValueError(f"duplicate normative line: {line_number}")
        seen_lines.add(line_number)
        if line_number < 1 or line_number > len(lines):
            raise ValueError(f"entry {identifier} line is out of range")
        source_contains = entry["source_contains"]
        if not isinstance(source_contains, str) or not source_contains:
            raise TypeError(f"entry {identifier} source_contains must be non-empty str")
        if source_contains not in lines[line_number - 1]:
            raise ValueError(f"entry {identifier} no longer matches source line {line_number}")
        actual_section = _section_for(line_number, headings)
        if section != actual_section:
            raise ValueError(
                f"entry {identifier} section mismatch: mapped {section}, actual {actual_section}"
            )
        coverage = entry["coverage"]
        if coverage not in COVERAGE:
            raise ValueError(f"entry {identifier} has unknown coverage {coverage!r}")
        counts[str(coverage)] += 1
        evidence = entry["evidence"]
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            raise TypeError(f"entry {identifier} evidence must be a string list")
        if coverage == "UNTESTABLE_AS_WRITTEN" and evidence:
            raise ValueError(f"entry {identifier} cannot claim evidence while untestable")
        if coverage != "UNTESTABLE_AS_WRITTEN" and not evidence:
            raise ValueError(f"entry {identifier} requires executable evidence")
        for relative in evidence:
            parsed = PurePosixPath(relative)
            if parsed.is_absolute() or ".." in parsed.parts or "__pycache__" in parsed.parts:
                raise ValueError(f"entry {identifier} has unsafe evidence path {relative!r}")
            if not (root / Path(*parsed.parts)).is_file():
                raise ValueError(f"entry {identifier} evidence does not exist: {relative}")
    if seen_lines != modal_lines:
        missing = sorted(modal_lines - seen_lines)
        extra = sorted(seen_lines - modal_lines)
        raise ValueError(f"normative coverage mismatch: missing={missing}, extra={extra}")
    clauses = len(modal_lines)
    return {
        "schema": REPORT_SCHEMA,
        "classification": "STATIC_SPEC_CONTRACT_COVERAGE_ONLY",
        "sections": expected_sections,
        "normative_modal_lines": clauses,
        "modal_word_occurrences": modal_occurrences,
        "coverage_counts": {key: counts[key] for key in sorted(COVERAGE)},
        "untestable_rate": counts["UNTESTABLE_AS_WRITTEN"] / clauses if clauses else 0.0,
        "unmapped_lines": 0,
        "extra_mapped_lines": 0,
        "skill_sha256": _digest_bytes(skill_text.encode("utf-8")),
        "non_claims": [
            "test-file existence does not prove every assertion in that file exercises the clause",
            "contract coverage does not prove learning efficacy or production behavior",
        ],
    }


def audit(skill_path: Path = SKILL_PATH, map_path: Path = MAP_PATH) -> dict[str, object]:
    skill_text = skill_path.read_text(encoding="utf-8")
    document = json.loads(map_path.read_text(encoding="utf-8"))
    return audit_document(skill_text, document, root=skill_path.parents[2])


def main() -> int:
    print(json.dumps(audit(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
