#!/usr/bin/env python3
"""Canonicalize, hash, AES-256-GCM seal, and verify local benchmark gold."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

AAD = b"REALITY-EXT-BENCH-V1\n"
MAGIC = b"REXTGOLD1"


def canonical_json_bytes(obj: Any) -> bytes:
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return text.encode("utf-8")


def read_gold_directory(path: Path) -> dict[str, Any]:
    files = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix in {".json", ".jsonl"})
    if not files:
        raise SystemExit("gold directory contains no .json/.jsonl files")
    payload: dict[str, Any] = {"format": "REALITY-EXT-BENCH-V1-GOLD", "files": {}}
    for file in files:
        rel = file.relative_to(path).as_posix()
        if file.suffix == ".jsonl":
            rows = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
            payload["files"][rel] = rows
        else:
            payload["files"][rel] = json.loads(file.read_text(encoding="utf-8"))
    return payload


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold-dir", required=True)
    parser.add_argument("--ciphertext", required=True)
    parser.add_argument("--plaintext-hash", required=True)
    parser.add_argument("--ciphertext-hash", required=True)
    parser.add_argument("--key-out", default="/mnt/data/REALITY_BENCHMARK_GOLD_KEY.txt")
    args = parser.parse_args()

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise SystemExit("cryptography is required; refusing insecure fallback") from exc

    gold = read_gold_directory(Path(args.gold_dir))
    plaintext = canonical_json_bytes(gold)
    plaintext_hash = sha256_hex(plaintext)
    key = os.urandom(32)
    nonce = os.urandom(12)
    ciphertext_body = AESGCM(key).encrypt(nonce, plaintext, AAD)
    envelope = MAGIC + nonce + ciphertext_body

    # Verify before writing committed artifacts.
    if not envelope.startswith(MAGIC):
        raise SystemExit("internal envelope failure")
    recovered = AESGCM(key).decrypt(envelope[len(MAGIC) : len(MAGIC) + 12], envelope[len(MAGIC) + 12 :], AAD)
    recovered_hash = sha256_hex(recovered)
    if recovered != plaintext or recovered_hash != plaintext_hash:
        raise SystemExit("AES-GCM decrypt/hash round trip failed")

    ciphertext_path = Path(args.ciphertext)
    ciphertext_path.parent.mkdir(parents=True, exist_ok=True)
    ciphertext_path.write_bytes(envelope)
    ciphertext_hash = sha256_hex(envelope)
    write_text(Path(args.plaintext_hash), plaintext_hash)
    write_text(Path(args.ciphertext_hash), ciphertext_hash)

    key_path = Path(args.key_out)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(key.hex() + "\n", encoding="ascii", newline="\n")
    try:
        key_path.chmod(0o600)
    except OSError:
        pass

    print("ENCRYPTION=AES-256-GCM")
    print(f"PLAINTEXT_SHA256={plaintext_hash}")
    print(f"CIPHERTEXT_SHA256={ciphertext_hash}")
    print("ROUND_TRIP=PASS")
    print(f"KEY_PATH={key_path}")


if __name__ == "__main__":
    main()
