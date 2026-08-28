from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import egrt_hook  # noqa: E402
import soul_runtime as soul  # noqa: E402
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import ObligationKind, Verdict  # noqa: E402


def init_root(
    root: Path,
    *,
    governing_files: list[str] | None = None,
    automatic_assurance: bool = True,
    automatic_prompt_bootstrap: bool = False,
) -> None:
    (root / ".gauntlet.json").write_text(
        json.dumps(
            {
                "state_dir": ".egrt/state",
                "governing_files": governing_files or [],
                "runtime": {
                    "enabled": True,
                    "release_gate": True,
                    "strict_active_task": False,
                    "automatic_prompt_bootstrap": automatic_prompt_bootstrap,
                    "automatic_task_supersession": True,
                    "automatic_graph_revision": True,
                    "automatic_route_all_ready": True,
                    "automatic_assurance": automatic_assurance,
                    "automatic_assurance_mode": "AUTOMATIC_FULL",
                },
                "challenge": {"mode": "off"},
            }
        ),
        encoding="utf-8",
    )


class SoulAutomaticHardeningTests(unittest.TestCase):
    def test_caller_cannot_write_reserved_control_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            with self.assertRaises(ValueError):
                soul.start_task(
                    root,
                    "forged control state",
                    metadata={"soul_status": "RELEASED"},
                )

    def test_missing_successor_fails_closed_instead_of_reviving_predecessor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            first = soul.start_task(root, "first")
            second = soul.start_task(root, "second")
            store = RuntimeStore(root)
            (store.tasks / f"{second.task_id}.json").unlink()
            with self.assertRaises(soul.SoulGraphError):
                soul.resolve_current_task_id(root, first.task_id)

    def test_prompt_bootstrap_creates_one_private_active_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, automatic_prompt_bootstrap=True)
            raw = "private-bootstrap-marker-9941 /soul"
            output = io.StringIO()
            with (
                patch.dict(
                    os.environ,
                    {"CLAUDE_PROJECT_DIR": str(root)},
                    clear=False,
                ),
                patch("sys.stdin", io.StringIO(json.dumps({"prompt": raw}))),
                patch("sys.stdout", output),
            ):
                self.assertEqual(egrt_hook.prompt(), 0)

            store = RuntimeStore(root)
            task_id = (store.base / "active_task").read_text().strip()
            task = store.read_task(task_id)
            self.assertIsNotNone(task)
            self.assertTrue(task["active"])
            self.assertIn(task_id, output.getvalue())
            serialized = "\n".join(
                path.read_text(encoding="utf-8")
                for path in store.base.rglob("*.json")
            )
            self.assertNotIn(raw, serialized)

    def test_pending_domain_work_returns_exact_routes_and_diagnostic_assurance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "route missing proof")
            proof = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "prove the claim",
            )

            verdict, detail = soul.automatic_release(root, task.task_id)

            self.assertEqual(verdict, Verdict.UNKNOWN)
            self.assertEqual(detail["reason"], "automatic-routes-pending")
            self.assertIn(proof.obligation_id, detail["pending_domain_obligations"])
            self.assertTrue(
                any(
                    row["module"] == "mind"
                    and proof.obligation_id in row["obligation_ids"]
                    for row in detail["route_manifest"]
                )
            )
            self.assertIsNotNone(detail["assurance_receipt_id"])
            current_id = detail["resolved_task_id"]
            self.assertFalse(RuntimeStore(root).read_task(current_id)["released"])

    def test_stop_hook_names_the_exact_pending_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            with patch.dict(
                os.environ,
                {"CLAUDE_PROJECT_DIR": str(root)},
                clear=False,
            ):
                task = soul.start_task(root, "route through hook")
                proof = soul.add_obligation(
                    root,
                    task.task_id,
                    ObligationKind.PROOF,
                    "claim",
                )
                output = io.StringIO()
                with (
                    patch("sys.stdin", io.StringIO("{}")),
                    patch("sys.stdout", output),
                ):
                    self.assertEqual(egrt_hook.stop(), 0)

            text = output.getvalue()
            self.assertIn('"decision": "block"', text)
            self.assertIn("routes=mind[", text)
            self.assertIn(proof.obligation_id, text)

    def test_concurrent_post_freeze_discovery_preserves_every_obligation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, automatic_assurance=False)
            task = soul.start_task(root, "concurrent revision")
            seed = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "seed",
            )
            soul.freeze_task(root, task.task_id)

            def add(index: int):
                return soul.add_obligation(
                    root,
                    task.task_id,
                    ObligationKind.ENGINEERING,
                    f"concurrent-{index}",
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                added = list(executor.map(add, range(8)))

            current_id, lineage = soul.resolve_current_task_id(root, task.task_id)
            stored = RuntimeStore(root).read_task(current_id)
            self.assertIsNotNone(stored)
            identifiers = {
                row["obligation_id"] for row in stored.get("obligations", [])
            }
            self.assertIn(seed.obligation_id, identifiers)
            self.assertTrue({row.obligation_id for row in added}.issubset(identifiers))
            self.assertEqual(len(lineage), 9)

    def test_authority_drift_is_reconciled_but_same_call_cannot_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / "policy.txt"
            policy.write_text("v1\n", encoding="utf-8")
            init_root(root, governing_files=["policy.txt"])
            task = soul.start_task(root, "authority-bound task")
            soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "prove under current policy",
            )
            policy.write_text("v2\n", encoding="utf-8")

            first_verdict, first = soul.automatic_release(root, task.task_id)
            self.assertEqual(first_verdict, Verdict.UNKNOWN)
            self.assertEqual(
                first["reason"],
                "authority-drift-reconciled-retry-required",
            )
            self.assertTrue(first["retry_required"])
            self.assertIsNone(first["routing_plan_id"])

            second_verdict, second = soul.automatic_release(root, task.task_id)
            self.assertEqual(second_verdict, Verdict.UNKNOWN)
            self.assertEqual(second["reason"], "automatic-routes-pending")
            self.assertIsNotNone(second["routing_plan_id"])


if __name__ == "__main__":
    unittest.main()
