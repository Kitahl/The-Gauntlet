"""Contract tests for the content-addressed FOIL v5 shadow protocol."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_v5_protocol as protocol  # noqa: E402


def example_protocol() -> dict[str, object]:
    path = ROOT / "validation" / "foil_v5_protocol.example.json"
    return json.loads(path.read_text(encoding="utf-8"))


class ProtocolContractTests(unittest.TestCase):
    def test_example_is_complete_but_unsealed(self) -> None:
        candidate = example_protocol()
        protocol.validate_protocol(candidate)
        self.assertNotIn("protocol_sha256", candidate)

    def test_seal_is_canonical_and_verifiable(self) -> None:
        first = protocol.seal_protocol(example_protocol())
        second = protocol.seal_protocol(example_protocol())
        self.assertEqual(first["protocol_sha256"], second["protocol_sha256"])
        protocol.validate_protocol(first, require_seal=True)

    def test_tamper_is_detected(self) -> None:
        sealed = protocol.seal_protocol(example_protocol())
        sealed["bindings"]["scanner_sha256"] = "9" * 64  # type: ignore[index]
        with self.assertRaisesRegex(protocol.ProtocolValidationError, "does not match"):
            protocol.validate_protocol(sealed, require_seal=True)

    def test_reseal_cannot_preserve_a_stale_candidate_identity(self) -> None:
        sealed = protocol.seal_protocol(example_protocol())
        changed = copy.deepcopy(sealed)
        changed["candidate_sha256"] = "9" * 64
        with self.assertRaisesRegex(protocol.ProtocolValidationError, "cannot re-seal"):
            protocol.seal_protocol(changed)

    def test_all_bindings_and_disjoint_partitions_are_required(self) -> None:
        missing = example_protocol()
        del missing["bindings"]["parser_sha256"]  # type: ignore[index]
        with self.assertRaisesRegex(protocol.ProtocolValidationError, "bindings missing"):
            protocol.validate_protocol(missing)
        overlap = example_protocol()
        overlap["partitions"]["lock"]["item_ids"] = ["dev-1"]  # type: ignore[index]
        with self.assertRaisesRegex(protocol.ProtocolValidationError, "must be disjoint"):
            protocol.validate_protocol(overlap)

    def test_gate_cannot_default_to_a_promotion_threshold(self) -> None:
        candidate = example_protocol()
        candidate["gates"]["residual_recall"]["bound"] = None  # type: ignore[index]
        with self.assertRaisesRegex(protocol.ProtocolValidationError, "cannot be null"):
            protocol.validate_protocol(candidate)

    def test_effect_contract_rejects_unknown_or_ambiguous_effectors(self) -> None:
        unknown = example_protocol()
        unknown["allowed_effect_classes"].append("mystery")  # type: ignore[index]
        with self.assertRaisesRegex(protocol.ProtocolValidationError, "unknown class"):
            protocol.validate_protocol(unknown)
        ambiguous = example_protocol()
        ambiguous["allowed_effect_classes"].append("network")  # type: ignore[index]
        with self.assertRaisesRegex(protocol.ProtocolValidationError, "both allowed and forbidden"):
            protocol.validate_protocol(ambiguous)

    def test_authority_is_bound_to_candidate(self) -> None:
        candidate = example_protocol()
        candidate["authority"]["candidate_id"] = "other"  # type: ignore[index]
        with self.assertRaisesRegex(protocol.ProtocolValidationError, "must bind"):
            protocol.validate_protocol(candidate)


if __name__ == "__main__":
    unittest.main()
