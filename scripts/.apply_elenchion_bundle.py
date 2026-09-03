#!/usr/bin/env python3
"""Apply a digest-bound one-shot Apparatus brand payload to this branch."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import shutil
import zlib

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "scripts/.brand_bundle_parts"
BUNDLE_SHA256 = '0f4abac8ee309861c95888b03df15eebe5fee7cc1f62a60e527d17d6f83688b0'
EXPECTED_HASHES = {
  "README.md": "ec35581d7d4dd7a6ee7aa0a7cbc811e2e884d08d9b6ed823cc394a581f4252ee",
  "THIRD_PARTY_NOTICES.md": "bba84db1c6078897874f0fdb2dc538811661d02e6df915e20eb289492b10511d",
  "docs/brand/BRAND_SYSTEM.md": "571a2e247f15b3a7291887291bc7d15e385cccf944f60c5f868a80e3a9b0aaae",
  "docs/brand/CLAIMS_REGISTER.md": "dadafda52d0d21e6dcb75c93d10450b0a159a020c8cc111ab306cd0cd0836e6e",
  "docs/brand/NAMING_ARCHITECTURE.md": "29e4855ff76f829ba5a98593d4a5670010830b6cd97c65a152825e9532555f2b",
  "docs/brand/README.md": "19e155a2a44abf4d002fd6a62068ee829e52ce78011df82587a30d5afef2ad75",
  "docs/brand/SOURCE_PACKAGE.md": "73340d1d7f50da427d8ec182c92abbdcfe83407f63623dda98f23f276693eafd",
  "docs/brand/asset-manifest.json": "bd8c3bf34f9360952fad2a6082bf656d608356921343236be0da3bc1942026a6",
  "docs/brand/brand-system.json": "51d962a687e20adf532a03f14817a7532cad208a584eeadd79139b27b0f5acb5",
  "docs/content-provenance.json": "93c6ee235351342fc30d74166c3f761be1a801415e66262b6377cdbb7493aae3",
  "docs/index.html": "549a89dd615666a2fc5f41fdf71a8e700aedc4daa5b1741df4b007028e38b453",
  "docs/styles.css": "78ff473528b793f566379608e8d03a0a68a45556f791a3ac8183e5d9dbe9d63a",
  "docs/system-field.js": "0b415e0771cc24c4d95ec4d6c87a2be1e0a65d3fbe210402431238cb4a5ba68f",
  "docs/visuals/APPARATUS_ASSETS.md": "00f45acdd69dca4aa1260421bbd093ce1a2396e8415932302ed2216ebfe4962f",
  "docs/visuals/apparatus-frontispiece.svg": "4b91a1cc0fd8b713aca27a5fbd3555562b2392a729ab4efc7c461661bb1d14a8",
  "docs/visuals/elenchion-mark.svg": "655878c5c97c2bba9328e5031cc692ec4034aa92d89b7749ea693f20f45e3b1c",
  "docs/visuals/visual-provenance.json": "2f2bd950af99342203ae3ebfd67cf2bca5acd75e4b0a2ed5922cd18e9d9f84dd"
}


def main() -> int:
    encoded = "".join(path.read_text(encoding="ascii") for path in sorted(PARTS.glob("part-*.b85")))
    raw = zlib.decompress(base64.b85decode(encoded.encode("ascii")))
    if hashlib.sha256(raw).hexdigest() != BUNDLE_SHA256:
        raise SystemExit("bundle digest mismatch")
    payload = json.loads(raw.decode("utf-8"))
    if set(payload) != set(EXPECTED_HASHES):
        raise SystemExit("bundle path set mismatch")
    for relative, content in payload.items():
        path = (ROOT / relative).resolve()
        if ROOT.resolve() not in path.parents:
            raise SystemExit(f"unsafe output path: {relative}")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if digest != EXPECTED_HASHES[relative]:
            raise SystemExit(f"content digest mismatch: {relative}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    for relative in (
        "docs/brand/brand-system.json",
        "docs/brand/asset-manifest.json",
        "docs/content-provenance.json",
        "docs/visuals/visual-provenance.json",
    ):
        json.loads((ROOT / relative).read_text(encoding="utf-8"))

    shutil.rmtree(PARTS)
    (ROOT / "scripts/.apply_elenchion_bundle.py").unlink(missing_ok=True)
    (ROOT / ".github/workflows/apply-elenchion-brand.yml").unlink(missing_ok=True)
    print(json.dumps({"status": "APPLIED", "files": len(payload), "bundle_sha256": BUNDLE_SHA256}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
