from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_result(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2))


def safe_div(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


def mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return None if not values else sum(values) / len(values)


def index_unique(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[tuple[Any, ...], dict[str, Any]]:
    out: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        if key in out:
            raise ValueError(f"duplicate key {key}")
        out[key] = row
    return out


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    pos = 0
    while pos < len(order):
        end = pos + 1
        while end < len(order) and values[order[end]] == values[order[pos]]:
            end += 1
        rank = (pos + 1 + end) / 2.0
        for j in range(pos, end):
            ranks[order[j]] = rank
        pos = end
    return ranks


def pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    sx = sum(v * v for v in dx)
    sy = sum(v * v for v in dy)
    if sx == 0 or sy == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / (sx * sy) ** 0.5


def spearman(x: list[float], y: list[float]) -> float | None:
    return pearson(average_ranks(x), average_ranks(y))


def group_rows(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[field])].append(row)
    return dict(grouped)
