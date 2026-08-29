from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from foil_typed_formula import (  # noqa: E402
    FormulaStatus,
    compare_formula,
    discover_formula_task,
    extract_target_formulas,
    unique_reference_formula,
)


REFERENCE = r"C = (V_m C_m + V_f C_f A)(V_m I + V_f <A>)^{-1}"


class TypedFormulaTests(unittest.TestCase):
    def test_real_missing_average_is_different(self) -> None:
        candidate = r"\(C=(V_fC_fA+V_mC_m)(V_fA+V_mI)^{-1}\)"
        result = compare_formula(candidate, (REFERENCE,), "C")
        self.assertEqual(result.status, FormulaStatus.DIFFERENT)

    def test_equivalent_notation_and_addition_order_pass(self) -> None:
        candidate = r"C=(V_f*C_f*A+V_m*C_m)*(V_f*<A>+V_m*I)^(-1)"
        result = compare_formula(candidate, (REFERENCE,), "C")
        self.assertEqual(result.status, FormulaStatus.EQUIVALENT)

    def test_multiplication_order_and_inverse_scope_are_preserved(self) -> None:
        self.assertEqual(
            compare_formula("C=B*A", ("C=A*B",), "C").status,
            FormulaStatus.DIFFERENT,
        )
        self.assertEqual(
            compare_formula("C=A+B^(-1)", ("C=(A+B)^(-1)",), "C").status,
            FormulaStatus.DIFFERENT,
        )

    def test_conflicting_sources_are_ambiguous(self) -> None:
        result = compare_formula("C=A", ("C=A", "C=B"), "C")
        self.assertEqual(result.status, FormulaStatus.AMBIGUOUS)
        self.assertIsNone(unique_reference_formula(("C=A", "C=B"), "C"))

    def test_named_formula_discovery_is_narrow(self) -> None:
        task = discover_formula_task("What is the expression of C given these tensors?")
        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task.target, "C")
        self.assertIsNone(discover_formula_task("Where was tensor C first published?"))

    def test_source_notation_is_preserved_for_output(self) -> None:
        formula = extract_target_formulas("The result is " + REFERENCE + ".", "C")[0]
        self.assertIn("<A>", formula.raw)
        self.assertNotIn("AVG", formula.raw)


if __name__ == "__main__":
    unittest.main()
