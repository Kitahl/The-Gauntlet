#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json

from mastermind_lib.intervention_boundary import (
    EditOperation, FaultNode, InterventionPolicy, SourceSpanBinding, TypedEdit,
    build_failure_graph, content_sha256,
)
from mastermind_lib.repair_minimality import (
    FAIL, SUCCESS, UNKNOWN, EXHAUSTIVE_MINIMUM_PASS, EXHAUSTIVE_MINIMUM_UNKNOWN,
    RepairOutcome, enumerate_repair_search_space, select_exhaustive_minimum_successful_repair,
)

checks = {}
def h(text: str) -> str: return hashlib.sha256(text.encode()).hexdigest()
def ck(name, cond, detail=None):
    if not cond: raise AssertionError(f"{name}: {detail}")
    checks[name] = True

span = SourceSpanBinding("src/example.py", 1, 1, content_sha256("old\n")).normalized()
node = FaultNode("F1", "ASSERTION", span, ("O1",), True).normalized()
graph = build_failure_graph(frozen_target_sha256=h("tree"), nodes=(node,))
edit_small = TypedEdit("E-small", EditOperation.REPLACE_SPAN, span, "new", ("O1",), ("F1",)).normalized()
edit_big = TypedEdit("E-big", EditOperation.REPLACE_SPAN, span, "new\nextra", ("O1",), ("F1",)).normalized()
space, plans = enumerate_repair_search_space(graph=graph, primitive_edits=(edit_small, edit_big), discriminating_probe_ids=("P1",), max_edit_count=1)
ck("01_exact_two_plan_universe", len(plans) == 2 and len(space.plan_ids) == 2, space)
policy = InterventionPolicy(("src",), (EditOperation.REPLACE_SPAN,), 1, 10, 20, ("P1",))
span_hashes = {span.key: span.before_sha256}
plan_by_edit = {plan.edits[0].edit_id: plan for plan in plans}
outcomes = (
    RepairOutcome(space.search_space_id, plan_by_edit["E-small"].plan_id, SUCCESS, "executor", "verifier", (h("small"),)).bound(),
    RepairOutcome(space.search_space_id, plan_by_edit["E-big"].plan_id, SUCCESS, "executor", "verifier", (h("big"),)).bound(),
)
result = select_exhaustive_minimum_successful_repair(
    search_space=space, graph=graph, plans=plans, policy=policy,
    known_obligation_ids=("O1",), current_span_hashes=span_hashes, required_obligation_ids=("O1",), outcomes=outcomes,
)
ck("02_exhaustive_minimum_selects_smallest_success", result["status"] == EXHAUSTIVE_MINIMUM_PASS and result["selected_plan_id"] == plan_by_edit["E-small"].plan_id, result)

incomplete = (outcomes[0],)
unknown_result = select_exhaustive_minimum_successful_repair(
    search_space=space, graph=graph, plans=plans, policy=policy,
    known_obligation_ids=("O1",), current_span_hashes=span_hashes, required_obligation_ids=("O1",), outcomes=incomplete,
)
ck("03_missing_outcome_blocks_global_claim", unknown_result["status"] == EXHAUSTIVE_MINIMUM_UNKNOWN and any(x.startswith("EXHAUSTIVE_VALID_PLAN_OUTCOME_COVERAGE_MISMATCH") for x in unknown_result["failures"]), unknown_result)

unknown_outcomes = (
    outcomes[0],
    RepairOutcome(space.search_space_id, plan_by_edit["E-big"].plan_id, UNKNOWN, "executor", "verifier", (h("unknown"),)).bound(),
)
unknown2 = select_exhaustive_minimum_successful_repair(
    search_space=space, graph=graph, plans=plans, policy=policy,
    known_obligation_ids=("O1",), current_span_hashes=span_hashes, required_obligation_ids=("O1",), outcomes=unknown_outcomes,
)
ck("04_unknown_outcome_blocks_global_claim", unknown2["status"] == EXHAUSTIVE_MINIMUM_UNKNOWN, unknown2)

try:
    RepairOutcome(space.search_space_id, plan_by_edit["E-small"].plan_id, SUCCESS, "same", "same", (h("x"),)).bound()
except ValueError:
    checks["05_self_verification_rejected"] = True
else:
    raise AssertionError("05_self_verification_rejected")

payload = {"schema":"mastermind/postbench-hardening-selftest/1","status":"PASS","passed":len(checks),"total":len(checks),"checks":checks}
open("MASTERMIND_POSTBENCH_HARDENING_RESULT.json","w").write(json.dumps(payload,indent=2,sort_keys=True)+"\n")
print(json.dumps(payload,indent=2,sort_keys=True))
