from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_v5_protocol import seal_protocol  # noqa: E402
from foil_v5_runtime import MANIFEST_SCHEMA, RECEIPT_SCHEMA, run_manifest  # noqa: E402


def protocol() -> dict:
    return {
        "schema": "egrt.foil-v5-protocol.v1",
        "candidate_id": "runtime-test",
        "candidate_sha256": "a" * 64,
        "bindings": {
            "model_config_sha256": "b" * 64,
            "system_prompt_sha256": "c" * 64,
            "foil_skill_sha256": "d" * 64,
            "task_prompt_sha256": "e" * 64,
            "tool_regime_sha256": "f" * 64,
            "base_answers_sha256": "1" * 64,
            "scanner_sha256": "2" * 64,
            "diagnostic_bank_sha256": "3" * 64,
            "parser_sha256": "4" * 64,
            "applicability_sha256": "5" * 64,
        },
        "partitions": {
            "development": {"artifact_sha256": "6" * 64, "item_ids": ["d"]},
            "lock": {"artifact_sha256": "7" * 64, "item_ids": ["l"]},
            "prospective": {"artifact_sha256": "8" * 64, "item_ids": ["p"]},
        },
        "gates": {
            name: {"metric": name, "direction": "required", "bound": True}
            for name in (
                "compiler_coverage", "compiler_precision", "verifier_validity", "residual_recall",
                "false_activation_rate", "incremental_value", "cost_completeness", "negative_controls",
            )
        },
        "allowed_effect_classes": ["local", "parser"],
        "forbidden_effect_classes": ["model", "tool", "network", "subprocess", "retry", "async", "profile", "router"],
        "no_answer_taxonomy": ["MALFORMED"],
        "authority": {"issuer": "test", "expires_at": "2027-01-01T00:00:00Z", "replay_protection": "nonce", "candidate_id": "runtime-test"},
    }


def manifest() -> dict:
    return {
        "schema": MANIFEST_SCHEMA,
        "g0_mode": "seal",
        "g0_protocol": protocol(),
        "bindings": {"a0_digest": "a" * 64, "task_digest": "b" * 64, "spec_digest": "c" * 64, "compiler_digest": "d" * 64, "config_digest": "e" * 64},
        "claim": {"statement": "value must match", "kind": "EXACT_MATCH", "decidability": "DETERMINISTIC", "applicability": "APPLICABLE", "reason": "exact predicate", "required_verifiers": ["builtin.exact_match"]},
        "observed_a0_digest": "a" * 64,
        "diagnostic_needs": [{"need_id": "need-1", "description": "exact value", "verifier_id": "builtin.exact_match", "weight_units": 3, "decidability": "DETERMINISTIC", "applicability": "APPLICABLE"}],
        "cases": [{"need_id": "need-1", "verifier_input": {"actual": "x", "expected": "x"}, "metadata": {"source": "fixture"}}],
        "declared_coverage": [{"need_id": "need-1", "evidence_digest": "f" * 64, "outcome": "PASS", "reason": "declared pass"}],
        "adjudicated_coverage": [{"need_id": "need-1", "evidence_digest": "1" * 64, "outcome": "PASS", "reason": "adjudicated pass"}],
    }


class ShadowRuntimeTests(unittest.TestCase):
    def test_seals_runs_and_emits_digest_only_receipt(self) -> None:
        receipt = run_manifest(manifest())
        self.assertEqual((receipt["schema"], receipt["scope"], receipt["status"]), (RECEIPT_SCHEMA, "ONE_CLAIM_V1", "PASS"))
        self.assertEqual(receipt["declared_coverage"]["covered_mass"], 3)
        self.assertEqual(receipt["adjudicated_coverage"]["covered_count"], 1)
        self.assertTrue(receipt["receipt_sha256"])
        serialized = json.dumps(receipt)
        self.assertNotIn("value must match", serialized)
        self.assertNotIn('"actual": "x"', serialized)
        self.assertFalse(receipt["execution_authorized"])
        self.assertFalse(receipt["repair_generated"])

    def test_verifies_a_presealed_g0_protocol_and_can_map_authority(self) -> None:
        data = manifest()
        sealed = seal_protocol(data["g0_protocol"])
        data["g0_mode"], data["g0_protocol"] = "verify", sealed
        data["cases"][0]["verifier_input"] = {"actual": "x", "expected": "y"}
        digest = sealed["protocol_sha256"]
        data["authority"] = {
            "registration": {"sensor_id": "sensor-1", "evidence_class": "MEASURED", "surface": "ANSWER", "authority_ceiling": "REPAIR_PROPOSAL_ALLOWED", "claim_scope": "answer.code", "producer": "foil.sensor", "version": "1"},
            "calibration_context": {"scope_digest": "0" * 64, "model_digest": "1" * 64, "config_digest": "e" * 64, "protocol_digest": digest, "evidence_digest": "2" * 64, "thresholds_digest": "3" * 64, "now": "2026-08-24T00:00:00+00:00"},
            "calibration": {"sensor_id": "sensor-1", "calibration_id": "cal-1", "scope_digest": "0" * 64, "model_digest": "1" * 64, "config_digest": "e" * 64, "protocol_digest": digest, "evidence_digest": "2" * 64, "thresholds_digest": "3" * 64, "correct_outputs": 10, "false_flags": 1, "wrong_outputs": 8, "true_flags": 6, "expires_at": "2026-08-25T00:00:00+00:00"},
            "authority_context": {"repair_proposals_enabled": True, "calibration_current": True, "owner_risk_allows_repair": True},
        }
        receipt = run_manifest(data)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["authority"]["calibration_state"], "CURRENT")
        self.assertEqual(receipt["authority"]["action"], "PROPOSE_REPAIR_SHADOW")
        self.assertFalse(receipt["authority"]["execution_authorized"])

    def test_missing_malformed_or_non_deterministic_fields_fail_closed(self) -> None:
        bad = manifest()
        del bad["claim"]
        self.assertEqual(run_manifest(bad)["status"], "UNKNOWN")
        mismatch = manifest()
        mismatch["observed_a0_digest"] = "f" * 64
        self.assertEqual(run_manifest(mismatch)["status"], "UNKNOWN")
        empirical = manifest()
        empirical["diagnostic_needs"][0]["decidability"] = "EMPIRICAL"
        self.assertEqual(run_manifest(empirical)["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
