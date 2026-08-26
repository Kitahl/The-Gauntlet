from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_contract_audit as contract_audit  # noqa: E402


class ContractAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = (ROOT / "skills" / "foil" / "SKILL.md").read_text(encoding="utf-8")
        cls.document = json.loads(
            (ROOT / "docs" / "FOIL_SPEC_CONTRACT_MAP.json").read_text(encoding="utf-8")
        )

    def test_all_sections_and_normative_modal_lines_are_closed(self) -> None:
        report = contract_audit.audit_document(self.skill_text, self.document, root=ROOT)
        self.assertEqual(report["sections"], 19)
        self.assertEqual(report["normative_modal_lines"], 35)
        self.assertEqual(report["modal_word_occurrences"], 36)
        self.assertEqual(report["unmapped_lines"], 0)
        self.assertEqual(report["extra_mapped_lines"], 0)
        self.assertEqual(sum(report["coverage_counts"].values()), 35)

    def test_new_unmapped_modal_fails_closed(self) -> None:
        changed = self.skill_text + "\nFOIL must silently trust this new clause.\n"
        with self.assertRaisesRegex(ValueError, "normative coverage mismatch"):
            contract_audit.audit_document(changed, self.document, root=ROOT)

    def test_stale_source_anchor_fails_closed(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["entries"][0]["source_contains"] = "not present"
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            contract_audit.audit_document(self.skill_text, changed, root=ROOT)

    def test_missing_evidence_path_fails_closed(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["entries"][0]["evidence"] = ["tests/not-a-real-test.py"]
        with self.assertRaisesRegex(ValueError, "evidence does not exist"):
            contract_audit.audit_document(self.skill_text, changed, root=ROOT)

    def test_untestable_clause_cannot_claim_executable_evidence(self) -> None:
        changed = copy.deepcopy(self.document)
        entry = next(item for item in changed["entries"] if item["coverage"] == "UNTESTABLE_AS_WRITTEN")
        entry["evidence"] = ["tests/test_egrt_claims.py"]
        with self.assertRaisesRegex(ValueError, "cannot claim evidence"):
            contract_audit.audit_document(self.skill_text, changed, root=ROOT)


if __name__ == "__main__":
    unittest.main()
