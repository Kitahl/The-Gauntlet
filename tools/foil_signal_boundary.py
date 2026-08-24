"""Typed boundary between FOIL control signals and admissible evidence.

Routing scores, verifier-selection hints, predicted complement usefulness, and
branch preferences are useful for deciding what to do next.  They are not
factual warrant and cannot establish user competence.  This module makes that
boundary executable without introducing a second evidence estimator.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

import foil_evidence

SCHEMA = "egrt.foil-signal-authority.v1"


class SignalAuthority(str, Enum):
    """The maximum authority an internal signal may carry."""

    CONTROL_ONLY = "CONTROL_ONLY"
    EVIDENCE_CANDIDATE = "EVIDENCE_CANDIDATE"


class EvidenceAdmissionError(ValueError):
    """Raised when a control signal is presented as admitted evidence."""


@dataclass(frozen=True)
class RoutedSignal:
    """Receipt-safe internal signal; never stores the underlying raw content."""

    kind: str
    authority: SignalAuthority = SignalAuthority.CONTROL_ONLY
    score: float | None = None
    source_sha256: str | None = None

    def __post_init__(self) -> None:
        kind = str(self.kind).strip()
        if not kind:
            raise ValueError("signal kind is required")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "authority", SignalAuthority(self.authority))
        if self.score is not None:
            if (
                isinstance(self.score, bool)
                or not isinstance(self.score, (int, float))
                or not math.isfinite(float(self.score))
                or not 0.0 <= float(self.score) <= 1.0
            ):
                raise ValueError("signal score must be a finite number in [0, 1]")
        if (
            self.source_sha256 is not None
            and re.fullmatch(r"[0-9a-f]{64}", self.source_sha256) is None
        ):
            raise ValueError("source_sha256 must be a lowercase SHA-256 digest")

    def trace(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "kind": self.kind,
            "authority": self.authority.value,
            "score": self.score,
            "source_sha256": self.source_sha256,
            "raw_signal_stored": False,
        }


def may_satisfy_factual_obligation(
    signal: RoutedSignal, *, ordinary_admission_passed: bool = False
) -> bool:
    """Whether an independently admitted candidate may enter existing evidence flow."""

    return (
        signal.authority is SignalAuthority.EVIDENCE_CANDIDATE and ordinary_admission_passed is True
    )


def admit_competence_observation(
    signal: RoutedSignal,
    observation: foil_evidence.Observation,
    *,
    ordinary_admission_passed: bool = False,
) -> foil_evidence.Observation:
    """Pass an evidence candidate to the existing estimator after admission.

    The returned observation is unchanged.  Its tier, verifier, recency, and
    weight are still governed solely by :mod:`foil_evidence`; this function adds
    no thresholds and cannot turn weak evidence into load-bearing evidence.
    """

    if signal.authority is SignalAuthority.CONTROL_ONLY:
        raise EvidenceAdmissionError(
            "CONTROL_ONLY signals cannot promote competence or become evidence"
        )
    if ordinary_admission_passed is not True:
        raise EvidenceAdmissionError(
            "EVIDENCE_CANDIDATE still requires ordinary evidence admission"
        )
    if not isinstance(observation, foil_evidence.Observation):
        raise TypeError("observation must be foil_evidence.Observation")
    return observation
