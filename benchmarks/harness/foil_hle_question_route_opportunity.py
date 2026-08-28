"""Freeze and score question-only FOIL route-opportunity predictions.

Prediction and scoring are separate commands on purpose. ``predict`` can read
only the public task manifest; ``score`` accepts the frozen prediction artifact
and the historical audit after predictions have been persisted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from foil_route_opportunity import (  # noqa: E402
    build_prediction_artifact,
    score_prediction_artifact,
)


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    predict = subparsers.add_parser("predict")
    predict.add_argument("items", type=Path)
    predict.add_argument("output", type=Path)

    score = subparsers.add_parser("score")
    score.add_argument("predictions", type=Path)
    score.add_argument("audit", type=Path)
    score.add_argument("output", type=Path)

    args = parser.parse_args()
    if args.command == "predict":
        artifact = build_prediction_artifact(_read_json(args.items))
        _write_json(args.output, artifact)
        print(artifact["prediction_sha256"])
        return 0

    report = score_prediction_artifact(
        _read_json(args.predictions),
        _read_json(args.audit),
    )
    _write_json(args.output, report)
    print(report["report_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
