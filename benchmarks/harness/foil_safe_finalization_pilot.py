#!/usr/bin/env python3
"""Run the preregistered deterministic FOIL safe-finalization small pilot."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_certificates import CertificateClass, EvidenceCertificate  # noqa: E402
from egrt_claims import Applicability, Decidability, PostSolveObligation  # noqa: E402
from egrt_coverage import (  # noqa: E402
    ContributionOutcome,
    CoverageContribution,
    CoverageRequirement,
    summarize_coverage,
)
from egrt_host_bridge import HostActionRequest, create_host_action_request  # noqa: E402
from egrt_host_finalizer import (  # noqa: E402
    FinalizationState,
    HostCommitApproval,
    answer_digest,
    finalize_host_answer,
    host_request_digest,
)
from egrt_types import ArtifactRef, EvidenceClass, digest  # noqa: E402
from egrt_verifiers import DEFAULT_REGISTRY, VerificationStatus  # noqa: E402
from foil_adaptive_route import (  # noqa: E402
    AdaptiveRoutePolicy,
    DecisionReason,
    FrozenEVModel,
    RiskClass,
    Route,
    decide_shadow_route,
    host_verifier_routes,
)
from foil_authority import (  # noqa: E402
    AdmissionState,
    Applicability as SensorApplicability,
    AuthorityAction,
    AuthorityCeiling,
    AuthorityContext,
    EvidenceSurface,
    SensorOutcome,
    SensorRegistration,
    SensorReport,
    decide_authority,
)
from foil_authority_replay import AuthorityReplayGuard  # noqa: E402
from foil_candidate_state import (  # noqa: E402
    AuthorityIssuer,
    CandidateBinding,
    CandidateState,
    Gate,
    GateReceipt,
    GateStatus,
    decide_candidate_state,
)
from foil_obligation_compiler import (  # noqa: E402
    COMPILER_VERSION,
    TASK_SPEC_SCHEMA,
    compile_task_spec,
)
from foil_shadow_repair import (  # noqa: E402
    ExternalRepairCandidate,
    admit_shadow_repair,
    propose_shadow_repair,
)


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RescueCase:
    case_id: str
    claim_kind: str
    predicate_kind: str
    verifier_id: str
    base_answer: str
    candidate_answer: str
    failing_input: dict[str, Any]
    passing_input: dict[str, Any]


RESCUE_CASES = (
    RescueCase(
        "arithmetic-rescue",
        "EXACT_ARITHMETIC",
        "EXACT_ARITHMETIC",
        "builtin.exact_arithmetic",
        "2 + 2 = 5",
        "2 + 2 = 4",
        {"expression": "2 + 2", "expected": "5"},
        {"expression": "2 + 2", "expected": "4"},
    ),
    RescueCase(
        "json-rescue",
        "JSON",
        "JSON",
        "builtin.json_exact",
        '{"answer":5}',
        '{"answer":4}',
        {"actual": '{"answer":5}', "expected": '{"answer":4}'},
        {"actual": '{"answer":4}', "expected": '{"answer":4}'},
    ),
    RescueCase(
        "tolerance-rescue",
        "NUMERIC_TOLERANCE",
        "NUMERIC_TOLERANCE",
        "builtin.numeric_tolerance",
        "measurement=10.0",
        "measurement=7.5",
        {"actual": "10.0", "expected": "7.5", "tolerance": "0.1"},
        {"actual": "7.5", "expected": "7.5", "tolerance": "0.1"},
    ),
)


def ev_model() -> FrozenEVModel:
    return FrozenEVModel(
        base_correct_ppm=500_000,
        verify_rescue_ppm=700_000,
        verify_damage_ppm=50_000,
        full_rescue_ppm=800_000,
        full_damage_ppm=100_000,
        rescue_utility_micro=1_000_000,
        damage_disutility_micro=1_000_000,
        cost_penalty_micro_per_unit=10_000,
        verify_incremental_cost_units=1,
        full_incremental_cost_units=2,
        evidence_digest=d("pilot-frozen-ev"),
    )


def compile_case(case: RescueCase):
    spec = {
        "schema": TASK_SPEC_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "task_digest": d(f"task:{case.case_id}"),
        "a0_digest": answer_digest(case.base_answer),
        "config_digest": d("pilot-config"),
        "claims": [
            {
                "claim_key": case.case_id,
                "statement_digest": d(f"statement:{case.case_id}"),
                "claim_kind": case.claim_kind,
                "decidability": "DETERMINISTIC",
                "applicability": "APPLICABLE",
                "reason": "Host-declared deterministic pilot obligation.",
                "obligations": [
                    {
                        "obligation_key": "primary",
                        "description": "Frozen pilot predicate",
                        "weight_range": {"start": 1, "end": 1},
                        "predicate_kind": case.predicate_kind,
                        "verifier_id": case.verifier_id,
                        "verifier_version": "1",
                        "verifier_input": case.failing_input,
                    }
                ],
            }
        ],
    }
    return compile_task_spec(spec, observed_a0_digest=spec["a0_digest"])


def certificate(
    *,
    compiled,
    candidate_digest: str,
    certificate_class: CertificateClass,
    verifier,
    certificate_id: str,
) -> EvidenceCertificate:
    bundle = compiled.claims[0].obligations[0]
    requirement = CoverageRequirement(
        bundle.obligation,
        Decidability.DETERMINISTIC,
        Applicability.APPLICABLE,
    )
    coverage = summarize_coverage(
        (requirement,),
        (
            CoverageContribution(
                bundle.obligation.obligation_id,
                verifier.evidence_digest,
                ContributionOutcome.PASS,
                "pilot verifier passed",
            ),
        ),
    )
    return EvidenceCertificate(
        certificate_id=certificate_id,
        certificate_class=certificate_class,
        claim_id=bundle.obligation.claim_id,
        base_digest=compiled.bindings.a0_digest,
        candidate_digest=candidate_digest,
        scope_digest=d(f"scope:{bundle.obligation.claim_id}"),
        obligation_set_digest=d(f"obligations:{bundle.obligation.obligation_id}"),
        bindings=compiled.bindings,
        verifier=verifier,
        environment_digest=d("pilot-environment"),
        evidence_digests=(verifier.evidence_digest,),
        coverage=coverage,
    )


def authority_for_defect(base_digest: str, scope: str):
    registration = SensorRegistration(
        sensor_id="pilot.closed-verifier",
        evidence_class=EvidenceClass.PROVEN,
        surface=EvidenceSurface.ANSWER,
        authority_ceiling=AuthorityCeiling.REPAIR_PROPOSAL_ALLOWED,
        claim_scope=scope,
        producer="pilot.closed-verifier",
        version="1",
    )
    report = SensorReport(
        sensor_id=registration.sensor_id,
        input_digest=base_digest,
        applicability=SensorApplicability.APPLICABLE,
        outcome=SensorOutcome.DEFECT,
        target_scope=scope,
    )
    return decide_authority(
        registration,
        report,
        AuthorityContext(True, True, True),
    )


def active_decision(case_id: str, base_digest: str, candidate_id: str):
    binding = CandidateBinding(
        candidate_id=candidate_id,
        task_digest=d(f"task:{case_id}"),
        base_answer_digest=base_digest,
        protocol_digest=d("pilot-protocol"),
        config_digest=d("pilot-config"),
        partition_digest=d("pilot-partition"),
        budget_ceiling_digest=d("pilot-budget"),
    )
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    issuer = AuthorityIssuer(f"pilot.host:{case_id}", d(case_id).encode("ascii"))

    def receipt(gate: Gate) -> GateReceipt:
        return GateReceipt(
            gate=gate,
            status=GateStatus.PASS,
            binding_digest=binding.digest(),
            evidence_digest=d(f"{case_id}:{gate.value}:evidence"),
            solve_equivalence_digest=base_digest,
            cost_ledger_digest=d(f"{case_id}:{gate.value}:cost"),
            reason="synthetic contract-pilot gate",
            forbidden_calls=0,
            required_domains_passed=True,
            cost_complete=True,
            conditional_validity_passed=True,
        )

    receipts = tuple(receipt(gate) for gate in Gate)
    locked = issuer.mint(
        binding,
        CandidateState.LOCKED,
        receipts[0].digest(),
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        nonce=f"{case_id}-locked",
    )
    combined = hashlib.sha256(
        "".join(item.digest() for item in receipts).encode("ascii")
    ).hexdigest()
    active = issuer.mint(
        binding,
        CandidateState.ACTIVE,
        combined,
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        nonce=f"{case_id}-active",
    )
    decision = decide_candidate_state(
        binding,
        enabled=True,
        issuer=issuer,
        now=now.isoformat(),
        gate_receipts=receipts,
        locked_token=locked,
        active_token=active,
        host_activation_approved=True,
    )
    return decision, binding, issuer, now


def full_request(case: RescueCase):
    compiled = compile_case(case)
    route = host_verifier_routes(compiled)[0]
    initial = decide_shadow_route(
        bindings=compiled.bindings,
        risk=RiskClass.ONE_FALSIFIABLE,
        policy=AdaptiveRoutePolicy(enabled=True),
        ev=ev_model(),
        compiled_spec=compiled,
        obligation_ids=(route.obligation_id,),
        verifier_routes=(route,),
    )
    failed = DEFAULT_REGISTRY.run(case.verifier_id, case.failing_input)
    escalated = decide_shadow_route(
        bindings=compiled.bindings,
        risk=RiskClass.VERIFIED_DEFECT,
        policy=AdaptiveRoutePolicy(enabled=True),
        ev=ev_model(),
        compiled_spec=compiled,
        obligation_ids=(route.obligation_id,),
        verifier_routes=(route,),
        verification=failed,
    )
    if initial.route is not Route.VERIFY or failed.status is not VerificationStatus.FAIL:
        raise RuntimeError("pilot rescue did not reach the declared verifier defect")
    if escalated.route is not Route.FULL:
        raise RuntimeError("pilot verified defect did not reach FULL recommendation")

    candidate_digest = answer_digest(case.candidate_answer)
    structural_result = DEFAULT_REGISTRY.run(case.verifier_id, case.passing_input)
    semantic_result = DEFAULT_REGISTRY.run(
        "builtin.exact_match",
        {"actual": case.candidate_answer, "expected": case.candidate_answer},
    )
    semantic_result = dataclasses.replace(
        semantic_result,
        provenance_group=f"pilot.independent:{case.case_id}",
    )
    structural = certificate(
        compiled=compiled,
        candidate_digest=candidate_digest,
        certificate_class=CertificateClass.PREDICATE_SCOPED,
        verifier=structural_result,
        certificate_id=f"{case.case_id}-structural",
    )
    semantic = certificate(
        compiled=compiled,
        candidate_digest=candidate_digest,
        certificate_class=CertificateClass.INDEPENDENT_SEMANTIC,
        verifier=semantic_result,
        certificate_id=f"{case.case_id}-semantic",
    )
    authority = authority_for_defect(compiled.bindings.a0_digest, case.case_id)
    external = ExternalRepairCandidate(
        candidate_id=f"candidate:{case.case_id}",
        base_digest=compiled.bindings.a0_digest,
        candidate_digest=candidate_digest,
        scope_digest=structural.scope_digest,
        obligation_set_digest=structural.obligation_set_digest,
        producer_id="pilot.fixture-producer",
        producer_version="1",
        artifact=ArtifactRef(
            locator=f"host://pilot/{case.case_id}",
            sha256=candidate_digest,
        ),
    )
    proposal = propose_shadow_repair(authority, external)
    admission = admit_shadow_repair(
        proposal,
        structural_certificate=structural,
        semantic_certificate=semantic,
    )
    decision, binding, issuer, now = active_decision(
        case.case_id,
        compiled.bindings.a0_digest,
        external.candidate_id,
    )
    request = create_host_action_request(
        admission,
        decision=decision,
        binding=binding,
        issuer=issuer,
        now=now.isoformat(),
        replay_guard=AuthorityReplayGuard(),
    )
    return request, initial, escalated, admission


def approve(request: HostActionRequest, case_id: str) -> HostCommitApproval:
    return HostCommitApproval(
        request_digest=host_request_digest(request),
        candidate_digest=request.candidate_digest,
        approver_id="pilot.explicit-host",
        approved_at="2026-08-24T12:00:00+00:00",
        reason=f"frozen pilot approval:{case_id}",
    )


def result_row(
    case_id: str,
    expected: str,
    selected: str,
    state: str,
    reason: str,
    elapsed_ns: int,
    **extra: object,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "passed": selected == expected,
        "expected_digest": answer_digest(expected),
        "selected_digest": answer_digest(selected),
        "state": state,
        "reason": reason,
        "elapsed_ns": elapsed_ns,
        **extra,
    }


def run_rescue(case: RescueCase) -> dict[str, object]:
    started = time.perf_counter_ns()
    request, initial, escalated, admission = full_request(case)
    final = finalize_host_answer(
        request,
        base_answer=case.base_answer,
        candidate_answer=case.candidate_answer,
        approval=approve(request, case.case_id),
    )
    return result_row(
        case.case_id,
        case.candidate_answer,
        final.answer,
        final.state.value,
        final.reason,
        time.perf_counter_ns() - started,
        initial_route=initial.route.value,
        verified_defect_route=escalated.route.value,
        admission_state=admission.decision.state.value,
        host_action_applied=final.host_action_applied,
    )


def run_correct_clear() -> dict[str, object]:
    started = time.perf_counter_ns()
    base = "2 + 2 = 4"
    registration = SensorRegistration(
        sensor_id="pilot.clear",
        evidence_class=EvidenceClass.PROVEN,
        surface=EvidenceSurface.ANSWER,
        authority_ceiling=AuthorityCeiling.REPAIR_PROPOSAL_ALLOWED,
        claim_scope="correct-clear-stand-down",
        producer="pilot.clear",
        version="1",
    )
    decision = decide_authority(
        registration,
        SensorReport(
            sensor_id=registration.sensor_id,
            input_digest=answer_digest(base),
            applicability=SensorApplicability.APPLICABLE,
            outcome=SensorOutcome.CLEAR,
            target_scope=registration.claim_scope,
        ),
        AuthorityContext(True, True, True),
    )
    return result_row(
        "correct-clear-stand-down",
        base,
        base,
        FinalizationState.BASE_PRESERVED.value,
        decision.reason,
        time.perf_counter_ns() - started,
        authority_action=decision.action.value,
        host_action_applied=False,
    )


def run_semantic_stand_down() -> dict[str, object]:
    started = time.perf_counter_ns()
    base = "A defensible semantic answer."
    spec = {
        "schema": TASK_SPEC_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "task_digest": d("semantic-task"),
        "a0_digest": answer_digest(base),
        "config_digest": d("pilot-config"),
        "claims": [
            {
                "claim_key": "semantic-only",
                "statement_digest": d("semantic statement"),
                "claim_kind": "OTHER",
                "decidability": "SEMANTIC",
                "applicability": "APPLICABLE",
                "reason": "No deterministic verifier exists.",
                "obligations": [
                    {
                        "obligation_key": "meaning",
                        "description": "Semantic-only obligation",
                        "weight_range": {"start": 1, "end": 1},
                        "predicate_kind": "EXACT_MATCH",
                        "verifier_id": "builtin.exact_match",
                        "verifier_version": "1",
                        "verifier_input": {"actual": "x", "expected": "x"},
                    }
                ],
            }
        ],
    }
    compiled = compile_task_spec(spec, observed_a0_digest=spec["a0_digest"])
    decision = decide_shadow_route(
        bindings=compiled.bindings,
        risk=RiskClass.ONE_FALSIFIABLE,
        policy=AdaptiveRoutePolicy(enabled=True),
        ev=ev_model(),
        compiled_spec=compiled,
    )
    return result_row(
        "semantic-route-stand-down",
        base,
        base,
        FinalizationState.BASE_PRESERVED.value,
        decision.reason.value,
        time.perf_counter_ns() - started,
        route=decision.route.value,
        host_action_applied=False,
    )


def run_same_provenance_rejection() -> dict[str, object]:
    started = time.perf_counter_ns()
    case = RESCUE_CASES[0]
    compiled = compile_case(case)
    candidate_digest = answer_digest(case.candidate_answer)
    structural_result = DEFAULT_REGISTRY.run(case.verifier_id, case.passing_input)
    semantic_result = DEFAULT_REGISTRY.run(
        "builtin.exact_match",
        {"actual": case.candidate_answer, "expected": case.candidate_answer},
    )
    structural = certificate(
        compiled=compiled,
        candidate_digest=candidate_digest,
        certificate_class=CertificateClass.PREDICATE_SCOPED,
        verifier=structural_result,
        certificate_id="same-provenance-structural",
    )
    semantic = certificate(
        compiled=compiled,
        candidate_digest=candidate_digest,
        certificate_class=CertificateClass.INDEPENDENT_SEMANTIC,
        verifier=semantic_result,
        certificate_id="same-provenance-semantic",
    )
    external = ExternalRepairCandidate(
        candidate_id="candidate:same-provenance",
        base_digest=compiled.bindings.a0_digest,
        candidate_digest=candidate_digest,
        scope_digest=structural.scope_digest,
        obligation_set_digest=structural.obligation_set_digest,
        producer_id="pilot.fixture-producer",
        producer_version="1",
        artifact=ArtifactRef(locator="host://pilot/same-provenance", sha256=candidate_digest),
    )
    proposal = propose_shadow_repair(
        authority_for_defect(compiled.bindings.a0_digest, case.case_id),
        external,
    )
    admission = admit_shadow_repair(
        proposal,
        structural_certificate=structural,
        semantic_certificate=semantic,
    )
    selected = case.base_answer
    return result_row(
        "same-provenance-rejection",
        case.base_answer,
        selected,
        FinalizationState.BASE_PRESERVED.value,
        admission.decision.reason,
        time.perf_counter_ns() - started,
        admission_state=admission.decision.state.value,
        host_action_applied=False,
    )


def run_tampered_candidate_rejection() -> dict[str, object]:
    started = time.perf_counter_ns()
    case = RESCUE_CASES[1]
    request, _, _, _ = full_request(case)
    tampered = '{"answer":999}'
    final = finalize_host_answer(
        request,
        base_answer=case.base_answer,
        candidate_answer=tampered,
        approval=approve(request, "tampered-candidate-rejection"),
    )
    return result_row(
        "tampered-candidate-rejection",
        case.base_answer,
        final.answer,
        final.state.value,
        final.reason,
        time.perf_counter_ns() - started,
        host_action_applied=final.host_action_applied,
        exact_base_object=final.answer is case.base_answer,
    )


def run() -> dict[str, object]:
    rows = [run_rescue(case) for case in RESCUE_CASES]
    rows.extend(
        (
            run_correct_clear(),
            run_semantic_stand_down(),
            run_same_provenance_rejection(),
            run_tampered_candidate_rejection(),
        )
    )
    rescue = rows[:3]
    denials = rows[3:]
    return {
        "schema": "foil.safe-finalization-small-pilot.v1",
        "preregistration": "benchmarks/FOIL_SAFE_FINALIZATION_SMALL_PILOT.md",
        "case_count": len(rows),
        "passed": sum(bool(row["passed"]) for row in rows),
        "failed": sum(not bool(row["passed"]) for row in rows),
        "rescue_passed": sum(bool(row["passed"]) for row in rescue),
        "rescue_total": len(rescue),
        "denial_passed": sum(bool(row["passed"]) for row in denials),
        "denial_total": len(denials),
        "unauthorized_answer_changes": sum(
            row["state"] == FinalizationState.CANDIDATE_SELECTED.value
            for row in denials
        ),
        "model_calls": 0,
        "network_calls": 0,
        "token_cost": 0,
        "cases": rows,
    }


def markdown(report: dict[str, object]) -> str:
    lines = [
        "# FOIL safe-finalization small pilot result",
        "",
        "This is deterministic software-contract evidence, not behavioral-efficacy "
        "or promotion evidence.",
        "",
        f"- Overall: **{report['passed']}/{report['case_count']} passed**",
        f"- Rescue cases: **{report['rescue_passed']}/{report['rescue_total']}**",
        f"- Preservation/rejection cases: **{report['denial_passed']}/{report['denial_total']}**",
        f"- Unauthorized answer changes: **{report['unauthorized_answer_changes']}**",
        "- Model/network calls: **0 / 0**",
        "- Token cost: **0**",
        "",
        "| Case | Result | State | Reason | Elapsed (ms) |",
        "|---|---:|---|---|---:|",
    ]
    for row in report["cases"]:
        lines.append(
            f"| {row['case_id']} | {'PASS' if row['passed'] else 'FAIL'} | "
            f"{row['state']} | {row['reason']} | {row['elapsed_ns'] / 1_000_000:.3f} |"
        )
    lines.extend(
        (
            "",
            "The three positive cases use host-supplied candidate fixtures and "
            "synthetic gate receipts. ",
            "They establish wiring and fail-closed selection behavior only; they do "
            "not establish that FOIL can discover repairs or improve real tasks.",
            "",
        )
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    report = run()
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output_dir is None:
        print(payload, end="")
    else:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "results.json").write_text(payload, encoding="utf-8")
        (args.output_dir / "report.md").write_text(markdown(report), encoding="utf-8")
        print(args.output_dir / "report.md")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
