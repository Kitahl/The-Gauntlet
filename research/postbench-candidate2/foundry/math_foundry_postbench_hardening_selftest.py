#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from math_foundry_exec.canonical import digest
from math_foundry_exec.formalization_evidence import ROLE_DEPENDENCY_CHECKER, VerificationAuthority
from math_foundry_exec.theory_graph import TRUSTED_BASE, UNTRUSTED_GENERATED, TheoryGraph, TheoryNode, build_trusted_base_comparator_manifest
from math_foundry_exec.trusted_base_minimality import (
    DOES_NOT_PROVE,
    GLOBAL_MINIMUM_FAIL,
    GLOBAL_MINIMUM_PASS,
    GLOBAL_MINIMUM_UNKNOWN,
    PROVES,
    ExhaustiveTrustedBaseReceipt,
    assess_bounded_global_trusted_base_minimality,
    build_trusted_base_search_space,
)
from math_foundry_isolated_qualification_runner import run_manifest

ROOT = Path(__file__).resolve().parent
checks: dict[str, bool] = {}


def h(value: object) -> str:
    return digest({"postbench-test": value})


def ck(name: str, value: bool, detail=None) -> None:
    if not value:
        raise AssertionError(f"{name}: {detail}")
    checks[name] = True


producer = h("producer")
checker = h("checker")
authority = VerificationAuthority(
    name="bounded-global-minimality-checker",
    subject_implementation_digest=checker,
    trust_root_digest=h("trust-root"),
    roles=(ROLE_DEPENDENCY_CHECKER,),
).bound()
registry = {authority.authority_id: authority}
source_id = h("source")
base_a = TheoryNode(
    name="Base.A", node_kind="AXIOM", artifact_digest=h("A"), source_product_id=source_id,
    version="1", trust_class=TRUSTED_BASE, dependencies=(), producer_id="trusted",
    producer_implementation_digest=h("trusted-build"), provenance_digests=(h("pA"),), protected=True,
).bound()
base_b = TheoryNode(
    name="Base.B", node_kind="THEOREM", artifact_digest=h("B"), source_product_id=source_id,
    version="1", trust_class=TRUSTED_BASE, dependencies=(base_a.node_id,), producer_id="trusted",
    producer_implementation_digest=h("trusted-build"), provenance_digests=(h("pB"),), protected=True,
).bound()
target = TheoryNode(
    name="Target", node_kind="THEOREM", artifact_digest=h("target"), source_product_id=source_id,
    version="candidate", trust_class=UNTRUSTED_GENERATED, dependencies=(base_b.node_id,), producer_id="candidate",
    producer_implementation_digest=producer, provenance_digests=(h("pt"),),
).bound()
comparator = TheoryNode(
    name="Comparator.Target", node_kind="COMPARATOR", artifact_digest=h("comparator"), source_product_id=source_id,
    version="candidate", trust_class=UNTRUSTED_GENERATED, dependencies=(base_b.node_id,), producer_id="candidate",
    producer_implementation_digest=producer, provenance_digests=(h("pc"),), comparator_target_id=target.node_id,
).bound()
graph = TheoryGraph(
    theory_name="PostbenchMinimality", version="1", toolchain_digest=h("toolchain"), theorem_library_digest=h("library"),
    nodes=(base_a, base_b, target, comparator),
).bound()
manifest = build_trusted_base_comparator_manifest(graph, comparator_node_id=comparator.node_id)
space = build_trusted_base_search_space(graph, manifest, max_universe_size=4)
ck("01_search_space_contains_all_trusted_nodes", space.eligible_dependency_ids == tuple(sorted((base_a.node_id, base_b.node_id))), space)

all_results = (
    ((), DOES_NOT_PROVE),
    ((base_a.node_id,), DOES_NOT_PROVE),
    ((base_b.node_id,), DOES_NOT_PROVE),
    ((base_a.node_id, base_b.node_id), PROVES),
)
receipt = ExhaustiveTrustedBaseReceipt(
    search_space_id=space.search_space_id,
    authority_id=authority.authority_id,
    checker_implementation_digest=checker,
    producer_implementation_digest=producer,
    subset_results=all_results,
    evidence_digests=(h("exhaustive-evidence"),),
).bound()
assessment = assess_bounded_global_trusted_base_minimality(
    search_space=space, manifest=manifest, receipt=receipt, authority_registry=registry,
    candidate_producer_implementation_digest=producer,
)
ck("02_exhaustive_global_minimum_passes", assessment.status == GLOBAL_MINIMUM_PASS and assessment.minimum_cardinality == 2, assessment)

smaller = ExhaustiveTrustedBaseReceipt(
    search_space_id=space.search_space_id,
    authority_id=authority.authority_id,
    checker_implementation_digest=checker,
    producer_implementation_digest=producer,
    subset_results=(
        ((), DOES_NOT_PROVE),
        ((base_a.node_id,), DOES_NOT_PROVE),
        ((base_b.node_id,), PROVES),
        ((base_a.node_id, base_b.node_id), PROVES),
    ),
    evidence_digests=(h("smaller-evidence"),),
).bound()
smaller_assessment = assess_bounded_global_trusted_base_minimality(
    search_space=space, manifest=manifest, receipt=smaller, authority_registry=registry,
    candidate_producer_implementation_digest=producer,
)
ck("03_smaller_proving_base_is_detected", smaller_assessment.status == GLOBAL_MINIMUM_FAIL and "SMALLER_PROVING_TRUSTED_BASE_EXISTS" in smaller_assessment.reasons, smaller_assessment)

