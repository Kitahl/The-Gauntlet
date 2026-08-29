from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import soul_runtime as soul  # noqa: E402
import space_runtime as space  # noqa: E402
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import ArtifactRef, ObligationKind, Verdict  # noqa: E402


def init_root(path: Path, *, challenge_mode: str = "shadow") -> None:
    (path / ".gauntlet.json").write_text(
        json.dumps(
            {
                "state_dir": ".egrt/state",
                "runtime": {"enabled": True},
                "challenge": {"mode": challenge_mode},
            }
        ),
        encoding="utf-8",
    )


class SpaceChallengeRuntimeTests(unittest.TestCase):
    def _task(self, root: Path) -> tuple[str, str]:
        task = soul.start_task(root, "find prior art for a bounded claim")
        obligation = soul.add_obligation(
            root,
            task.task_id,
            ObligationKind.DISCOVERY,
            "find and assess relevant prior art",
        )
        return task.task_id, obligation.obligation_id

    def _plan(
        self,
        task_id: str,
        obligation_id: str,
        *,
        base_query: str = "legacy vocabulary",
        reframe_query: str = "mechanism vocabulary",
        query_class: space.QueryClass = space.QueryClass.TERMINOLOGY_MISMATCH,
        queries: tuple[str, ...] | None = None,
        sources: tuple[str, ...] = ("fake",),
        saturation_queries: int = 1,
    ) -> space.SearchPlan:
        plan_id = "space-plan"
        frozen_queries = queries or (base_query,)
        hypothesis = space.QueryHypothesis(
            hypothesis_id="qh-1",
            search_plan_id=plan_id,
            obligation_id=obligation_id,
            parent_query_hash=space.canonical_query_hash(base_query),
            query_class=query_class,
            reframe_query=reframe_query,
            task_id=task_id,
        )
        return space.SearchPlan(
            plan_id=plan_id,
            obligation_id=obligation_id,
            question="Does relevant prior art exist in the registered scope?",
            queries=frozen_queries,
            sources=sources,
            max_queries=len(frozen_queries),
            saturation_queries=saturation_queries,
            query_hypotheses=(hypothesis,),
            task_id=task_id,
        )

    def test_terminology_mismatch_runs_one_automatic_reframe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            plan = self._plan(task_id, obligation_id)
            calls: list[str] = []

            def fake(query: str, _limit: int) -> list[dict[str, object]]:
                calls.append(query)
                if query == "mechanism vocabulary":
                    return [
                        {
                            "title": "Recovered mechanism paper",
                            "doi": "10.1/recovered",
                            "source_index": "fake",
                        }
                    ]
                return []

            with patch.dict(space.ADAPTERS, {"fake": fake}, clear=True):
                receipt, result = space.run_plan(root, plan)

            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            self.assertEqual(calls, ["legacy vocabulary", "mechanism vocabulary"])
            self.assertEqual(result["scope_status"], "CANDIDATES_RETRIEVED_REVIEW_REQUIRED")
            self.assertTrue(result["reframe_executed"])
            self.assertEqual(result["challenge_rounds"], 1)
            self.assertEqual(result["rounds"][1]["query_class"], "TERMINOLOGY_MISMATCH")
            self.assertEqual(result["rounds"][1]["reframe_outcome"], "NOVEL_YIELD")
            self.assertEqual(result["rounds"][1]["novel_yield"], 1)

    def test_query_reframe_lineage_binds_parent_challenge_scope_and_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            plan = self._plan(task_id, obligation_id)
            with patch.dict(space.ADAPTERS, {"fake": lambda _q, _limit: []}, clear=True):
                _, result = space.run_plan(root, plan)

            reframe = result["rounds"][1]
            self.assertEqual(reframe["task_id"], task_id)
            self.assertEqual(reframe["obligation_id"], obligation_id)
            self.assertEqual(reframe["search_plan_id"], plan.plan_id)
            self.assertEqual(
                reframe["parent_query_hash"],
                space.canonical_query_hash("legacy vocabulary"),
            )
            self.assertEqual(
                reframe["registered_scope_hash"],
                result["registered_search_scope_hash"],
            )
            self.assertIsNotNone(reframe["challenge_id"])
            challenge = RuntimeStore(root).read_challenge(str(reframe["challenge_id"]))
            self.assertIsNotNone(challenge)
            assert challenge is not None
            self.assertEqual(challenge["task_id"], task_id)
            self.assertEqual(challenge["obligation_id"], obligation_id)
            self.assertEqual(challenge["scope_hash"], result["registered_search_scope_hash"])
            self.assertEqual(challenge["state"], "UNRESOLVED")

    def test_exact_repeat_is_rejected_and_does_not_count_as_new_round(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            plan = self._plan(
                task_id,
                obligation_id,
                base_query="Base Query",
                reframe_query="  base   query ",
            )
            calls: list[str] = []

            def fake(query: str, _limit: int) -> list[dict[str, object]]:
                calls.append(query)
                return []

            with patch.dict(space.ADAPTERS, {"fake": fake}, clear=True):
                _, result = space.run_plan(root, plan)

            self.assertEqual(calls, ["Base Query"])
            self.assertEqual(result["queries_executed"], 1)
            self.assertEqual(result["challenge_rounds"], 0)
            self.assertFalse(result["reframe_executed"])
            self.assertEqual(
                result["reframe_diagnostics"][0]["reframe_outcome"],
                "REJECTED_REDUNDANT",
            )
            self.assertEqual(RuntimeStore(root).challenges_for(task_id, obligation_id), [])

    def test_source_adapter_gap_is_typed_and_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            plan = space.SearchPlan(
                "adapter-gap",
                obligation_id,
                "question",
                ("query",),
                ("unregistered-adapter",),
                task_id=task_id,
            )
            with patch.dict(space.ADAPTERS, {}, clear=True):
                receipt, result = space.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.UNAVAILABLE)
            self.assertEqual(result["scope_status"], "SEARCH_UNAVAILABLE")
            self.assertEqual(result["final_query_class"], "SOURCE_ADAPTER_GAP")
            self.assertNotEqual(result["scope_status"], "NOT_FOUND_WITHIN_SCOPE")

    def test_shared_provenance_forms_one_independence_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            plan = space.SearchPlan(
                "derivative-plan",
                obligation_id,
                "claim",
                ("query",),
                ("fake",),
                task_id=task_id,
            )
            with patch.dict(
                space.ADAPTERS,
                {
                    "fake": lambda _q, _limit: [
                        {"title": "Primary", "doi": "10.1/primary", "source_index": "fake"}
                    ]
                },
                clear=True,
            ):
                retrieval, _ = space.run_plan(root, plan)
            assessment = space.assess_sources(
                root,
                obligation_id,
                retrieval.receipt_id,
                [
                    space.SourceAssessment(
                        "a1",
                        ArtifactRef("primary.pdf", sha256="content-a"),
                        "SUPPORTS",
                        "reviewer-1",
                        "same scoped claim",
                        "shared-lineage",
                    ),
                    space.SourceAssessment(
                        "a2",
                        ArtifactRef("mirror.html", sha256="content-b"),
                        "SUPPORTS",
                        "reviewer-2",
                        "same scoped claim",
                        "shared-lineage",
                    ),
                ],
            )
            notes = json.loads(assessment.notes or "{}")
            self.assertEqual(assessment.verdict, Verdict.CLEARED)
            self.assertEqual(notes["independent_support_count"], 1)
            self.assertEqual(notes["derivative_component_count"], 1)
            stored = RuntimeStore(root).read_receipt(assessment.receipt_id)
            self.assertIsNotNone(stored)
            assert stored is not None
            groups = {
                item["metadata"]["independence_group_hash"] for item in stored["evidence"]
            }
            self.assertEqual(len(groups), 1)
            challenges = RuntimeStore(root).challenges_for(task_id, obligation_id)
            self.assertEqual(challenges[-1]["kind"], "SOURCE_CONFLICT")
            self.assertIn(
                "DERIVATIVE_SOURCE_COLLISION",
                challenges[-1]["metadata"]["conflict_types"],
            )
            self.assertIn(
                "PROVENANCE_COLLISION",
                challenges[-1]["metadata"]["conflict_types"],
            )

    def test_content_identical_derivatives_do_not_add_independent_support(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            plan = space.SearchPlan(
                "content-duplicate-plan",
                obligation_id,
                "claim",
                ("query",),
                ("fake",),
                task_id=task_id,
            )
            with patch.dict(
                space.ADAPTERS,
                {"fake": lambda _q, _limit: [{"title": "P", "doi": "10.1/p"}]},
                clear=True,
            ):
                retrieval, _ = space.run_plan(root, plan)
            assessment = space.assess_sources(
                root,
                obligation_id,
                retrieval.receipt_id,
                [
                    space.SourceAssessment(
                        "copy-a",
                        ArtifactRef("publisher.pdf", sha256="identical-content"),
                        "SUPPORTS",
                        "reviewer-a",
                        "same scoped claim",
                        "publisher",
                    ),
                    space.SourceAssessment(
                        "copy-b",
                        ArtifactRef("mirror.pdf", sha256="identical-content"),
                        "SUPPORTS",
                        "reviewer-b",
                        "same scoped claim",
                        "mirror",
                    ),
                ],
            )
            notes = json.loads(assessment.notes or "{}")
            self.assertEqual(notes["independent_support_count"], 1)
            self.assertEqual(notes["duplicate_content_group_count"], 1)
            self.assertEqual(notes["provenance_collision_group_count"], 0)
            self.assertIn("DERIVATIVE_SOURCE_COLLISION", notes["conflict_types"])
            self.assertNotIn("PROVENANCE_COLLISION", notes["conflict_types"])

    def test_support_refutation_conflict_stays_unknown_and_opens_challenge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            plan = space.SearchPlan(
                "conflict-plan",
                obligation_id,
                "claim",
                ("query",),
                ("fake",),
                task_id=task_id,
            )
            with patch.dict(
                space.ADAPTERS,
                {"fake": lambda _q, _limit: [{"title": "P", "doi": "10.1/p"}]},
                clear=True,
            ):
                retrieval, _ = space.run_plan(root, plan)
            assessment = space.assess_sources(
                root,
                obligation_id,
                retrieval.receipt_id,
                [
                    space.SourceAssessment(
                        "support",
                        ArtifactRef("support.pdf", sha256="support-content"),
                        "SUPPORTS",
                        "reviewer-a",
                        "same scoped claim",
                        "lineage-a",
                    ),
                    space.SourceAssessment(
                        "refute",
                        ArtifactRef("refute.pdf", sha256="refute-content"),
                        "REFUTES",
                        "reviewer-b",
                        "same scoped claim",
                        "lineage-b",
                    ),
                ],
            )
            self.assertEqual(assessment.verdict, Verdict.UNKNOWN)
            notes = json.loads(assessment.notes or "{}")
            self.assertEqual(notes["claim_outcome"], "CONFLICTED")
            self.assertIn("ASSESSED_RELATION_CONFLICT", notes["conflict_types"])
            challenges = RuntimeStore(root).challenges_for(task_id, obligation_id)
            self.assertEqual(challenges[-1]["kind"], "SOURCE_CONFLICT")

    def test_scoped_not_found_after_reframe_remains_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            plan = self._plan(task_id, obligation_id)
            with patch.dict(space.ADAPTERS, {"fake": lambda _q, _limit: []}, clear=True):
                receipt, result = space.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            self.assertEqual(result["scope_status"], "NOT_FOUND_WITHIN_SCOPE")
            self.assertEqual(
                result["final_query_class"],
                "TRUE_NOT_FOUND_WITHIN_REGISTERED_SCOPE",
            )
            self.assertEqual(result["rounds"][1]["reframe_outcome"], "NO_NOVEL_YIELD")
            self.assertIn("not proof of nonexistence", result["absence_boundary"])

    def test_saturation_is_evaluated_after_the_registered_reframe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            plan = self._plan(
                task_id,
                obligation_id,
                queries=("legacy vocabulary", "later base query"),
                saturation_queries=1,
            )
            calls: list[str] = []

            def fake(query: str, _limit: int) -> list[dict[str, object]]:
                calls.append(query)
                if query == "mechanism vocabulary":
                    return [
                        {
                            "title": "Novel candidate",
                            "doi": "10.1/novel",
                            "source_index": "fake",
                        }
                    ]
                return []

            with patch.dict(space.ADAPTERS, {"fake": fake}, clear=True):
                _, result = space.run_plan(root, plan)
            self.assertEqual(
                calls,
                ["legacy vocabulary", "mechanism vocabulary", "later base query"],
            )
            self.assertEqual(result["queries_executed"], 3)
            self.assertEqual(result["rounds"][1]["reframe_outcome"], "NOVEL_YIELD")
            self.assertEqual(result["rounds"][2]["novel_yield"], 0)

    def test_all_registered_adapters_unavailable_remains_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            plan = space.SearchPlan(
                "all-unavailable",
                obligation_id,
                "question",
                ("query",),
                ("missing", "timeout"),
                task_id=task_id,
            )

            def timeout(_query: str, _limit: int) -> list[dict[str, object]]:
                raise requests.Timeout("bounded failure")

            with patch.dict(space.ADAPTERS, {"timeout": timeout}, clear=True):
                receipt, result = space.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.UNAVAILABLE)
            self.assertEqual(result["successful_calls"], 0)
            self.assertEqual(result["attempted_calls"], 2)
            self.assertEqual(result["scope_status"], "SEARCH_UNAVAILABLE")


    def test_unavailable_reframe_is_not_labeled_true_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            plan_id = "reframe-unavailable"
            hypothesis = space.QueryHypothesis(
                hypothesis_id="qh-unavailable",
                search_plan_id=plan_id,
                obligation_id=obligation_id,
                parent_query_hash=space.canonical_query_hash("base query"),
                query_class=space.QueryClass.TERMINOLOGY_MISMATCH,
                reframe_query="alternate terminology",
                task_id=task_id,
                sources=("missing-reframe-adapter",),
            )
            plan = space.SearchPlan(
                plan_id=plan_id,
                obligation_id=obligation_id,
                question="bounded claim",
                queries=("base query",),
                sources=("base",),
                query_hypotheses=(hypothesis,),
                task_id=task_id,
            )
            with patch.dict(space.ADAPTERS, {"base": lambda _q, _limit: []}, clear=True):
                receipt, result = space.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            self.assertEqual(result["scope_status"], "NOT_FOUND_WITHIN_SCOPE")
            self.assertEqual(result["final_query_class"], "SOURCE_ADAPTER_GAP")
            self.assertEqual(result["reframe_successful_calls"], 0)
            self.assertEqual(result["rounds"][1]["reframe_outcome"], "UNAVAILABLE")

    def test_unbound_legacy_call_is_distinct_from_challenge_off(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            plan_id = "unbound-plan"
            hypothesis = space.QueryHypothesis(
                hypothesis_id="qh-unbound",
                search_plan_id=plan_id,
                obligation_id="legacy-obligation",
                parent_query_hash=space.canonical_query_hash("base query"),
                query_class=space.QueryClass.TERMINOLOGY_MISMATCH,
                reframe_query="alternate terminology",
            )
            plan = space.SearchPlan(
                plan_id=plan_id,
                obligation_id="legacy-obligation",
                question="bounded claim",
                queries=("base query",),
                sources=("base",),
                query_hypotheses=(hypothesis,),
            )
            with patch.dict(space.ADAPTERS, {"base": lambda _q, _limit: []}, clear=True):
                _, result = space.run_plan(root, plan)
            self.assertFalse(result["reframe_executed"])
            self.assertEqual(
                result["reframe_diagnostics"][0]["reframe_outcome"],
                "SKIPPED_UNBOUND",
            )

    def test_challenge_off_restores_baseline_without_executing_reframe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, challenge_mode="off")
            task_id, obligation_id = self._task(root)
            plan = self._plan(task_id, obligation_id)
            calls: list[str] = []

            def fake(query: str, _limit: int) -> list[dict[str, object]]:
                calls.append(query)
                return []

            with patch.dict(space.ADAPTERS, {"fake": fake}, clear=True):
                _, result = space.run_plan(root, plan)
            self.assertEqual(calls, ["legacy vocabulary"])
            self.assertFalse(result["reframe_executed"])
            self.assertEqual(
                result["reframe_diagnostics"][0]["reframe_outcome"],
                "SKIPPED_CHALLENGE_OFF",
            )
            self.assertEqual(RuntimeStore(root).challenges_for(task_id, obligation_id), [])

    def test_plan_rejects_order_dependent_duplicate_load_bearing_reframes(self) -> None:
        parent_hash = space.canonical_query_hash("base")
        hypotheses = tuple(
            space.QueryHypothesis(
                hypothesis_id=f"qh-{index}",
                search_plan_id="ambiguous-plan",
                obligation_id="obligation",
                parent_query_hash=parent_hash,
                query_class=space.QueryClass.TERMINOLOGY_MISMATCH,
                reframe_query=f"reframe {index}",
            )
            for index in range(2)
        )
        with self.assertRaisesRegex(ValueError, "at most one load-bearing"):
            space.SearchPlan(
                "ambiguous-plan",
                "obligation",
                "question",
                ("base",),
                query_hypotheses=hypotheses,
            )

    def test_query_class_taxonomy_is_frozen(self) -> None:
        self.assertEqual(
            {item.value for item in space.QueryClass},
            {
                "TERMINOLOGY_MISMATCH",
                "REPRESENTATION_MISMATCH",
                "SOURCE_ADAPTER_GAP",
                "QUERY_TOO_NARROW",
                "QUERY_TOO_BROAD",
                "NEIGHBOR_FIELD_MISSED",
                "CITATION_CHAIN_NOT_TRAVERSED",
                "DERIVATIVE_SOURCE_COLLISION",
                "STALE_SOURCE",
                "TRUE_NOT_FOUND_WITHIN_REGISTERED_SCOPE",
            },
        )

    def test_persisted_runtime_state_contains_hashes_not_raw_queries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, obligation_id = self._task(root)
            base_query = "raw-private-base-query-token"
            reframe_query = "raw-private-reframe-query-token"
            plan = self._plan(
                task_id,
                obligation_id,
                base_query=base_query,
                reframe_query=reframe_query,
            )
            with patch.dict(space.ADAPTERS, {"fake": lambda _q, _limit: []}, clear=True):
                space.run_plan(root, plan)

            state_root = root / ".egrt" / "state"
            persisted = "\n".join(
                path.read_text(encoding="utf-8")
                for path in state_root.rglob("*.json")
            )
            self.assertNotIn(base_query, persisted)
            self.assertNotIn(reframe_query, persisted)
            self.assertIn(space.canonical_query_hash(base_query), persisted)
            self.assertIn(space.canonical_query_hash(reframe_query), persisted)


if __name__ == "__main__":
    unittest.main()
