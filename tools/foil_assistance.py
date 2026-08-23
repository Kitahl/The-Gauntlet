"""FOIL assistance ladder — one vocabulary for the contract and the runtime.

The prior release defined the ladder as `A0 INDEPENDENT_FIRST ... A4 DIRECT_SOLVE`
in `skills/foil/SKILL.md`, while `foil_interventions.intervention_status()`
recognised independence only from the string set `{"none", "independent"}`.  The
intersection was empty, so a caller who followed the documented contract had
every ownership and transfer record silently discarded.

This module is the single source of truth.  `SKILL.md` is generated from - or at
minimum tested against - `ladder_contract_block()`, so the two cannot drift
again without a test failure.

Parsing is deliberately permissive on *legacy* input and strict on everything
else: unknown assistance strings raise instead of being treated as assisted.
Failing closed on an unknown label is the conservative choice, because the
alternative silently downgrades real independent evidence.
"""
from __future__ import annotations

from enum import Enum

SCHEMA = "egrt.foil-assistance.v1"

__all__ = [
    "SCHEMA",
    "Assistance",
    "ExecutionOwner",
    "LEGACY_ALIASES",
    "EXECUTION_OWNER_ALIASES",
    "independent_mastery_eligible",
    "ladder_contract_block",
    "parse_assistance",
    "parse_execution_owner",
]


class Assistance(str, Enum):
    """Assistance intensity actually supplied for one attempt."""

    A0_INDEPENDENT = "A0_INDEPENDENT"
    A1_MICRO_HINT = "A1_MICRO_HINT"
    A2_SCAFFOLD = "A2_SCAFFOLD"
    A3_PARTIAL_WORKED = "A3_PARTIAL_WORKED"
    A4_DIRECT_SOLVE = "A4_DIRECT_SOLVE"

    @property
    def rung(self) -> int:
        return int(self.value[1])

    @property
    def is_independent(self) -> bool:
        """Only A0 can support an ownership, transfer, or defence claim."""
        return self is Assistance.A0_INDEPENDENT

    @property
    def label(self) -> str:
        return self.value[3:].replace("_", " ").lower()


class ExecutionOwner(str, Enum):
    """Who actually performed the attempt.

    Assistance intensity and execution ownership are different axes.  A0 says
    nobody handed over a hint; it does not say the *person* did the work.  A tool
    or agent that produced the artifact end to end can be A0 on the assistance
    ladder and still supply no evidence about the person, which is exactly how
    tool output was previously able to accumulate as user competence.
    """

    USER = "USER"
    SHARED = "SHARED"
    TOOL = "TOOL"

    @property
    def is_user_owned(self) -> bool:
        """Only USER-owned execution can support a competence claim."""
        return self is ExecutionOwner.USER


#: Accepted spellings for execution ownership.  As with assistance, an unknown
#: string is an error rather than an implicit default, because defaulting either
#: way silently mislabels evidence.
EXECUTION_OWNER_ALIASES: dict[str, ExecutionOwner] = {
    "user": ExecutionOwner.USER,
    "self": ExecutionOwner.USER,
    "shared": ExecutionOwner.SHARED,
    "pair": ExecutionOwner.SHARED,
    "tool": ExecutionOwner.TOOL,
    "model": ExecutionOwner.TOOL,
    "agent": ExecutionOwner.TOOL,
    "ai": ExecutionOwner.TOOL,
}


