"""Closed host proofs for a narrow class of decidability questions.

This module does not translate arbitrary prose into logic.  It recognizes a
small, versioned theorem schema whose premises are explicit in the question:
minimum program length in an effectively enumerable *total* language.  When
the schema does not match exactly, it declines.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Mapping

from egrt_types import digest


PROOF_SCHEMA = "foil.formal-decidability-proof.v1"
THEOREM = "TOTAL_LANGUAGE_MINIMUM_PROGRAM_SEARCH"

_ASKS_DECIDABILITY = re.compile(r"\b(?:computable|decidable)\b", re.IGNORECASE)
_MINIMUM_PROGRAM = re.compile(
    r"\b(?:length\s+of\s+the\s+shortest|shortest|minimum(?:-length|\s+length)?)\b"
    r"[\s\S]{0,100}\b(?:program|description)\b|"
    r"\b(?:program|description)\b[\s\S]{0,100}"
    r"\b(?:shortest|minimum(?:-length|\s+length)?)\b",
    re.IGNORECASE,
)
_OUTPUT_TARGET = re.compile(r"\b(?:outputs?|returns?|computes?|produces?)\b", re.IGNORECASE)
_SELF_OUTPUT_DEFINITION = re.compile(
    r"\b(?P<function>[A-Za-z][A-Za-z0-9_]*)\s*\(\s*(?P<argument>[A-Za-z][A-Za-z0-9_]*)\s*\)"
    r"[\s\S]{0,180}\b(?:outputs?|returns?|produces?)\s+(?P=argument)\b",
    re.IGNORECASE,
)
_PROGRAM_LANGUAGE = re.compile(r"\b(?:programming\s+language|programs?)\b", re.IGNORECASE)
_TOTALITY = re.compile(
    r"\b(?:primitive\s+recursive\s+programming\s+language|total\s+programming\s+language|"
    r"strongly\s+normaliz(?:ing|ed)|every\s+(?:valid\s+)?program\s+(?:halts|terminates)|"
    r"all\s+(?:valid\s+)?programs\s+(?:halt|terminate))\b",
    re.IGNORECASE,
)
_NEGATIVE_TOTALITY = re.compile(
    r"\b(?:turing[- ]complete|partial\s+recursive|may\s+not\s+(?:halt|terminate)|"
    r"not\s+(?:all|every)[^.]{0,40}(?:halt|terminate)|halting\s+problem)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FormalDecidabilityProof:
    theorem: str
    question_digest: str
    conclusion: str
    premise_codes: tuple[str, ...]
    algorithm_steps: tuple[str, ...]
    schema: str = PROOF_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != PROOF_SCHEMA or self.theorem != THEOREM:
            raise ValueError("unsupported formal-decidability proof")
        if self.conclusion != "Yes":
            raise ValueError("the total-language theorem concludes Yes")
        if not isinstance(self.premise_codes, tuple) or self.premise_codes != (
            "EFFECTIVE_PROGRAM_ENUMERATION_BY_LENGTH",
            "TOTAL_PROGRAM_EXECUTION",
            "OUTPUT_TARGET_IS_REPRESENTABLE",
        ):
            raise ValueError("formal-decidability premises are incomplete")
        if self.algorithm_steps != (
            "ENUMERATE_PROGRAMS_BY_NONDECREASING_LENGTH",
            "EXECUTE_EACH_FINITE_LENGTH_COHORT_TO_COMPLETION",
            "RETURN_FIRST_LENGTH_WITH_TARGET_OUTPUT",
        ):
            raise ValueError("formal-decidability algorithm is not canonical")
        if not re.fullmatch(r"[0-9a-f]{64}", self.question_digest):
            raise ValueError("question_digest must be lowercase SHA-256")

    def body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "theorem": self.theorem,
            "question_digest": self.question_digest,
            "conclusion": self.conclusion,
            "premise_codes": list(self.premise_codes),
            "algorithm_steps": list(self.algorithm_steps),
        }

    @property
    def payload(self) -> str:
        return json.dumps(self.body(), sort_keys=True, separators=(",", ":"))


def derive_formal_decidability_proof(question: str) -> FormalDecidabilityProof | None:
    """Return the canonical proof only for the closed total-language schema."""

    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be non-empty text")
    if _NEGATIVE_TOTALITY.search(question):
        return None
    required = (
        _ASKS_DECIDABILITY.search(question),
        _MINIMUM_PROGRAM.search(question),
        _OUTPUT_TARGET.search(question),
        _SELF_OUTPUT_DEFINITION.search(question),
        _PROGRAM_LANGUAGE.search(question),
        _TOTALITY.search(question),
    )
    if not all(required):
        return None
    return FormalDecidabilityProof(
        THEOREM,
        digest(question),
        "Yes",
        (
            "EFFECTIVE_PROGRAM_ENUMERATION_BY_LENGTH",
            "TOTAL_PROGRAM_EXECUTION",
            "OUTPUT_TARGET_IS_REPRESENTABLE",
        ),
        (
            "ENUMERATE_PROGRAMS_BY_NONDECREASING_LENGTH",
            "EXECUTE_EACH_FINITE_LENGTH_COHORT_TO_COMPLETION",
            "RETURN_FIRST_LENGTH_WITH_TARGET_OUTPUT",
        ),
    )


def validate_formal_decidability_payload(
    question: str,
    candidate_answer: str,
    payload: str,
) -> FormalDecidabilityProof:
    """Re-derive and byte-compare the proof; unknown fields fail closed."""

    if candidate_answer.strip().casefold() != "yes":
        raise ValueError("formal-decidability candidate must be Yes")
    try:
        raw = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("formal-decidability payload must be canonical JSON") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("formal-decidability payload must be an object")
    expected_fields = {
        "schema", "theorem", "question_digest", "conclusion",
        "premise_codes", "algorithm_steps",
    }
    if set(raw) != expected_fields:
        raise ValueError("closed formal-decidability payload schema mismatch")
    derived = derive_formal_decidability_proof(question)
    if derived is None or raw != derived.body() or payload != derived.payload:
        raise ValueError("formal-decidability proof does not bind the question")
    return derived
