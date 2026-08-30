"""Pure bridge from a committable shadow candidate to an explicit host request."""

from __future__ import annotations

from dataclasses import dataclass

from foil_authority import AdmissionState
from foil_authority_replay import AuthorityReplayGuard
from foil_candidate_state import (
    AuthorityIssuer,
    CandidateBinding,
    CandidateDecision,
    CandidateState,
)
from foil_shadow_repair import ShadowRepairAdmission


def _require_digest(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_locator(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("artifact_locator must be non-empty text")
    return value


@dataclass(frozen=True)
class HostActionRequest:
    """Digests and a locator only; the host remains the sole action owner."""

    candidate_id: str
    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str
    artifact_locator: str
    artifact_sha256: str
    proposal_digest: str
    structural_certificate_digest: str
    semantic_certificate_digest: str
    requires_explicit_host_action: bool = True
    execution_authorized: bool = False
    base_answer_preserved: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise ValueError("candidate_id must be non-empty text")
        for name in (
            "base_digest",
            "candidate_digest",
            "scope_digest",
            "obligation_set_digest",
            "artifact_sha256",
            "proposal_digest",
            "structural_certificate_digest",
            "semantic_certificate_digest",
        ):
            _require_digest(name, getattr(self, name))
        _require_locator(self.artifact_locator)
        if self.requires_explicit_host_action is not True or self.execution_authorized is not False:
            raise ValueError("host request requires explicit host action and grants no execution")
        if self.base_answer_preserved is not True:
            raise ValueError("host request must preserve A0")


def create_host_action_request(
    admission: ShadowRepairAdmission,
    *,
    decision: CandidateDecision,
    binding: CandidateBinding,
    issuer: AuthorityIssuer,
    now: str,
    replay_guard: AuthorityReplayGuard,
) -> HostActionRequest:
    """Package an admitted candidate only after consuming current ACTIVE authority.

    The resulting request remains non-executable and must be acted on by the
    host explicitly. Consuming the authority token makes this bridge a one-shot
    boundary rather than a path from repair admission to a host action.
    """

    if not isinstance(admission, ShadowRepairAdmission):
        raise TypeError("admission must be ShadowRepairAdmission")
    if not isinstance(decision, CandidateDecision):
        raise TypeError("decision must be CandidateDecision")
    if not isinstance(binding, CandidateBinding):
        raise TypeError("binding must be CandidateBinding")
    if not isinstance(issuer, AuthorityIssuer):
        raise TypeError("issuer must be AuthorityIssuer")
    if not isinstance(replay_guard, AuthorityReplayGuard):
        raise TypeError("replay_guard must be AuthorityReplayGuard")
    if not isinstance(now, str) or not now.strip():
        raise ValueError("now must be non-empty ISO-8601 text")
    if admission.decision.state is not AdmissionState.COMMITTABLE:
        raise ValueError("host request requires a COMMITTABLE admission")
    if (
        admission.structural_certificate_digest is None
        or admission.semantic_certificate_digest is None
    ):
        raise ValueError("host request requires both certificate digests")
    candidate = admission.proposal.candidate
    if (
        binding.candidate_id != candidate.candidate_id
        or binding.base_answer_digest != candidate.base_digest
    ):
        raise ValueError("candidate binding must match the repair candidate and A0")
    if decision.state is not CandidateState.ACTIVE or decision.token is None:
        raise ValueError("host request requires an ACTIVE candidate decision token")
    if not replay_guard.consume(
        decision.token,
        issuer,
        binding,
        now=now,
        expected_state=CandidateState.ACTIVE,
    ):
        raise ValueError("host request requires a current, matching, unused ACTIVE token")
    artifact = admission.proposal.artifact
    return HostActionRequest(
        candidate_id=candidate.candidate_id,
        base_digest=candidate.base_digest,
        candidate_digest=candidate.candidate_digest,
        scope_digest=candidate.scope_digest,
        obligation_set_digest=candidate.obligation_set_digest,
        artifact_locator=artifact.locator,
        artifact_sha256=artifact.sha256 or "",
        proposal_digest=admission.proposal.proposal_digest,
        structural_certificate_digest=admission.structural_certificate_digest,
        semantic_certificate_digest=admission.semantic_certificate_digest,
    )
