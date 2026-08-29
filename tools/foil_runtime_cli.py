"""CLI for question-only probing and mechanical FOIL v2 execution."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from egrt_types import digest
from foil_active_runtime_v2 import FoilRuntimePolicyV2
from foil_bounded_answer_constructor_v2 import ConstructorPolicyV2
from foil_evidence_archive import RawEvidenceArchive
from foil_evidence_contract import AnswerKind, QuestionObligation
from foil_retrieval_claim_comparator import ComparatorPolicy
from foil_route_opportunity_v2 import (
    QUESTION_SCHEMA_V2,
    RuntimeToolFamily,
    discover_route_opportunity_v2,
)
from foil_runtime_active import run_foil
from foil_runtime_token_ledger import RuntimeTokenLedger
from foil_runtime_tools_v2 import (
    ExactArithmeticAdapterV2,
    FormalDecidabilityAdapterV2,
    RestrictedPythonAdapterV2,
    SymbolicLinearAdapterV2,
)


def _input(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("input JSON must be an object")
    return value


def _persist(path: Path, value: dict[str, object]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foil-runtime")
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser("probe", help="freeze a question-only route opportunity")
    probe.add_argument("input", type=Path)
    probe.add_argument("--output", required=True, type=Path)
    run = sub.add_parser("run", help="run active mechanical FOIL v2")
    run.add_argument("input", type=Path)
    run.add_argument("--a0", required=True)
    run.add_argument("--answer-kind", choices=[item.value for item in AnswerKind], required=True)
    run.add_argument("--archive-dir", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--active-answer-change", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    raw = _input(args.input)
    if args.command == "probe":
        trace = discover_route_opportunity_v2(raw).trace()
        _persist(args.output, trace)
        print(f"stored={args.output.resolve()} status={trace['status']}")
        return 0

    if raw.get("schema") != QUESTION_SCHEMA_V2:
        raise ValueError("run input must use foil.question-only-route-input.v2")
    task_id = raw.get("task_id")
    question = raw.get("question")
    if not isinstance(task_id, str) or not isinstance(question, str):
        raise ValueError("run input requires text task_id and question")
    obligation = QuestionObligation(
        task_id,
        digest(question),
        AnswerKind(args.answer_kind),
    )
    adapters = {
        RuntimeToolFamily.EXACT_ARITHMETIC: ExactArithmeticAdapterV2(),
        RuntimeToolFamily.RESTRICTED_PYTHON: RestrictedPythonAdapterV2(),
        RuntimeToolFamily.SYMBOLIC_COMPUTATION: SymbolicLinearAdapterV2(),
        RuntimeToolFamily.FORMAL_DECIDABILITY: FormalDecidabilityAdapterV2(),
    }
    final, receipt = run_foil(
        raw,
        args.a0,
        obligation,
        adapters=adapters,
        ledger=RuntimeTokenLedger(),
        policy=FoilRuntimePolicyV2(
            True,
            args.active_answer_change,
            ComparatorPolicy(),
            ConstructorPolicyV2(),
        ),
        archive=RawEvidenceArchive(args.archive_dir),
    )
    trace = receipt.trace()
    result: dict[str, object] = {
        "schema": "foil.runtime-cli-result.v1",
        "final_answer": final,
        "final_answer_sha256": digest(final),
        "receipt": trace,
    }
    result["result_sha256"] = digest(result)
    _persist(args.output, result)
    print(
        f"stored={args.output.resolve()} outcome={trace['outcome']} "
        f"answer_changed={str(trace['answer_changed']).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
