#!/usr/bin/env python3
"""Initialize and verify the exact Hermes gitlink used by Gauntlet's fast build."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = "NousResearch/hermes-agent"
URL = "https://github.com/NousResearch/hermes-agent.git"
TAG = "v2026.8.27"
COMMIT = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
LICENSE_HASH = "821556e6336796450ab852d375117b48a4887e71d255794fd6318d99982a5ab6"
DEST = Path("vendor/hermes-agent")
MANIFEST = Path("vendor/HERMES_SNAPSHOT.json")
NOTICE = Path("third_party/HERMES_LICENSE.txt")


class VendorError(RuntimeError):
    pass


def command(*parts: str, cwd: Path | None = None) -> str:
    try:
        done = subprocess.run(
            parts,
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        raise VendorError(f"command failed: {' '.join(parts)}\n{detail}") from exc
    return done.stdout.strip()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def root_path(value: Path | None) -> Path:
    root = value.resolve() if value else Path(__file__).resolve().parents[1]
    if not (root / "pyproject.toml").is_file() or not (root / "tools/soul_runtime.py").is_file():
        raise VendorError(f"not a Gauntlet repository root: {root}")
    return root


def manifest(root: Path) -> dict:
    path = root / MANIFEST
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VendorError(f"cannot read Hermes source manifest: {path}") from exc
    expected = {
        "schema": "gauntlet.vendor_gitlink.v1",
        "state": "gitlink",
        "upstream_repository": REPO,
        "upstream_tag": TAG,
        "upstream_commit": COMMIT,
        "upstream_url": URL,
        "destination": DEST.as_posix(),
        "license_sha256": LICENSE_HASH,
    }
    if any(data.get(key) != value for key, value in expected.items()):
        raise VendorError("Hermes source manifest pin mismatch")
    if data.get("local_modifications") != []:
        raise VendorError("Hermes source manifest must declare zero local modifications")
    return data


def verify_notice(root: Path) -> None:
    path = root / NOTICE
    if not path.is_file() or file_hash(path) != LICENSE_HASH:
        raise VendorError(f"missing or modified MIT notice: {path}")


def verify_gitmodules(root: Path) -> None:
    path = root / ".gitmodules"
    if not path.is_file():
        raise VendorError("missing .gitmodules")
    configured_path = command(
        "git", "config", "-f", str(path), "--get", "submodule.vendor/hermes-agent.path", cwd=root
    )
    configured_url = command(
        "git", "config", "-f", str(path), "--get", "submodule.vendor/hermes-agent.url", cwd=root
    )
    if configured_path != DEST.as_posix() or configured_url != URL:
        raise VendorError("Hermes .gitmodules pin mismatch")


def gitlink_sha(root: Path) -> str:
    line = command("git", "ls-files", "--stage", "--", DEST.as_posix(), cwd=root)
    if not line:
        raise VendorError("Hermes gitlink is not tracked")
    try:
        metadata, path = line.split("\t", 1)
        mode, sha, stage = metadata.split()
    except ValueError as exc:
        raise VendorError("cannot parse Hermes gitlink index entry") from exc
    if path != DEST.as_posix() or mode != "160000" or stage != "0":
        raise VendorError("vendor/hermes-agent must be a stage-0 mode-160000 gitlink")
    if sha != COMMIT:
        raise VendorError(f"Hermes gitlink is {sha}, expected {COMMIT}")
    return sha


def checkout_initialized(root: Path) -> bool:
    destination = root / DEST
    return destination.is_dir() and (destination / "LICENSE").is_file()


def verify_checkout(root: Path) -> None:
    destination = root / DEST
    if not checkout_initialized(root):
        raise VendorError(
            "Hermes submodule is not initialized; run scripts/vendor_hermes.py --init"
        )
    if command("git", "rev-parse", "HEAD^{commit}", cwd=destination) != COMMIT:
        raise VendorError("Hermes submodule HEAD is not the pinned commit")
    if command("git", "status", "--porcelain=v1", "--untracked-files=all", cwd=destination):
        raise VendorError("Hermes submodule checkout is dirty")
    if file_hash(destination / "LICENSE") != LICENSE_HASH:
        raise VendorError("Hermes submodule LICENSE hash mismatch")


def initialize(root: Path) -> None:
    verify_gitmodules(root)
    gitlink_sha(root)
    command(
        "git",
        "submodule",
        "update",
        "--init",
        "--depth",
        "1",
        "--",
        DEST.as_posix(),
        cwd=root,
    )


def verify(root: Path) -> dict:
    manifest(root)
    verify_notice(root)
    verify_gitmodules(root)
    sha = gitlink_sha(root)
    verify_checkout(root)
    return {
        "state": "verified",
        "storage": "gitlink",
        "upstream_repository": REPO,
        "upstream_tag": TAG,
        "upstream_commit": sha,
        "license_sha256": LICENSE_HASH,
        "local_modifications": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        root = root_path(args.repo_root)
        if sum(bool(value) for value in (args.init, args.verify_only, args.dry_run)) > 1:
            raise VendorError("choose only one of --init, --verify-only, or --dry-run")
        if args.dry_run:
            result = {
                "state": "planned",
                "storage": "gitlink",
                "upstream_repository": REPO,
                "upstream_tag": TAG,
                "upstream_commit": COMMIT,
                "destination": DEST.as_posix(),
            }
        else:
            if args.init:
                initialize(root)
            result = verify(root)
    except (VendorError, OSError) as exc:
        print(json.dumps({"state": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
