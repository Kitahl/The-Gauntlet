from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "benchmarks" / "harness" / "codex_dose_response_runner.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("codex_dose_response_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_receipt(
    *,
    kind: str = "units",
    call_id: str = "unit",
    model: str = "gpt-5.6-terra",
    effort: str = "low",
    prompt: str = "test",
    answer: str = "A",
    frozen_commit: str | None = None,
    codex_cli_version: str = "codex-cli 1",
) -> dict[str, object]:
    return {
        "schema": "foil-codex-dose-receipt/v1",
        "kind": kind,
        "call_id": call_id,
        "model": model,
        "effort": effort,
        "codex_version": codex_cli_version,
        "pre_call_commit": d("commit") if frozen_commit is None else frozen_commit,
        "started_at": "2026-08-24T00:00:00+00:00",
        "finished_at": "2026-08-24T00:00:01+00:00",
        "wall_seconds": 1.0,
        "returncode": 0,
        "timed_out": False,
        "prompt_sha256": runner.sha256_text(prompt),
        "stdout_sha256": d("stdout"),
        "stderr_sha256": d("stderr"),
        "last_output_sha256": d("last"),
        "event_types": ["thread.started", "turn.completed"],
        "usage": {"input_tokens": 1, "output_tokens": 1},
        "answer": answer,
        "valid": True,
        "invalid_reasons": [],
    }


def item(index: int) -> dict[str, object]:
    row: dict[str, object] = {
        "id": f"item-{index}",
        "source_index": index,
        "question": f"Question {index}?",
        "choices": {"A": "one", "B": "two", "C": "three", "D": "four"},
        "expert_accuracy": 0.5,
        "nonexpert_accuracy": 0.25,
        "difficulty": "Graduate",
    }
    row["item_sha256"] = d(json.dumps(row, sort_keys=True))
    return row


