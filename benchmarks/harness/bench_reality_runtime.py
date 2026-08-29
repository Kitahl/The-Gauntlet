"""Offline Reality vNext correctness and runtime microbenchmark.

This harness measures deterministic mechanical behavior only. It does not measure global
novelty, scientific efficacy, causal validity, benchmark improvement, or downstream
engineering correctness. Space retrieval is replaced with a local deterministic adapter
so the timing numbers describe Reality/runtime storage and challenge mechanics rather
than network latency.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import reality_runtime as reality  # noqa: E402
import soul_runtime as soul  # noqa: E402
import space_runtime as space  # noqa: E402
from egrt_store import new_id  # noqa: E402
from egrt_types import ArtifactRef, ObligationKind, Verdict, digest  # noqa: E402

CLAIM_SCOPE = (
    "Within the registered assessed scope, the nearest prior art does not match "
    "the candidate changed assumption and mechanism."
)


def _init_root(root: Path) -> None:
    (root / ".gauntlet.json").write_text(
        json.dumps(
            {
                "state_dir": ".egrt/state",
                "runtime": {"enabled": True, "schema": "egrt.runtime.v1"},
                "challenge": {
                    "mode": "shadow",
                    "max_total_per_obligation": 4,
                    "max_load_bearing_per_obligation": 2,
                    "max_selected_discriminators": 2,
                    "allow_foil_proposals": True,
                    "require_claim_native_receipt": True,
                    "block_on_unavailable_load_bearing": True,
                    "persist_raw_text": False,
                },
            }
        ),
        encoding="utf-8",
    )


def _task(root: Path) -> tuple[str, str, str]:
    task = soul.start_task(root, "benchmark one bounded candidate mechanism")
    discovery = soul.add_obligation(
        root,
        task.task_id,
        ObligationKind.DISCOVERY,
        "assess concrete candidate prior art",
    )
    synthesis = soul.add_obligation(
        root,
        task.task_id,
        ObligationKind.SYNTHESIS,
        "synthesize a testable candidate",
        metadata={"depends_on": [discovery.obligation_id]},
    )
    soul.freeze_task(root, task.task_id)
    return task.task_id, discovery.obligation_id, synthesis.obligation_id


def _candidate(
    synthesis_id: str,
    *,
    candidate_id: str = "bench-candidate",
    metadata: dict[str, Any] | None = None,
) -> reality.MethodCandidate:
    merged: dict[str, Any] = {
        "scope_hash": digest({"scope": candidate_id}),
        "prior_art_claim_scope": CLAIM_SCOPE,
    }
    if metadata:
        merged.update(metadata)
    return reality.MethodCandidate(
        candidate_id=candidate_id,
        obligation_id=synthesis_id,
        gap="existing mechanism cannot condition on the required local state",
        failed_constraint="next action must depend on bounded local context",
        changed_assumption="allow local state to condition the next mechanism",
        mechanism="condition the transition on a bounded local state witness",
        nearest_prior_art=("KnownMechanismA",),
        actual_delta="adds an explicit local-state-conditioned transition",
        inputs=("problem state", "local witness"),
        outputs=("next action",),
        invariants=("bounded state", "deterministic binding"),
        dependencies=("Space assessed prior art",),
        failure_modes=("local state is uninformative",),
        negative_control="restore the baseline assumption while holding all else fixed",
        transfer_target="repeat on a different problem-family representation",
        ablation_plan=(
            "remove the local-state transition and measure the predeclared signal"
        ),
        verifier_plan="independent Time evaluation with a predeclared scorer",
        tags=("bounded", "mechanism"),
        metadata=merged,
    )


def _retrieval(
    root: Path,
    task_id: str,
    discovery_id: str,
    candidate: reality.MethodCandidate,
):
    plan = space.SearchPlan(
        plan_id=new_id("space-plan"),
        obligation_id=discovery_id,
        question="Does assessed prior art match this concrete candidate mechanism?",
        queries=("candidate mechanism comparison",),
        sources=("bench",),
        max_queries=1,
        saturation_queries=1,
        task_id=task_id,
        candidate_hash=reality.candidate_hash(candidate),
        scope_hash=str(candidate.metadata["scope_hash"]),
    )
    with patch.dict(
        space.ADAPTERS,
        {
            "bench": lambda _query, _limit: [
                {
                    "title": "Nearest assessed prior art",
                    "doi": "10.1/reality-benchmark",
                    "source_index": "bench",
                }
            ]
        },
        clear=True,
    ):
        return space.run_plan(root, plan)[0]


def _assessment(
    root: Path,
    discovery_id: str,
    search_receipt_id: str,
    relation: str,
    *,
    ident: str,
):
    return space.assess_sources(
        root,
        discovery_id,
        search_receipt_id,
        [
            space.SourceAssessment(
                ident,
                ArtifactRef(f"{ident}.pdf", sha256=digest(ident)),
                relation,
                f"verifier-{ident}",
                CLAIM_SCOPE,
                f"lineage-{ident}",
            )
        ],
    )


def _prepared(
    root: Path,
    *,
    relation: str = "SUPPORTS",
    metadata: dict[str, Any] | None = None,
    candidate_id: str = "bench-candidate",
) -> tuple[reality.MethodCandidate, Any, Any, str]:
    _init_root(root)
    task_id, discovery_id, synthesis_id = _task(root)
    candidate = _candidate(
        synthesis_id,
        candidate_id=candidate_id,
        metadata=metadata,
    )
    retrieval = _retrieval(root, task_id, discovery_id, candidate)
    assessment = _assessment(
        root,
        discovery_id,
        retrieval.receipt_id,
        relation,
        ident=f"assessment-{candidate_id}-{relation.lower()}",
    )
    return candidate, retrieval, assessment, discovery_id


def _case(name: str, expected: Verdict, actual: Verdict) -> dict[str, Any]:
    return {
        "name": name,
        "expected": expected.value,
        "actual": actual.value,
        "pass": actual is expected,
    }


def _correctness_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        candidate, _, assessment, _ = _prepared(root)
        receipt = reality.record_candidate(root, candidate, [assessment.receipt_id])
        cases.append(_case("supported_prior_art_non_match", Verdict.CLEARED, receipt.verdict))

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        candidate, _, assessment, _ = _prepared(root, relation="REFUTES")
        receipt = reality.record_candidate(root, candidate, [assessment.receipt_id])
        cases.append(_case("refuted_prior_art_non_match", Verdict.ISSUE, receipt.verdict))

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        candidate, _, assessment, _ = _prepared(root, relation="CONTEXT_ONLY")
        receipt = reality.record_candidate(root, candidate, [assessment.receipt_id])
        cases.append(_case("context_only_prior_art", Verdict.UNKNOWN, receipt.verdict))

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _init_root(root)
        task_id, discovery_id, synthesis_id = _task(root)
        candidate = _candidate(synthesis_id)
        retrieval = _retrieval(root, task_id, discovery_id, candidate)
        receipt = reality.record_candidate(root, candidate, [retrieval.receipt_id])
        cases.append(_case("retrieval_without_assessment", Verdict.UNKNOWN, receipt.verdict))

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        candidate, retrieval, support, discovery_id = _prepared(root)
        _assessment(
            root,
            discovery_id,
            retrieval.receipt_id,
            "REFUTES",
            ident="assessment-newer-refute",
        )
        receipt = reality.record_candidate(root, candidate, [support.receipt_id])
        cases.append(_case("newer_refute_outranks_stale_support", Verdict.ISSUE, receipt.verdict))

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        candidate, _, support, _ = _prepared(
            root,
            metadata={
                "competing_mechanism_required": True,
                "competing_mechanism": "global-state transition",
                "competing_discriminator": (
                    "hold local witness fixed while varying global state"
                ),
            },
        )
        receipt = reality.record_candidate(root, candidate, [support.receipt_id])
        cases.append(_case("explicit_competing_discriminator", Verdict.CLEARED, receipt.verdict))

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        candidate, _, support, _ = _prepared(
            root,
            metadata={
                "competing_mechanism_required": True,
                "competing_mechanism": "global-state transition",
            },
        )
        receipt = reality.record_candidate(root, candidate, [support.receipt_id])
        cases.append(_case("missing_competing_discriminator", Verdict.UNKNOWN, receipt.verdict))

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _init_root(root)
        task_id, discovery_id, synthesis_id = _task(root)
        candidate = replace(
            _candidate(synthesis_id),
            invariants=(),
            dependencies=(),
        )
        retrieval = _retrieval(root, task_id, discovery_id, candidate)
        assessment = _assessment(
            root,
            discovery_id,
            retrieval.receipt_id,
            "SUPPORTS",
            ident="assessment-missing-contract-fields",
        )
        receipt = reality.record_candidate(root, candidate, [assessment.receipt_id])
        cases.append(_case("missing_invariants_dependencies", Verdict.UNKNOWN, receipt.verdict))

    return cases


def _summary_ms(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("benchmark sample cannot be empty")
    p95_index = max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999999) - 1))
    return {
        "n": len(ordered),
        "mean": round(statistics.fmean(ordered), 4),
        "median": round(statistics.median(ordered), 4),
        "p95": round(ordered[p95_index], 4),
        "min": round(ordered[0], 4),
        "max": round(ordered[-1], 4),
    }


def _cold_admission_ms(samples: int) -> dict[str, Any]:
    values: list[float] = []
    for index in range(samples):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, _, support, _ = _prepared(
                root,
                candidate_id=f"cold-{index}",
            )
            started = time.perf_counter()
            receipt = reality.record_candidate(root, candidate, [support.receipt_id])
            elapsed = (time.perf_counter() - started) * 1000.0
            if receipt.verdict is not Verdict.CLEARED:
                raise AssertionError(f"cold benchmark admission failed: {receipt.verdict.value}")
            values.append(elapsed)
    return _summary_ms(values)


def _hot_evaluation_ms(samples: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        candidate, _, support, _ = _prepared(root, candidate_id="hot")
        receipt = reality.record_candidate(root, candidate, [support.receipt_id])
        if receipt.verdict is not Verdict.CLEARED:
            raise AssertionError("hot benchmark setup did not clear")
        bundle = reality.load_attack_bundle(root, candidate.candidate_id)
        if bundle is None:
            raise AssertionError("hot benchmark bundle missing")
        values: list[float] = []
        for _ in range(samples):
            started = time.perf_counter()
            verdict, _ = reality.evaluate_admission(root, candidate, bundle)
            values.append((time.perf_counter() - started) * 1000.0)
            if verdict is not Verdict.CLEARED:
                raise AssertionError(f"hot benchmark evaluation failed: {verdict.value}")
    return _summary_ms(values)


def _signature_ms(samples: int) -> dict[str, Any]:
    candidate = _candidate("signature-obligation", candidate_id="signature")
    values: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        value = reality.mechanism_signature(candidate)
        values.append((time.perf_counter() - started) * 1000.0)
        if len(value) != 64:
            raise AssertionError("mechanism signature is not SHA-256 shaped")
    summary = _summary_ms(values)
    mean = float(summary["mean"])
    summary["operations_per_second_from_mean"] = (
        round(1000.0 / mean, 2) if mean > 0 else None
    )
    return summary


def run_benchmark(
    *,
    cold_samples: int = 8,
    hot_samples: int = 50,
    signature_samples: int = 2000,
) -> dict[str, Any]:
    for name, value in (
        ("cold_samples", cold_samples),
        ("hot_samples", hot_samples),
        ("signature_samples", signature_samples),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive int")

    cases = _correctness_cases()
    passed = sum(1 for row in cases if row["pass"])
    return {
        "schema": "reality.benchmark.v1",
        "correctness": {
            "passed": passed,
            "total": len(cases),
            "rate": passed / len(cases),
            "cases": cases,
        },
        "latency_ms": {
            "record_candidate_cold": _cold_admission_ms(cold_samples),
            "evaluate_admission_hot": _hot_evaluation_ms(hot_samples),
            "mechanism_signature": _signature_ms(signature_samples),
        },
        "scope": {
            "offline": True,
            "external_search": False,
            "network_latency_measured": False,
            "scientific_efficacy_measured": False,
            "global_novelty_measured": False,
            "causal_mechanism_efficacy_measured": False,
            "downstream_benchmark_improvement_measured": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cold-samples", type=int, default=8)
    parser.add_argument("--hot-samples", type=int, default=50)
    parser.add_argument("--signature-samples", type=int, default=2000)
    args = parser.parse_args()
    result = run_benchmark(
        cold_samples=args.cold_samples,
        hot_samples=args.hot_samples,
        signature_samples=args.signature_samples,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["correctness"]["passed"] == result["correctness"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
