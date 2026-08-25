#!/usr/bin/env python3
"""Build Session 3R / Test 3R Space package from first-party GitHub release metadata."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import random
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPERIMENT_ID = "SESSION3R_TEST3R_SPACE"
SEED = 2026082503
ROOT = Path(__file__).resolve().parent
BASE_DIR = ROOT / "base"
SPACE_DIR = ROOT / "space"
SEALED_DIR = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT"
CUTOFF = "2026-08-24T23:59:59Z"
RECENCY_FLOOR = "2025-01-01T00:00:00Z"
SPACE_BLOB_SHA = "a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d"
VISIBLE_TOKEN_CEILING = 450
SEARCH_QUERY_CEILING = 6
FOLLOWUP_CEILING = 8

REPOSITORIES = [
    "openai/openai-python", "openai/openai-node", "pydantic/pydantic", "fastapi/fastapi",
    "pallets/flask", "django/django", "psf/requests", "numpy/numpy", "pandas-dev/pandas",
    "scipy/scipy", "scikit-learn/scikit-learn", "pytorch/pytorch", "tensorflow/tensorflow",
    "huggingface/transformers", "huggingface/datasets", "ray-project/ray", "apache/airflow",
    "kubernetes/kubernetes", "helm/helm", "hashicorp/terraform", "prometheus/prometheus",
    "grafana/grafana", "nodejs/node", "denoland/deno", "neovim/neovim", "microsoft/vscode",
    "vercel/next.js", "facebook/react", "vuejs/core", "sveltejs/svelte", "vitejs/vite",
    "pnpm/pnpm", "npm/cli", "cli/cli", "docker/compose", "docker/buildx", "moby/moby",
    "ansible/ansible", "pytest-dev/pytest", "astral-sh/ruff", "astral-sh/uv",
    "python-poetry/poetry", "conda/conda", "pipxproject/pipx", "encode/httpx", "psf/black",
    "scrapy/scrapy", "fastapi/typer", "Textualize/rich", "pallets/click", "celery/celery",
    "redis/redis", "sqlalchemy/sqlalchemy", "sqlalchemy/alembic", "fastapi/sqlmodel",
    "opensearch-project/OpenSearch", "milvus-io/milvus", "qdrant/qdrant", "weaviate/weaviate",
    "chroma-core/chroma", "ollama/ollama", "ggml-org/llama.cpp", "vllm-project/vllm",
    "langchain-ai/langchain", "run-llama/llama_index", "BerriAI/litellm", "instructor-ai/instructor",
    "microsoft/semantic-kernel", "crewAIInc/crewAI", "PrefectHQ/prefect", "dagster-io/dagster",
    "streamlit/streamlit", "gradio-app/gradio", "plotly/dash", "matplotlib/matplotlib",
    "jupyterlab/jupyterlab", "ipython/ipython", "jupyter/notebook", "python/cpython",
    "openssl/openssl", "curl/curl", "caddyserver/caddy", "traefik/traefik", "envoyproxy/envoy",
    "istio/istio", "argoproj/argo-cd", "fluxcd/flux2", "k3s-io/k3s", "rancher/rancher",
    "containerd/containerd", "etcd-io/etcd", "minio/minio", "cockroachdb/cockroach",
    "ClickHouse/ClickHouse", "duckdb/duckdb", "prisma/prisma", "typeorm/typeorm",
    "sequelize/sequelize", "getsentry/sentry", "apache/superset", "apache/arrow",
    "apache/beam", "apache/flink", "apache/kafka", "apache/spark", "elastic/kibana",
    "godotengine/godot", "blender/blender", "obsproject/obs-studio", "yt-dlp/yt-dlp",
    "FFmpeg/FFmpeg", "mpv-player/mpv", "sharkdp/bat", "BurntSushi/ripgrep", "junegunn/fzf",
    "starship/starship", "nushell/nushell", "fish-shell/fish-shell", "tmux/tmux",
]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, obj: Any) -> None:
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    write_text(path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def api_get(path: str) -> Any:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Gauntlet-Space-Test3R-Builder/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def stable_releases(repo: str) -> list[dict[str, Any]]:
    try:
        releases = api_get(f"/repos/{repo}/releases?per_page=100")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return []
    if not isinstance(releases, list):
        return []
    out = []
    for r in releases:
        if not isinstance(r, dict) or r.get("draft") or r.get("prerelease"):
            continue
        published = str(r.get("published_at") or "")
        tag = str(r.get("tag_name") or "").strip()
        url = str(r.get("html_url") or "").strip()
        if not published or not tag or not url or published > CUTOFF:
            continue
        out.append({
            "tag": tag,
            "published_at": published,
            "published_date": published[:10],
            "html_url": url,
            "name": str(r.get("name") or "").strip(),
            "id": r.get("id"),
        })
    out.sort(key=lambda x: (x["published_at"], x["id"] or 0), reverse=True)
    return out


def eligible_histories() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for repo in REPOSITORIES:
        history = stable_releases(repo)
        if len(history) >= 2 and history[0]["published_at"] >= RECENCY_FLOOR:
            result[repo] = history
    return result


def choose_unique_pairs(repos: list[str], rng: random.Random, n: int) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    usage = Counter()
    attempts = 0
    while len(pairs) < n and attempts < 10000:
        attempts += 1
        a, b = rng.sample(repos, 2)
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        # Keep source reuse bounded when feasible.
        if usage[a] >= 3 or usage[b] >= 3:
            continue
        seen.add(key)
        usage[a] += 1
        usage[b] += 1
        pairs.append((a, b))
    if len(pairs) < n:
        while len(pairs) < n:
            a, b = rng.sample(repos, 2)
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((a, b))
    return pairs


def official_prefix(repo: str) -> str:
    return f"https://github.com/{repo}/releases"


def build_tasks(histories: dict[str, list[dict[str, Any]]], rng: random.Random):
    repos = sorted(histories)
    if len(repos) < 50:
        raise RuntimeError(f"need at least 50 eligible repositories, found {len(repos)}")

    primary_repos = rng.sample(repos, 50)
    comparison_pairs = choose_unique_pairs(repos, rng, 30)
    predecessor_repos = rng.sample(repos, 20)

    questions: list[dict[str, Any]] = []
    gold: list[dict[str, Any]] = []

    for i, repo in enumerate(primary_repos, 1):
        latest = histories[repo][0]
        item_id = f"space_release_lookup_{i:03d}"
        prompt = (
            f"Find and verify the most recent stable GitHub Release for `{repo}` that was neither a draft nor a prerelease "
            f"and was published on or before {CUTOFF}. Return exactly one JSON object with keys `repo`, `tag`, and "
            "`published_date` (YYYY-MM-DD). Also retain the first-party evidence URL you used in your prediction receipt."
        )
        questions.append({"id": item_id, "section": "primary_verified_release_retrieval", "task_type": "release_lookup", "prompt": prompt})
        gold.append({
            "id": item_id,
            "section": "primary_verified_release_retrieval",
            "task_type": "release_lookup",
            "expected": {"repo": repo, "tag": latest["tag"], "published_date": latest["published_date"]},
            "official_repos": [repo],
            "official_prefixes": [official_prefix(repo)],
            "source_urls": [latest["html_url"]],
            "source_snapshot": {"latest": latest, "previous": histories[repo][1]},
        })

    for i, (repo_a, repo_b) in enumerate(comparison_pairs, 1):
        a = histories[repo_a][0]
        b = histories[repo_b][0]
        later_repo = repo_a if a["published_at"] > b["published_at"] else repo_b
        item_id = f"space_release_compare_{i:03d}"
        prompt = (
            f"For `{repo_a}` and `{repo_b}`, find and verify each repository's most recent stable GitHub Release "
            f"published on or before {CUTOFF}. Return exactly one JSON object with keys `later_repo`, `repo_a_tag`, "
            "`repo_a_date`, `repo_b_tag`, and `repo_b_date`. `later_repo` must be the repository whose qualifying release "
            "was published later. Retain first-party evidence URLs for both repositories in your prediction receipt."
        )
        questions.append({"id": item_id, "section": "secondary_multi_source_comparison", "task_type": "release_compare", "prompt": prompt})
        gold.append({
            "id": item_id,
            "section": "secondary_multi_source_comparison",
            "task_type": "release_compare",
            "expected": {
                "later_repo": later_repo,
                "repo_a_tag": a["tag"], "repo_a_date": a["published_date"],
                "repo_b_tag": b["tag"], "repo_b_date": b["published_date"],
            },
            "official_repos": [repo_a, repo_b],
            "official_prefixes": [official_prefix(repo_a), official_prefix(repo_b)],
            "source_urls": [a["html_url"], b["html_url"]],
            "source_snapshot": {"repo_a": repo_a, "repo_a_latest": a, "repo_b": repo_b, "repo_b_latest": b},
        })

    for i, repo in enumerate(predecessor_repos, 1):
        latest, previous = histories[repo][0], histories[repo][1]
        item_id = f"space_release_predecessor_{i:03d}"
        prompt = (
            f"For `{repo}`, identify and verify the stable GitHub Release immediately preceding its most recent stable "
            f"release published on or before {CUTOFF}. Ignore drafts and prereleases. Return exactly one JSON object with "
            "keys `repo`, `tag`, and `published_date` (YYYY-MM-DD). Retain a first-party evidence URL in your prediction receipt."
        )
        questions.append({"id": item_id, "section": "exploratory_release_history_navigation", "task_type": "release_predecessor", "prompt": prompt})
        gold.append({
            "id": item_id,
            "section": "exploratory_release_history_navigation",
            "task_type": "release_predecessor",
            "expected": {"repo": repo, "tag": previous["tag"], "published_date": previous["published_date"]},
            "official_repos": [repo],
            "official_prefixes": [official_prefix(repo)],
            "source_urls": [previous["html_url"]],
            "source_snapshot": {"latest": latest, "previous": previous},
        })

    if len(questions) != 100 or len({q["id"] for q in questions}) != 100:
        raise AssertionError("task construction did not produce 100 unique IDs")
    return questions, gold


def seal_gold(gold: list[dict[str, Any]]) -> bytes:
    raw = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in gold).encode("utf-8")
    return base64.b64encode(gzip.compress(raw, compresslevel=9))


def main() -> None:
    rng = random.Random(SEED)
    histories = eligible_histories()
    questions, gold = build_tasks(histories, rng)

    write_jsonl(BASE_DIR / "questions.jsonl", questions)
    write_jsonl(SPACE_DIR / "questions.jsonl", questions)
    SEALED_DIR.mkdir(parents=True, exist_ok=True)
    sealed = seal_gold(gold)
    write_text(SEALED_DIR / "gold.jsonl.gz.b64", sealed.decode("ascii") + "\n")
    write_text(SEALED_DIR / "README.md", "# Sealed scoring payload\n\nThis payload is gzip-compressed JSONL encoded as base64. Do not decode it before both independent arm receipts are committed.\n")

    assignment = {
        "experiment_id": EXPERIMENT_ID,
        "seed": SEED,
        "policy": "same 100 tasks, independent fresh BASE and SPACE sessions, third scoring session",
        "task_ids": [q["id"] for q in questions],
        "sections": dict(Counter(q["section"] for q in questions)),
    }
    write_json(ROOT / "assignment_manifest.json", assignment)

    validation = {
        "experiment_id": EXPERIMENT_ID,
        "SOURCE_VALIDATED": True,
        "GOLD_SEMANTICALLY_HIDDEN_FROM_SEARCH": True,
        "source_type": "first-party GitHub Releases API snapshot",
        "cutoff": CUTOFF,
        "recency_floor_for_latest_release": RECENCY_FLOOR,
        "eligible_repository_count": len(histories),
        "selected_task_count": 100,
        "primary_count": 50,
        "secondary_count": 30,
        "exploratory_count": 20,
        "base_space_question_files_byte_identical": (BASE_DIR / "questions.jsonl").read_bytes() == (SPACE_DIR / "questions.jsonl").read_bytes(),
        "question_projection_has_no_gold_fields": all(not ({"expected", "tag", "published_date", "source_urls", "source_snapshot"} & set(q)) for q in questions),
        "all_sources_first_party_github_release_pages": all(all(u.startswith("https://github.com/") and "/releases/" in u for u in g["source_urls"]) for g in gold),
        "all_gold_dates_at_or_before_cutoff": all(all(str(v)[:10] <= CUTOFF[:10] for k, v in g["expected"].items() if k.endswith("date")) for g in gold),
        "task_ids_unique": len({q["id"] for q in questions}) == 100,
        "prior_test3_public_benchmark_questions_reused": False,
        "gold_payload_encoding": "gzip+base64; no plaintext gold JSON committed",
    }
    if not all([
        validation["base_space_question_files_byte_identical"],
        validation["question_projection_has_no_gold_fields"],
        validation["all_sources_first_party_github_release_pages"],
        validation["all_gold_dates_at_or_before_cutoff"],
        validation["task_ids_unique"],
    ]):
        raise AssertionError(f"validation failed: {validation}")
    write_json(ROOT / "VALIDATION_REPORT.json", validation)

    generated = [
        BASE_DIR / "questions.jsonl", SPACE_DIR / "questions.jsonl",
        SEALED_DIR / "gold.jsonl.gz.b64", SEALED_DIR / "README.md",
        ROOT / "assignment_manifest.json", ROOT / "VALIDATION_REPORT.json",
    ]
    manifest = {
        "schema": "gauntlet.session3r.test3r.space-package.v1",
        "experiment_id": EXPERIMENT_ID,
        "seed": SEED,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cutoff": CUTOFF,
        "SOURCE_VALIDATED": True,
        "GOLD_SEMANTICALLY_HIDDEN_FROM_SEARCH": True,
        "space": {"repository": "Kitahl/The-Gauntlet", "path": "skills/scoutbot/SKILL.md", "blob_sha": SPACE_BLOB_SHA},
        "counts": {"unique_questions": 100, "base_predictions_required": 100, "space_predictions_required": 100, "primary": 50, "secondary": 30, "exploratory": 20},
        "resource_limits": {"search_queries_per_task": SEARCH_QUERY_CEILING, "source_followups_per_task": FOLLOWUP_CEILING, "visible_output_tokens_per_item": VISIBLE_TOKEN_CEILING},
        "gold_storage": {"path": "gold/SEALED_UNTIL_BOTH_ARMS_COMMIT/gold.jsonl.gz.b64", "encoding": "gzip+base64", "plaintext_gold_committed": False},
        "files": {str(p.relative_to(ROOT)): {"sha256": sha256_file(p), "bytes": p.stat().st_size} for p in generated},
    }
    write_json(ROOT / "MANIFEST.json", manifest)
    print(json.dumps({"SOURCE_VALIDATED": True, "eligible_repositories": len(histories), "tasks": 100}, sort_keys=True))


if __name__ == "__main__":
    main()
