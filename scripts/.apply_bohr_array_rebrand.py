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

SPECIAL = {
    "prism.brand-system.v1": "array.brand-system.v1",
    "prism-brand-01": "array-brand-01",
    "lattice-prism-1": "bohr-array-1",
    "prism-semantic-instrument-field": "array-semantic-instrument-field",
    "prism-modular-control": "array-modular-control",
}


def replace_brand(text: str) -> str:
    for old, new in SPECIAL.items():
        text = text.replace(old, new)
    text = re.sub(r"\bLATTICE\b", "BOHR", text)
    text = re.sub(r"\bLattice\b", "Bohr", text)
    text = re.sub(r"\bPRISM\b", "ARRAY", text)
    text = re.sub(r"\bPrism\b", "Array", text)
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
        after = replace_brand(before)
        if after != before:
            path.write_text(after, encoding="utf-8", newline="\n")
            touched.append(rel)

    # Correct the human-readable rationale after the mechanical brand substitution.
    naming_path = ROOT / "docs/brand/NAMING_ARCHITECTURE.md"
    if naming_path.is_file():
        text = naming_path.read_text(encoding="utf-8")
        text = re.sub(
            r"\*\*Bohr\*\* is selected because it is a short scientific term for an ordered structural arrangement\. \*\*Array\*\* is selected because it is a short scientific instrument/object term associated with separating a complex input into inspectable components\.",
            "**Bohr** is selected as a short, memorable scientific identity. **Array** is selected as a short scientific/computing term for an ordered collection, matching a suite composed of distinct specialist instruments.",
            text,
        )
        naming_path.write_text(text, encoding="utf-8", newline="\n")

    readme_path = ROOT / "README.md"
    if readme_path.is_file():
        text = readme_path.read_text(encoding="utf-8")
        text = text.replace(
            "| Organization | **Bohr** | One-word scientific identity: an ordered structure for research and engineering instruments |",
            "| Organization | **Bohr** | One-word scientific identity chosen for memorability and technical character |",
        )
        text = text.replace(
            "| Product suite | **Array** | One runtime, one evidence-control plane, and a portfolio of specialist gemstone instruments |",
            "| Product suite | **Array** | An ordered collection: one runtime, one evidence-control plane, and specialist gemstone instruments |",
        )
        readme_path.write_text(text, encoding="utf-8", newline="\n")

    brand_path = ROOT / "docs/brand/brand-system.json"
    if brand_path.is_file():
        brand = json.loads(brand_path.read_text(encoding="utf-8"))
        brand["schema"] = "array.brand-system.v1"
        brand["brand_edition"] = "array-brand-01"
        brand["organization"]["public_name"] = "Bohr"
        brand["product"]["public_name"] = "Array"
        brand["runtime"]["public_name"] = "Quartz"
        brand["evidence_boundary"] = (
            "Brand imagery, gemstone names, and historical or scientific cues never add "
            "evidential weight to technical or scientific claims."
        )
        brand_path.write_text(json.dumps(brand, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

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
        visual["brand_edition"] = "bohr-array-1"
        for item in visual.get("visuals", []):
            source = ROOT / str(item.get("file", ""))
            if source.is_file():
                item["source_file_sha256"] = digest(source)
        visual_path.write_text(json.dumps(visual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    content_path = ROOT / "docs/content-provenance.json"
    if content_path.is_file():
        data = json.loads(content_path.read_text(encoding="utf-8"))
        data["brand_edition"] = "bohr-array-1"
        content_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # One-shot payload: leave only the product files.
    (ROOT / "scripts/.apply_bohr_array_rebrand.py").unlink(missing_ok=True)
    (ROOT / ".github/workflows/apply-bohr-array-rebrand.yml").unlink(missing_ok=True)
    print(json.dumps({"status": "APPLIED", "touched": touched}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
