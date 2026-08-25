"""Compatibility import for the production certified-arithmetic parser."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from foil_certified_arithmetic import (  # noqa: E402,F401
    ASSERTIVE_LANGUAGE,
    AUDIT_LANGUAGE,
    CERTIFIED_LANGUAGE,
    CERTIFIED_V1_LANGUAGE,
    DIVISION_SAFE_LANGUAGE,
    MAX_ABS_NUMERATOR,
    MAX_AST_NODES,
    MAX_DENOMINATOR,
    MAX_MATH_SPAN_CHARS,
    MAX_POWER,
    MAX_RAW_LINES,
    POWER_LANGUAGE,
    RAW_NUMERIC_LANGUAGE,
    EqualityFinding,
    MathSpan,
    UnsupportedExpression,
    check,
    evaluate_exact,
    extract_step,
    extract_steps,
    normalize_expression,
)