class FrozenPilotTests(unittest.TestCase):
    def test_canonical_gpqa_difficulty_labels_are_closed_and_match_expected_scope(self) -> None:
        self.assertTrue(
            runner.hard_difficulty(
                "Hard undergraduate level (could be a question on a hard undergraduate exam)"
            )
        )
        self.assertTrue(runner.hard_difficulty("Hard graduate level (PhD exam)"))
        self.assertTrue(runner.hard_difficulty("Post-graduate level or harder"))
        self.assertFalse(runner.hard_difficulty("Easy undergraduate level (or easier)"))
        self.assertFalse(runner.hard_difficulty("graduate"))

    def test_three_item_matrix_and_call_cap_are_exact(self) -> None:
        self.assertEqual((runner.TARGET, runner.EXPECTED_UNITS), (3, 36))
        self.assertEqual((runner.EXPECTED_PAIRS, runner.MAX_CALLS), (18, 42))
        units = runner.build_units([item(0), item(1), item(2)])
        self.assertEqual(len(units), 36)
        self.assertEqual(len({row["unit_id"] for row in units}), 36)
        groups = {
            (row["item_id"], row["config_id"], row["condition_id"])
            for row in units
        }
        self.assertEqual(len(groups), 36)

    def test_execution_flags_are_ephemeral_read_only_and_schema_bound(self) -> None:
        argv = runner.build_argv("gpt-5.6-terra", "high", Path("work"), Path("last"))
        self.assertEqual(argv[:2], ["codex", "exec"])
        self.assertIn("read-only", argv)
        self.assertIn("--ephemeral", argv)
        self.assertIn("--ignore-user-config", argv)
        self.assertIn("--ignore-rules", argv)
        self.assertIn("--output-schema", argv)
        self.assertEqual(argv[-1], "-")

    def test_stream_parser_surfaces_tool_events_and_bad_json(self) -> None:
        payload = "\n".join(
            (
                json.dumps({"type": "item.completed", "item": {"type": "tool_call"}}),
                "not-json",
            )
        )
        parsed = runner.parse_stream(payload)
        self.assertEqual(parsed["jsonl_parse_errors"], 1)
        self.assertTrue(parsed["tool_events"])

    def test_answer_parser_is_closed(self) -> None:
        self.assertEqual(runner.parse_answer('{"answer":"B"}'), ("B", None))
        self.assertIsNotNone(runner.parse_answer('{"answer":"B","reason":"x"}')[1])
        self.assertIsNotNone(runner.parse_answer("B")[1])

    def test_call_cap_stops_before_subprocess_or_file_creation(self) -> None:
        with (
            mock.patch.object(runner, "call_count", return_value=runner.MAX_CALLS),
            mock.patch.object(runner.subprocess, "run") as process,
            self.assertRaises(runner.ProtocolError),
        ):
            runner.execute_call(
                kind="units",
                call_id="blocked",
                model="gpt-5.6-terra",
                effort="low",
                prompt="test",
                frozen_commit=d("commit"),
                codex_cli_version="codex-cli 1",
            )
        process.assert_not_called()

    def test_orphaned_private_attempt_prohibits_retry_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            raw_dir = Path(temporary) / "private" / "units" / "orphaned"
            raw_dir.mkdir(parents=True)
            public = Path(temporary) / "receipt.json"
            with (
                mock.patch.object(runner, "receipt_path", return_value=public),
                mock.patch.object(runner, "PRIVATE", Path(temporary) / "private"),
                mock.patch.object(runner, "call_count", return_value=0),
                mock.patch.object(runner.subprocess, "run") as process,
                self.assertRaises(runner.ProtocolError),
            ):
                runner.execute_call(
                    kind="units",
                    call_id="orphaned",
                    model="gpt-5.6-terra",
                    effort="low",
                    prompt="test",
                    frozen_commit=d("commit"),
                    codex_cli_version="codex-cli 1",
                )
            process.assert_not_called()

    def test_protocol_hash_is_part_of_the_frozen_manifest(self) -> None:
        self.assertEqual(
            runner.PROTOCOL.name,
            "FOIL_CODEX_DOSE_RESPONSE_SMALL_PILOT.md",
        )
        with mock.patch.object(runner, "now", return_value="frozen"):
            manifest = runner.build_manifest(
                [item(0), item(1), item(2)],
                source_archive_sha256=d("archive"),
            )
        self.assertEqual(manifest["sample_n"], 3)
        self.assertEqual(manifest["scored_call_count"], 36)
        self.assertEqual(manifest["control_call_count"], 6)
        self.assertEqual(manifest["call_cap"], 42)
        self.assertEqual(len(manifest["protocol_sha256"]), 64)

    def test_closed_event_shapes_allow_messages_and_reject_unknown_tool_transports(self) -> None:
        allowed = "\n".join(
            (
                json.dumps({"type": "thread.started"}),
                json.dumps({"type": "turn.started"}),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message"},
                    }
                ),
                json.dumps({"type": "turn.completed", "usage": {"output_tokens": 1}}),
            )
        )
        parsed = runner.parse_stream(allowed)
        self.assertEqual(parsed["tool_events"], [])
        forbidden = runner.parse_stream(
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "custom_function_call"},
                }
            )
        )
        self.assertTrue(forbidden["tool_events"])
        malformed = runner.parse_stream(json.dumps(["not", "an", "event"]))
        self.assertTrue(malformed["tool_events"])
        malformed_item = runner.parse_stream(
            json.dumps({"type": "thread.started", "item": "opaque"})
        )
        self.assertTrue(malformed_item["tool_events"])
        self.assertTrue(runner.parse_stream("")["tool_events"])

    def test_resume_rejects_valid_receipt_with_wrong_binding_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "receipt.json"
            runner.write_json(
                path,
                valid_receipt(call_id="unit", model="gpt-5.6-sol"),
            )
            with (
                mock.patch.object(runner, "receipt_path", return_value=path),
                mock.patch.object(runner.subprocess, "run") as process,
                self.assertRaises(runner.ProtocolError),
            ):
                runner.execute_call(
                    kind="units",
                    call_id="unit",
                    model="gpt-5.6-terra",
                    effort="low",
                    prompt="test",
                    frozen_commit=d("commit"),
                    codex_cli_version="codex-cli 1",
                )
            process.assert_not_called()

    def test_prepare_refuses_any_existing_frozen_output_before_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            existing = root / "items.json"
            existing.write_text("already frozen", encoding="utf-8")
            with (
                mock.patch.object(runner, "ITEMS", existing),
                mock.patch.object(runner, "MANIFEST", root / "manifest.json"),
                mock.patch.object(runner, "CONDITION_MAP", root / "condition.json"),
                mock.patch.object(runner, "SCHEMA_FILE", root / "schema.json"),
                mock.patch.object(runner, "LOCK", root / "lock.json"),
                mock.patch.object(runner, "RECEIPTS", root / "receipts"),
                mock.patch.object(runner, "PREDICTIONS", root / "predictions.json"),
                mock.patch.object(runner, "RESULTS", root / "results.json"),
                mock.patch.object(runner, "fetch_archive") as fetch,
                self.assertRaises(runner.ProtocolError),
            ):
                runner.prepare()
            fetch.assert_not_called()

    def test_source_archive_digest_is_checked_before_parsing(self) -> None:
        with self.assertRaises(runner.ProtocolError):
            runner.load_rows(b"not the archive", expected_sha256=d("different"))

    def test_private_ignore_is_a_hard_pre_call_gate(self) -> None:
        with (
            mock.patch.object(runner, "validate_lock"),
            mock.patch.object(runner, "frozen_artifacts", return_value=()),
            mock.patch.object(runner, "git_ignored", return_value=False),
            self.assertRaises(runner.ProtocolError),
        ):
            runner.require_frozen_artifacts_committed()

    def test_scoring_rejects_prediction_answer_that_differs_from_receipt(self) -> None:
        items = [item(0), item(1), item(2)]
        units = runner.build_units(items)
        manifest = {"units": units}
        items_payload = {"items": items}
        condition = runner.condition_payload()
        predictions = {
            "schema": "foil-codex-dose-predictions/v1",
            "manifest_sha256": d("file"),
            "complete": True,
            "predictions": [
                {
                    "unit_id": unit["unit_id"],
                    "item_id": unit["item_id"],
                    "config_id": unit["config_id"],
                    "condition_id": unit["condition_id"],
                    "answer": "A",
                    "valid": True,
                    "receipt_sha256": d("file"),
                }
                for unit in units
            ],
        }
        receipt = valid_receipt(answer="B")
        with (
            mock.patch.object(
                runner,
                "validate_controls",
                return_value=(d("commit"), "codex-cli 1"),
            ),
            mock.patch.object(runner, "require_receipts_committed"),
            mock.patch.object(runner, "sha256_file", return_value=d("file")),
            mock.patch.object(runner, "read_json", return_value=receipt),
            mock.patch.object(runner, "validate_receipt_binding", return_value=receipt),
            mock.patch.object(runner, "validate_private_material"),
            self.assertRaises(runner.ProtocolError),
        ):
            runner.validate_scoring_bindings(
                manifest,
                items_payload,
                condition,
                predictions,
            )

    def test_scoring_requires_exact_42_receipt_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            receipts = Path(temporary)
            extra = receipts / "units" / "extra.json"
            extra.parent.mkdir(parents=True)
            extra.write_text("{}", encoding="utf-8")
            manifest = {"units": runner.build_units([item(0), item(1), item(2)])}
            with (
                mock.patch.object(runner, "RECEIPTS", receipts),
                self.assertRaises(runner.ProtocolError),
            ):
                runner.require_receipts_committed(manifest)


if __name__ == "__main__":
    unittest.main()
