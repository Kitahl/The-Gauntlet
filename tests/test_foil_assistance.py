"""D3, D8 - one assistance/ownership vocabulary for the contract and the runtime."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_assistance import (  # noqa: E402
    Assistance,
    ExecutionOwner,
    independent_mastery_eligible,
    ladder_contract_block,
    parse_assistance,
    parse_execution_owner,
)


class AssistanceVocabularyTests(unittest.TestCase):
    def test_documented_ladder_labels_parse(self):
        for level in Assistance:
            self.assertIs(parse_assistance(level.value), level)

    def test_legacy_tokens_still_parse(self):
        self.assertTrue(parse_assistance("none").is_independent)
        self.assertTrue(parse_assistance("independent").is_independent)
        self.assertTrue(parse_assistance("A0 INDEPENDENT_FIRST").is_independent)
        self.assertIs(parse_assistance("hint"), Assistance.A1_MICRO_HINT)
        self.assertIs(parse_assistance("partial"), Assistance.A3_PARTIAL_WORKED)
        self.assertIs(parse_assistance("full"), Assistance.A4_DIRECT_SOLVE)

    def test_unknown_assistance_fails_closed(self):
        with self.assertRaises(ValueError):
            parse_assistance("banana")

    def test_only_a0_is_independent(self):
        independent = [a for a in Assistance if a.is_independent]
        self.assertEqual(independent, [Assistance.A0_INDEPENDENT])

    def test_enum_order_is_append_only(self):
        """Ordinals are contract data; reordering silently rewrites history."""
        self.assertEqual(
            [level.value for level in Assistance],
            [
                "A0_INDEPENDENT",
                "A1_MICRO_HINT",
                "A2_SCAFFOLD",
                "A3_PARTIAL_WORKED",
                "A4_DIRECT_SOLVE",
            ],
        )


class ExecutionOwnerTests(unittest.TestCase):
    """Assistance intensity and execution ownership are different axes."""

    def test_canonical_values_and_aliases_parse(self):
        for owner in ExecutionOwner:
            self.assertIs(parse_execution_owner(owner.value), owner)
            self.assertIs(parse_execution_owner(owner), owner)
        for alias in ("user", "self"):
            self.assertIs(parse_execution_owner(alias), ExecutionOwner.USER)
        for alias in ("shared", "pair"):
            self.assertIs(parse_execution_owner(alias), ExecutionOwner.SHARED)
        for alias in ("tool", "model", "agent", "ai"):
            self.assertIs(parse_execution_owner(alias), ExecutionOwner.TOOL)

    def test_unknown_owner_fails_closed(self):
        for value in ("banana", "", None):
            with self.assertRaises(ValueError, msg=value):
                parse_execution_owner(value)

    def test_only_user_ownership_supports_a_claim(self):
        self.assertEqual(
            [o for o in ExecutionOwner if o.is_user_owned], [ExecutionOwner.USER]
        )

    def test_mastery_eligibility_needs_all_three_conditions(self):
        self.assertTrue(
            independent_mastery_eligible(verified=True, assistance="A0_INDEPENDENT")
        )
        self.assertTrue(
            independent_mastery_eligible(
                verified=True, assistance="none", execution_owner="USER"
            )
        )
        self.assertFalse(
            independent_mastery_eligible(verified=False, assistance="A0_INDEPENDENT")
        )
        self.assertFalse(
            independent_mastery_eligible(verified=True, assistance="A1_MICRO_HINT")
        )
        for owner in ("TOOL", "SHARED", "agent", "pair"):
            self.assertFalse(
                independent_mastery_eligible(
                    verified=True, assistance="A0_INDEPENDENT", execution_owner=owner
                ),
                owner,
            )


class ContractDriftTests(unittest.TestCase):
    """The documented contract and the runtime cannot drift apart silently."""

    SKILL = ROOT / "skills" / "foil" / "SKILL.md"

    def test_skill_file_exists(self):
        self.assertTrue(self.SKILL.is_file(), f"missing contract file: {self.SKILL}")

    # MEASURED 2026-08-23: the generated block is now pasted verbatim into
    # skills/foil/SKILL.md section 7, so this is a live gate rather than an
    # expected failure. It fails if the file and the runtime enums drift.
    def test_skill_file_embeds_the_generated_ladder_block(self):
        text = self.SKILL.read_text(encoding="utf-8")
        self.assertIn(ladder_contract_block(), text,
                      "skills/foil/SKILL.md does not contain the generated assistance ladder; "
                      "regenerate it with `python tools/foil_assistance.py`")

    def test_no_orphan_rung_labels_remain_in_the_skill_text(self):
        text = self.SKILL.read_text(encoding="utf-8")
        known = {level.value for level in Assistance}
        for match in set(re.findall(r"`(A[0-4][A-Z_ ]*)`", text)):
            self.assertIn(match.strip().replace(" ", "_"), known,
                          f"SKILL.md references an assistance label the runtime does not accept: {match}")

    def test_generated_block_covers_both_axes(self):
        block = ladder_contract_block()
        for level in Assistance:
            self.assertIn(f"`{level.value}`", block)
        for owner in ExecutionOwner:
            self.assertIn(f"`{owner.value}`", block)
        self.assertEqual(
            block.count("<!-- generated from tools/foil_assistance.py: do not edit by hand -->"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