#: Historic strings that must keep working.  Everything here maps to a rung; a
#: string that is not here and not an `Assistance` value is an error, not an
#: implicit "assisted".
LEGACY_ALIASES: dict[str, Assistance] = {
    "none": Assistance.A0_INDEPENDENT,
    "independent": Assistance.A0_INDEPENDENT,
    "independent_first": Assistance.A0_INDEPENDENT,
    "a0": Assistance.A0_INDEPENDENT,
    "hint": Assistance.A1_MICRO_HINT,
    "micro_hint": Assistance.A1_MICRO_HINT,
    "a1": Assistance.A1_MICRO_HINT,
    "scaffold": Assistance.A2_SCAFFOLD,
    "a2": Assistance.A2_SCAFFOLD,
    "partial": Assistance.A3_PARTIAL_WORKED,
    "partial_worked": Assistance.A3_PARTIAL_WORKED,
    "a3": Assistance.A3_PARTIAL_WORKED,
    "solve": Assistance.A4_DIRECT_SOLVE,
    "direct_solve": Assistance.A4_DIRECT_SOLVE,
    "full": Assistance.A4_DIRECT_SOLVE,
    "a4": Assistance.A4_DIRECT_SOLVE,
}


def parse_assistance(value: str | Assistance) -> Assistance:
    """Accept an enum, a canonical value, or a documented legacy alias."""
    if isinstance(value, Assistance):
        return value
    if value is None:
        raise ValueError("assistance is required; there is no safe default")
    raw = str(value).strip()
    for candidate in (raw, raw.upper()):
        try:
            return Assistance(candidate)
        except ValueError:
            pass
    key = raw.lower().replace("-", "_").replace(" ", "_")
    # tolerate "A0 INDEPENDENT_FIRST" style prose from the old SKILL.md text
    head = key.split("_", 1)[0]
    if key in LEGACY_ALIASES:
        return LEGACY_ALIASES[key]
    if head in LEGACY_ALIASES:
        return LEGACY_ALIASES[head]
    raise ValueError(
        f"unknown assistance level: {value!r}. "
        f"Use one of {[a.value for a in Assistance]} or a documented alias."
    )


def parse_execution_owner(value: str | ExecutionOwner | None) -> ExecutionOwner:
    """Accept an enum, a canonical value, or a documented alias. Fails closed."""
    if isinstance(value, ExecutionOwner):
        return value
    if value is None:
        raise ValueError("execution owner is required; there is no safe default")
    raw = str(value).strip()
    for candidate in (raw, raw.upper()):
        try:
            return ExecutionOwner(candidate)
        except ValueError:
            pass
    key = raw.lower().replace("-", "_").replace(" ", "_")
    if key in EXECUTION_OWNER_ALIASES:
        return EXECUTION_OWNER_ALIASES[key]
    raise ValueError(
        f"unknown execution owner: {value!r}. "
        f"Use one of {[o.value for o in ExecutionOwner]} or a documented alias."
    )


def independent_mastery_eligible(
    *,
    verified: bool,
    assistance: str | Assistance,
    execution_owner: str | ExecutionOwner = ExecutionOwner.USER,
) -> bool:
    """The single admissibility predicate for an independent-mastery claim.

    All three conditions are necessary: the outcome was checked by a verifier,
    reached without material assistance, and executed by the person.
    """
    return (
        bool(verified)
        and parse_assistance(assistance).is_independent
        and parse_execution_owner(execution_owner) is ExecutionOwner.USER
    )


def ladder_contract_block() -> str:
    """The exact Markdown block `skills/foil/SKILL.md` must contain.

    `tests/test_foil_assistance.py::ContractDriftTests` asserts the file contains
    this verbatim, so the documented vocabulary and the runtime cannot drift.
    """
    marker = "<!-- generated from tools/foil_assistance.py: do not edit by hand -->"
    lines = [marker]
    for level in Assistance:
        suffix = (
            " (the only rung that can support ownership or transfer)"
            if level.is_independent
            else ""
        )
        lines.append(f"- `{level.value}` — {level.label}{suffix}")
    lines.append("")
    lines.append(marker)
    lines.append(
        "Execution owner — who performed the attempt, a separate axis from assistance:"
    )
    for owner in ExecutionOwner:
        suffix = (
            " (the only owner that can support a competence claim)"
            if owner.is_user_owned
            else ""
        )
        lines.append(f"- `{owner.value}`{suffix}")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    print(ladder_contract_block())