incomplete = ExhaustiveTrustedBaseReceipt(
    search_space_id=space.search_space_id,
    authority_id=authority.authority_id,
    checker_implementation_digest=checker,
    producer_implementation_digest=producer,
    subset_results=all_results[:-1],
    evidence_digests=(h("incomplete-evidence"),),
).bound()
incomplete_assessment = assess_bounded_global_trusted_base_minimality(
    search_space=space, manifest=manifest, receipt=incomplete, authority_registry=registry,
    candidate_producer_implementation_digest=producer,
)
ck("04_incomplete_search_is_unknown", incomplete_assessment.status == GLOBAL_MINIMUM_UNKNOWN and any(r.startswith("TRUSTED_BASE_EXHAUSTIVE_COVERAGE_MISMATCH") for r in incomplete_assessment.reasons), incomplete_assessment)

self_authority = VerificationAuthority(
    name="self-checker", subject_implementation_digest=producer, trust_root_digest=h("self-root"),
    roles=(ROLE_DEPENDENCY_CHECKER,),
).bound()
self_receipt = ExhaustiveTrustedBaseReceipt(
    search_space_id=space.search_space_id,
    authority_id=self_authority.authority_id,
    checker_implementation_digest=producer,
    producer_implementation_digest=producer,
    subset_results=all_results,
    evidence_digests=(h("self-evidence"),),
).bound()
self_assessment = assess_bounded_global_trusted_base_minimality(
    search_space=space, manifest=manifest, receipt=self_receipt,
    authority_registry={self_authority.authority_id: self_authority}, candidate_producer_implementation_digest=producer,
)
ck("05_self_checker_cannot_establish_global_minimum", self_assessment.status == GLOBAL_MINIMUM_FAIL and "TRUSTED_BASE_CHECKER_NOT_IMPLEMENTATION_INDEPENDENT" in self_assessment.reasons, self_assessment)

with tempfile.TemporaryDirectory(prefix="mf_isolation_selftest_") as td:
    root = Path(td)
    (root / "fixture.txt").write_text("ORIGINAL\n")
    (root / "mutate.py").write_text("from pathlib import Path\nPath('fixture.txt').write_text('MUTATED\\n')\n")
    (root / "assert_original.py").write_text("from pathlib import Path\nraise SystemExit(0 if Path('fixture.txt').read_text() == 'ORIGINAL\\n' else 2)\n")
    candidate_manifest = {
        "candidate": "isolation-selftest",
        "authority": "TEST_ONLY",
        "claim_boundary": "runner isolation selftest",
        "suite_isolation_required": True,
        "suites": [
            {"name": "mutate", "command": ["python", "mutate.py"], "timeout_seconds": 10},
            {"name": "assert_original", "command": ["python", "assert_original.py"], "timeout_seconds": 10},
        ],
    }
    (root / "manifest.json").write_text(json.dumps(candidate_manifest))
    result = run_manifest(
        root=root,
        manifest_path=root / "manifest.json",
        out_path=root / "result.json",
        log_dir=root / "logs",
    )
    ck("06_isolated_runner_enforces_fresh_root", result["status"] == "PASS" and result["passed"] == 2 and result["suite_isolation_enforced"], result)
    ck("07_isolated_runner_preserves_original_root", (root / "fixture.txt").read_text() == "ORIGINAL\n", (root / "fixture.txt").read_text())

with tempfile.TemporaryDirectory(prefix="mf_artifact_staging_selftest_") as td:
    root = Path(td)
    (root / "artifact.json").write_text("FORGED\n")
    (root / "produce.py").write_text("from pathlib import Path\nPath('artifact.json').write_text('REAL\\n')\n")
    (root / "consume.py").write_text("from pathlib import Path\nraise SystemExit(0 if Path('artifact.json').read_text() == 'REAL\\n' else 2)\n")
    candidate_manifest = {
        "candidate": "artifact-staging-selftest",
        "authority": "TEST_ONLY",
        "claim_boundary": "runner artifact staging selftest",
        "suite_isolation_required": True,
        "qualification_dependency_policy": "FRESH_ROOT_PER_SUITE_WITH_EXPLICIT_HASH_BOUND_ARTIFACT_STAGING_ONLY",
        "suites": [
            {"name": "produce", "command": ["python", "produce.py"], "timeout_seconds": 10, "produces": ["artifact.json"]},
            {"name": "consume", "command": ["python", "consume.py"], "timeout_seconds": 10, "requires_artifacts": ["artifact.json"]},
        ],
    }
    (root / "manifest.json").write_text(json.dumps(candidate_manifest))
    result = run_manifest(root=root, manifest_path=root / "manifest.json", out_path=root / "result.json", log_dir=root / "logs")
    ck("08_explicit_artifact_staging_passes", result["status"] == "PASS" and result["passed"] == 2, result)
    ledger = result.get("artifact_ledger", [])
    ck("09_artifact_staging_is_hash_bound_and_not_source_root_forgery", len(ledger) == 1 and ledger[0]["name"] == "artifact.json" and (root / "artifact.json").read_text() == "FORGED\n", ledger)

out = {"schema": "mathfoundry/postbench-hardening-selftest/2", "status": "PASS", "passed": len(checks), "total": len(checks), "checks": checks}
(ROOT / "MATH_FOUNDRY_POSTBENCH_HARDENING_SELFTEST_RESULT.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
