#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/index.html",
    "docs/system-field.js",
    "docs/brand/BRAND_SYSTEM.md",
    "docs/brand/CLAIMS_REGISTER.md",
    "docs/brand/NAMING_ARCHITECTURE.md",
    "docs/brand/README.md",
    "docs/brand/SOURCE_PACKAGE.md",
    "docs/brand/brand-system.json",
    "docs/brand/asset-manifest.json",
    "docs/content-provenance.json",
    "docs/visuals/APPARATUS_ASSETS.md",
    "docs/visuals/apparatus-frontispiece.svg",
    "docs/visuals/elenchion-mark.svg",
    "docs/visuals/visual-provenance.json",
    "validation/validate_soul_gauntlet_public.py",
]

# Multiword replacements first. Word boundaries prevent Canon -> canonical corruption.
MAPPING = [
    ("Elenchion Systems", "Lattice"),
    ("ELENCHION SYSTEMS", "LATTICE"),
    ("Elenchion", "Lattice"),
    ("ELENCHION", "LATTICE"),
    ("Mercury Runtime", "Quartz"),
    ("MERCURY RUNTIME", "QUARTZ"),
    ("Strategist Candidate", "Moonstone Candidate"),
    ("Formal Plane Candidate", "Zircon Candidate"),
    ("Mercury", "Quartz"),
    ("MERCURY", "QUARTZ"),
    ("Apparatus", "Prism"),
    ("APPARATUS", "PRISM"),
    ("Axis", "Diamond"),
    ("AXIS", "DIAMOND"),
    ("Canon", "Sapphire"),
    ("CANON", "SAPPHIRE"),
    ("Atlas", "Emerald"),
    ("ATLAS", "EMERALD"),
    ("Crucible", "Ruby"),
    ("CRUCIBLE", "RUBY"),
    ("Forge", "Garnet"),
    ("FORGE", "GARNET"),
    ("Chronometer", "Topaz"),
    ("CHRONOMETER", "TOPAZ"),
    ("Aegis", "Onyx"),
    ("AEGIS", "ONYX"),
    ("Sextant", "Citrine"),
    ("SEXTANT", "CITRINE"),
    ("Conclave", "Amethyst"),
    ("CONCLAVE", "AMETHYST"),
    ("Parallax", "Opal"),
    ("PARALLAX", "OPAL"),
]

SPECIAL = {
    "apparatus.brand-system.v1": "prism.brand-system.v1",
    "apparatus-brand-01": "prism-brand-01",
    "elenchion-apparatus-1": "lattice-prism-1",
    "apparatus-semantic-instrument-field": "prism-semantic-instrument-field",
    "apparatus-modular-control": "prism-modular-control",
    "mercury-pinned-runtime": "quartz-pinned-runtime",
    "mercury-checkpoint-eight": "quartz-checkpoint-eight",
    "mercury-limitations-visible": "quartz-limitations-visible",
    "parallax-adaptation-only": "opal-adaptation-only",
    "conclave-independent-review": "amethyst-independent-review",
}


def replace_text(text: str) -> str:
    for old, new in SPECIAL.items():
        text = text.replace(old, new)
    for old, new in MAPPING:
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    return text


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    touched = []
    for rel in TARGETS:
        path = ROOT / rel
        if not path.is_file():
            continue
        before = path.read_text(encoding="utf-8")
        after = replace_text(before)
        if after != before:
            path.write_text(after, encoding="utf-8", newline="\n")
            touched.append(rel)

    # Normalize machine-readable brand identifiers after the prose rename.
    brand_path = ROOT / "docs/brand/brand-system.json"
    if brand_path.is_file():
        brand = json.loads(brand_path.read_text(encoding="utf-8"))
        brand["schema"] = "prism.brand-system.v1"
        brand["brand_edition"] = "prism-brand-01"
        brand["organization"]["public_name"] = "Lattice"
        brand["product"]["public_name"] = "Prism"
        brand.setdefault("runtime", {})
        brand["runtime"].update({
            "public_name": "Quartz",
            "technical_id": "gauntlet_host",
            "status": "INTERIM_ALPHA_OBSERVATION_ONLY",
        })
        brand["evidence_boundary"] = (
            "Brand imagery, gemstone names, and historical cues never add evidential "
            "weight to technical or scientific claims."
        )
        brand_path.write_text(json.dumps(brand, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Recompute hashes for project-authored assets whose labels changed.
    manifest_path = ROOT / "docs/brand/asset-manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest:
            source = ROOT / str(item.get("source_object_id", ""))
            if source.is_file():
                item["source_file_sha256"] = digest(source)
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    visual_path = ROOT / "docs/visuals/visual-provenance.json"
    if visual_path.is_file():
        visual = json.loads(visual_path.read_text(encoding="utf-8"))
        visual["brand_edition"] = "lattice-prism-1"
        for item in visual.get("visuals", []):
            source = ROOT / str(item.get("file", ""))
            if source.is_file():
                item["source_file_sha256"] = digest(source)
        visual_path.write_text(json.dumps(visual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    content_path = ROOT / "docs/content-provenance.json"
    if content_path.is_file():
        data = json.loads(content_path.read_text(encoding="utf-8"))
        data["brand_edition"] = "lattice-prism-1"
        content_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # The old filenames remain as stable repository paths; their visible titles and
    # metadata now carry Lattice/Prism. Remove this one-shot applicator and workflow.
    shutil.rmtree(ROOT / "scripts/.prism_rebrand_unused", ignore_errors=True)
    (ROOT / "scripts/.apply_prism_gemstone_rebrand.py").unlink(missing_ok=True)
    (ROOT / ".github/workflows/apply-prism-gemstone-rebrand.yml").unlink(missing_ok=True)
    print(json.dumps({"status": "APPLIED", "touched": touched}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
