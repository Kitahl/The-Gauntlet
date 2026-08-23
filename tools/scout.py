"""Small, keyless OpenAlex prior-art lookup used by Research Discovery."""
from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path

import requests


def toolkit_version() -> str:
    try:
        return (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


UA = f"Evidence-Governed-Research-Toolkit/{toolkit_version()} (+https://github.com/Kitahl/The-Gauntlet)"


def search_openalex(query: str, limit: int = 8, timeout: float = 20.0) -> list[dict]:
    params = urllib.parse.urlencode({"search": query, "per-page": max(1, min(limit, 25))})
    r = requests.get(f"https://api.openalex.org/works?{params}", headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    out = []
    for work in r.json().get("results", [])[:limit]:
        primary = work.get("primary_location") or {}
        source = primary.get("source") or {}
        out.append({
            "title": work.get("display_name"),
            "year": work.get("publication_year"),
            "doi": work.get("doi"),
            "openalex": work.get("id"),
            "source": source.get("display_name"),
            "cited_by": work.get("cited_by_count"),
        })
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("query", nargs="+")
    p.add_argument("--limit", type=int, default=8)
    args = p.parse_args(argv)
    try:
        print(json.dumps({"query": " ".join(args.query), "results": search_openalex(" ".join(args.query), args.limit)}, indent=2))
        return 0
    except requests.RequestException as exc:
        print(json.dumps({"query": " ".join(args.query), "error": str(exc), "results": []}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
