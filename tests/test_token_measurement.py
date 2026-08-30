from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gauntlet_host import gauntlet_plugin
from gauntlet_host.runtime_profile import _measurement_key
from gauntlet_host.token_measurement import summarize_measurements
from gauntlet_host.token_measurement_bridge import (
    TokenMeasurementError,
    _reject_raw_and_authority_keys,
    build_measurement,
)


def _base(dispatch_id: str, request_kind: str) -> dict[str, object]:
    return {
        "schema": "gauntlet.token-measurement.v1",
        "request_kind": request_kind,
        "task_id": "task-0000000000000000",
        "host_request_id": "req-0000000000000000",
        "dispatch_id": dispatch_id,
        "attempt": 1,
        "retry_count": 0,
        "fallback_index": None,
        "fallback_detected": False,
        "tool_call_count": None,
        "auxiliary_stream": False,
        "request_composition": {
            "payload_hmac_sha256": "a" * 64,
            "canonical_chars": 1,
            "canonical_utf8_bytes": 1,
            "wire_utf8_bytes": None,
            "local_estimated_tokens": 1,
            "reconciliation": {
                "non_overlapping": True,
                "reconciles_to_canonical_payload": True,
            },
            "components": {
                "conversation_user": {
                    "availability": "MEASURED",
                    "items": 1,
                    "chars": 1,
                    "utf8_bytes": 1,
                    "local_estimated_tokens": 1,
                    "hmac_sha256": "b" * 64,
                }
            },
        },
        "provider_usage": {
            "source": "provider_reported",
            "input_tokens": None,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
            "billable_input_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "total_tokens": None,
        },
        "outcome": {"status": "OK"},
        "timing": {
            "started_at": "2026-08-30T00:00:00Z",
            "finished_at": "2026-08-30T00:00:01Z",
            "latency_ms": 1,
            "time_to_first_token_ms": None,
        },
        "endpoint_identity": {},
        "source": {},
        "runtime_estimates": {},
        "cost": {"status": "UNPRICED"},
        "digest_key_id": "c" * 16,
        "privacy": {
            "raw_prompt_persisted": False,
            "raw_tool_output_persisted": False,
            "raw_response_persisted": False,
        },
    }


class TokenMeasurementPrivacyTests(unittest.TestCase):
    def test_raw_and_authority_fields_are_rejected_recursively(self) -> None:
        for value in (
            {"nested": {"prompt": "secret"}},
            {"nested": [{"tool_output": "secret"}]},
            {"nested": {"verdict": "PASS"}},
        ):
            with self.subTest(value=value):
                with self.assertRaises(TokenMeasurementError):
                    _reject_raw_and_authority_keys(value)

    def test_request_measurement_persists_hmac_and_counts_not_prompt(self) -> None:
        canary = "TOKEN000_PRIVATE_CANARY"
        result = gauntlet_plugin._request_measurement(
            {"messages": [{"role": "user", "content": canary}]},
            b"k" * 32,
        )
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(canary, serialized)
        user = result["components"]["conversation_user"]
        self.assertEqual(user["items"], 1)
        self.assertEqual(user["utf8_bytes"], len(canary.encode("utf-8")))
        self.assertRegex(user["hmac_sha256"], r"^[0-9a-f]{64}$")

    def test_provider_usage_preserves_null_versus_zero(self) -> None:
        unknown = gauntlet_plugin._usage_record({})
        zero = gauntlet_plugin._usage_record(
            {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "prompt_tokens_details": {"cached_tokens": 0},
            }
        )
        self.assertIsNone(unknown["input_tokens"])
        self.assertIsNone(unknown["cache_read_tokens"])
        self.assertEqual(zero["input_tokens"], 0)
        self.assertEqual(zero["cache_read_tokens"], 0)
        self.assertEqual(zero["output_tokens"], 0)
        self.assertEqual(zero["total_tokens"], 0)


class TokenMeasurementStorageTests(unittest.TestCase):
    def test_bridge_rejects_malformed_component_digest(self) -> None:
        value = _base("dispatch-main", "conversation")
        value["request_composition"]["components"]["conversation_user"]["hmac_sha256"] = (
            "not-a-digest"
        )
        environment = {
            "GAUNTLET_TASK_ID": "task-0000000000000000",
            "GAUNTLET_HOST_REQUEST_ID": "req-0000000000000000",
        }
        with patch.dict("os.environ", environment, clear=False):
            with self.assertRaises(TokenMeasurementError):
                build_measurement(value)

    def test_bridge_provenance_matches_request_kind(self) -> None:
        environment = {
            "GAUNTLET_TASK_ID": "task-0000000000000000",
            "GAUNTLET_HOST_REQUEST_ID": "req-0000000000000000",
        }
        with patch.dict("os.environ", environment, clear=False):
            conversation = build_measurement(_base("dispatch-main", "conversation"))
            auxiliary = build_measurement(_base("dispatch-aux", "auxiliary"))
        self.assertEqual(
            conversation["provenance"]["event_source"],
            "hermes.llm_execution",
        )
        self.assertEqual(
            auxiliary["provenance"]["event_source"],
            "agent.auxiliary_client.relay",
        )

    def test_summary_reconciles_main_and_auxiliary_separately(self) -> None:
        task_id = "task-0000000000000000"
        request_id = "req-0000000000000000"
        environment = {
            "GAUNTLET_TASK_ID": task_id,
            "GAUNTLET_HOST_REQUEST_ID": request_id,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict("os.environ", environment, clear=False):
                documents = [
                    build_measurement(_base("dispatch-main", "conversation")),
                    build_measurement(_base("dispatch-aux", "auxiliary")),
                ]
            task_bucket = hashlib.sha256(task_id.encode()).hexdigest()[:24]
            request_bucket = hashlib.sha256(request_id.encode()).hexdigest()[:24]
            target = root / "measurements" / "token-efficiency" / task_bucket / request_bucket
            target.mkdir(parents=True)
            for document in documents:
                path = target / f"{document['measurement_id']}.json"
                path.write_text(
                    json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            summary = summarize_measurements(
                str(root),
                task_id=task_id,
                request_id=request_id,
                expected_api_calls=1,
                provider_usage={},
            )
        self.assertTrue(summary["measurement_complete"])
        self.assertEqual(summary["dispatches_recorded"], 2)
        self.assertEqual(summary["conversation_dispatches_recorded"], 1)
        self.assertEqual(summary["auxiliary_dispatches_recorded"], 1)
        self.assertEqual(summary["measurement_drop_count"], 0)

    def test_measurement_key_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "measurements" / ".hmac-key"
            path.parent.mkdir(parents=True)
            first_path, first_id = _measurement_key(path)
            first_bytes = first_path.read_bytes()
            second_path, second_id = _measurement_key(path)
            second_bytes = second_path.read_bytes()
        self.assertEqual(first_path, second_path)
        self.assertEqual(first_id, second_id)
        self.assertEqual(first_bytes, second_bytes)


if __name__ == "__main__":
    unittest.main()
