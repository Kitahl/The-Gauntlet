#!/usr/bin/env python3
"""Materialize and verify the exact Hermes source used by Gauntlet's fast build."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
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
        done = subprocess.run(parts, cwd=cwd, check=True, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        raise VendorError(f"cannot read snapshot manifest: {path}") from exc
    expected = {"upstream_repository": REPO, "upstream_tag": TAG,
                "upstream_commit": COMMIT, "destination": DEST.as_posix(),
                "license_sha256": LICENSE_HASH}
    if any(data.get(key) != value for key, value in expected.items()):
        raise VendorError("snapshot manifest pin mismatch")
    return data


def verify_notice(root: Path) -> None:
    path = root / NOTICE
    if not path.is_file() or file_hash(path) != LICENSE_HASH:
        raise VendorError(f"missing or modified MIT notice: {path}")


def verify_checkout(source: Path) -> None:
    if command("git", "rev-parse", "HEAD^{commit}", cwd=source) != COMMIT:
        raise VendorError("source HEAD is not the pinned commit")
    if command("git", "rev-parse", f"refs/tags/{TAG}^{{commit}}", cwd=source) != COMMIT:
        raise VendorError("pinned tag does not resolve to the pinned commit")
    if command("git", "status", "--porcelain=v1", "--untracked-files=all", cwd=source):
        raise VendorError("source checkout is dirty")
    if file_hash(source / "LICENSE") != LICENSE_HASH:
        raise VendorError("upstream LICENSE hash mismatch")


def tree_hash(root: Path) -> tuple[int, str]:
    digest, count = hashlib.sha256(), 0
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix().encode()
        digest.update(relative + b"\0" + bytes.fromhex(file_hash(path)) + b"\n")
        count += 1
    return count, digest.hexdigest()


def verify(root: Path) -> dict:
    verify_notice(root)
    data, destination = manifest(root), root / DEST
    if not destination.is_dir() or (destination / ".git").exists():
        raise VendorError(f"invalid vendored tree: {destination}")
    if file_hash(destination / "LICENSE") != LICENSE_HASH:
        raise VendorError("vendored LICENSE hash mismatch")
    count, digest = tree_hash(destination)
    if data.get("state") != "materialized" or data.get("file_count") != count \
            or data.get("tree_sha256") != digest:
        raise VendorError("vendored tree does not match its manifest")
    return {"state": "verified", "upstream_commit": COMMIT,
            "file_count": count, "tree_sha256": digest,
            "license_sha256": LICENSE_HASH}


def materialize(root: Path, source: Path | None, force: bool) -> dict:
    verify_notice(root)
    data = manifest(root)
    with tempfile.TemporaryDirectory(prefix="gauntlet-hermes-") as temp:
        checkout = source.resolve() if source else Path(temp) / "checkout"
        if source is None:
            command("git", "clone", "--filter=blob:none", "--depth", "1",
                    "--branch", TAG, "--single-branch", URL, str(checkout))
        verify_checkout(checkout)
        staging = root / "vendor" / f".hermes-agent.staging-{os.getpid()}"
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(checkout, staging, symlinks=True,
                        ignore=shutil.ignore_patterns(".git"))
        count, digest = tree_hash(staging)
        destination = root / DEST
        if destination.exists() and not force:
            shutil.rmtree(staging)
            raise VendorError(f"destination exists; review and rerun with --force: {destination}")
        backup = destination.with_name(f".{destination.name}.backup-{os.getpid()}")
        if destination.exists():
            destination.rename(backup)
        try:
            staging.rename(destination)
        except BaseException:
            if backup.exists() and not destination.exists():
                backup.rename(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    data.update({"state": "materialized", "file_count": count,
                 "tree_sha256": digest, "local_modifications": [],
                 "materialized_at": datetime.now(timezone.utc).isoformat()})
    path = root / MANIFEST
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return verify(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        root = root_path(args.repo_root)
        if args.verify_only and (args.source or args.force or args.dry_run):
            raise VendorError("--verify-only cannot be combined with other actions")
        if args.dry_run:
            result = {"state": "planned", "upstream_repository": REPO,
                      "upstream_tag": TAG, "upstream_commit": COMMIT,
                      "destination": DEST.as_posix(),
                      "source": str(args.source.resolve()) if args.source else "clone pinned tag",
                      "force": args.force}
        elif args.verify_only:
            result = verify(root)
        else:
            result = materialize(root, args.source, args.force)
    except (VendorError, OSError) as exc:
        print(json.dumps({"state": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
