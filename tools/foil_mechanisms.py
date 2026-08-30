"""Dormant, independently ablatable FOIL P1 mechanism controllers.

The controllers in this module only choose receipt-safe *plans*.  They never
call a model, a tool, or a network client.  A host may execute an emitted plan
through its own adapter and feed the resulting digests back on a later turn.
Nothing returned here is evidence or a factual conclusion.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol, Sequence

from foil_policy import ClaimKind, TaskContext, VerifierKind
from foil_signal_boundary import SignalAuthority

_SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _require_digest(name: str, value: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _uncertainty_digest(label: str, kind: ClaimKind) -> str:
    """Create an internal correlation digest without placing a label in a trace."""

    return _digest(f"foil-p1-uncertainty-v1:{kind.value}:{label}")


class VerifierStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class MechanismFlags:
    """All P1 mechanisms are off unless a host explicitly enables each one."""

    claim_native_verifier: bool = False
    targeted_acquisition: bool = False
    challenger_search: bool = False
    critic_repair: bool = False

    def trace(self) -> dict[str, bool]:
        return {
            "claim_native_verifier": self.claim_native_verifier,
            "targeted_acquisition": self.targeted_acquisition,
            "challenger_search": self.challenger_search,
            "critic_repair": self.critic_repair,
        }


@dataclass(frozen=True)
class VerifierResult:
    """A host-supplied verifier outcome, never an automatically admitted fact."""

    verifier: VerifierKind
    status: VerifierStatus
    provenance_sha256: tuple[str, ...] = ()
    failure_scope_sha256: str | None = None
    authority: SignalAuthority = SignalAuthority.CONTROL_ONLY

    def __post_init__(self) -> None:
        object.__setattr__(self, "verifier", VerifierKind(self.verifier))
        object.__setattr__(self, "status", VerifierStatus(self.status))
        object.__setattr__(self, "authority", SignalAuthority(self.authority))
        if self.authority is not SignalAuthority.CONTROL_ONLY:
            raise ValueError("P1 verifier results are CONTROL_ONLY routing signals")
        for digest in self.provenance_sha256:
            _require_digest("provenance_sha256", digest)
        if self.failure_scope_sha256 is not None:
            _require_digest("failure_scope_sha256", self.failure_scope_sha256)

    @property
    def blocks_competence_update(self) -> bool:
        """A non-pass cannot update competence; a pass still needs normal admission."""

        return self.status is not VerifierStatus.PASS

    def trace(self) -> dict[str, object]:
        return {
            "verifier": self.verifier.value,
            "status": self.status.value,
            "authority": self.authority.value,
            "provenance_sha256": self.provenance_sha256,
            "failure_scope_sha256": self.failure_scope_sha256,
            "blocks_competence_update": self.blocks_competence_update,
            "automatic_evidence_admission": False,
        }


@dataclass(frozen=True)
class AcquisitionProposal:
    """Digest-only host proposal; execution remains the host's responsibility."""

    action_sha256: str
    target_uncertainty_sha256: str

    def __post_init__(self) -> None:
        _require_digest("action_sha256", self.action_sha256)
        _require_digest("target_uncertainty_sha256", self.target_uncertainty_sha256)


@dataclass(frozen=True)
class AcquisitionObservation:
    """A digest of host-observed material with no evidentiary authority here."""

    observation_sha256: str
    target_uncertainty_sha256: str

    def __post_init__(self) -> None:
        _require_digest("observation_sha256", self.observation_sha256)
        _require_digest("target_uncertainty_sha256", self.target_uncertainty_sha256)


@dataclass(frozen=True)
class ChallengerCandidate:
    """A digest-only alternate candidate returned by a host search branch."""

    candidate_sha256: str
    branch_sha256: str
    agreement_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_digest("candidate_sha256", self.candidate_sha256)
        _require_digest("branch_sha256", self.branch_sha256)
        if self.agreement_sha256 is not None:
            _require_digest("agreement_sha256", self.agreement_sha256)


class HostExecutorAdapter(Protocol):
    """Documentation-only adapter boundary.  Controllers deliberately never call it."""

    def acquire(self, proposal: AcquisitionProposal) -> AcquisitionObservation: ...

    def challenge(self, branch_sha256: str) -> ChallengerCandidate: ...


_CLAIM_NATIVE_VERIFIER: Mapping[ClaimKind, VerifierKind] = {
    ClaimKind.EXTERNAL_FACT: VerifierKind.SOURCE_EVIDENCE,
    ClaimKind.FRESH_FACT: VerifierKind.CURRENT_SOURCE,
    ClaimKind.NUMERIC: VerifierKind.EXACT_CALCULATION,
    ClaimKind.SUPPLIED_EXAMPLES: VerifierKind.SUPPLIED_EXAMPLE_CONSISTENCY,
    ClaimKind.EXECUTABLE: VerifierKind.EXECUTION_TEST,
    ClaimKind.LOGICAL: VerifierKind.CONTRADICTION_COUNTEREXAMPLE,
    ClaimKind.OUTPUT_CONTRACT: VerifierKind.OUTPUT_CONTRACT,
}


def _costs(*, routing: int = 0, branches: int = 0, revisions: int = 0) -> dict[str, int | None]:
    """RunCostReceipt-compatible units; unknown token counts stay ``None``."""

    return {
        "profile_lookup_count": 0,
        "routing_decision_count": routing,
        "model_calls": 0,
        "tool_calls": 0,
        "verification_calls": 0,
        "retry_count": 0,
        "branch_count": branches,
        "revision_count": revisions,
        "tokens_in": None,
        "tokens_out": None,
        "wall_time_ms": None,
    }


@dataclass(frozen=True)
class VerifierSelectionReceipt:
    enabled: bool
    selected: tuple[VerifierKind, ...]
    uncertainty_sha256: tuple[str, ...]
    stop_reason: str

    def trace(self) -> dict[str, object]:
        return {
            "mechanism": "claim_native_verifier",
            "enabled": self.enabled,
            "authority": SignalAuthority.CONTROL_ONLY.value,
            "selected_verifiers": tuple(item.value for item in self.selected),
            "uncertainty_sha256": self.uncertainty_sha256,
            "stop_reason": self.stop_reason,
            "automatic_factual_closure": False,
            "costs": _costs(routing=int(self.enabled)),
        }


@dataclass(frozen=True)
class AcquisitionReceipt:
    enabled: bool
    selected_action_sha256: tuple[str, ...]
    pending_uncertainty_sha256: tuple[str, ...]
    observations_seen: int
    stop_reason: str

    def trace(self) -> dict[str, object]:
        return {
            "mechanism": "targeted_acquisition",
            "enabled": self.enabled,
            "authority": SignalAuthority.CONTROL_ONLY.value,
            "selected_action_sha256": self.selected_action_sha256,
            "pending_uncertainty_sha256": self.pending_uncertainty_sha256,
            "observations_seen": self.observations_seen,
            "stop_reason": self.stop_reason,
            "observations_are_evidence": False,
            "automatic_factual_closure": False,
            "costs": _costs(routing=int(self.enabled)),
        }


@dataclass(frozen=True)
class ChallengerReceipt:
    enabled: bool
    selected_candidate_sha256: tuple[str, ...]
    selected_branch_sha256: tuple[str, ...]
    agreement_sha256: tuple[str, ...]
    stop_reason: str

    def trace(self) -> dict[str, object]:
        return {
            "mechanism": "challenger_search",
            "enabled": self.enabled,
            "authority": SignalAuthority.CONTROL_ONLY.value,
            "selected_candidate_sha256": self.selected_candidate_sha256,
            "selected_branch_sha256": self.selected_branch_sha256,
            "agreement_sha256": self.agreement_sha256,
            "stop_reason": self.stop_reason,
            "branch_agreement_is_evidence": False,
            "automatic_factual_closure": False,
            "costs": _costs(routing=int(self.enabled), branches=len(self.selected_branch_sha256)),
        }


@dataclass(frozen=True)
class RepairReceipt:
    enabled: bool
    candidate_sha256: str | None
    scope_sha256: str | None
    recheck_verifier: VerifierKind | None
    revision_count: int
    requires_recheck: bool
    stop_reason: str

    def trace(self) -> dict[str, object]:
        return {
            "mechanism": "critic_repair",
            "enabled": self.enabled,
            "authority": SignalAuthority.CONTROL_ONLY.value,
            "candidate_sha256": self.candidate_sha256,
            "scope_sha256": self.scope_sha256,
            "recheck_verifier": (
                self.recheck_verifier.value if self.recheck_verifier is not None else None
            ),
            "revision_count": self.revision_count,
            "requires_recheck": self.requires_recheck,
            "stop_reason": self.stop_reason,
            "automatic_factual_closure": False,
            "costs": _costs(routing=int(self.enabled), revisions=self.revision_count),
        }


class FoilP1Mechanisms:
    """Pure P1 mechanism planner with per-mechanism feature gates and ablation trace."""

    def __init__(self, flags: MechanismFlags = MechanismFlags()) -> None:
        self.flags = flags

    def ablation_trace(self) -> dict[str, object]:
        enabled = self.flags.trace()
        return {
            "mechanism_flags": enabled,
            "enabled_mechanisms": tuple(name for name, active in enabled.items() if active),
            "ablated_mechanisms": tuple(name for name, active in enabled.items() if not active),
            "authority": SignalAuthority.CONTROL_ONLY.value,
        }

    def select_claim_native_verifiers(self, task: TaskContext) -> VerifierSelectionReceipt:
        pending = tuple(item for item in task.uncertainties if item.decisive and not item.resolved)
        uncertainty_sha256 = tuple(
            _uncertainty_digest(item.label, item.claim_kind) for item in pending
        )
        if not self.flags.claim_native_verifier:
            return VerifierSelectionReceipt(False, (), uncertainty_sha256, "feature_disabled")
        selected = tuple(
            sorted(
                {_CLAIM_NATIVE_VERIFIER[item.claim_kind] for item in pending}, key=lambda x: x.value
            )
        )
        return VerifierSelectionReceipt(
            True,
            selected,
            uncertainty_sha256,
            "no_pending_uncertainties" if not pending else "selected",
        )

    def plan_targeted_acquisition(
        self,
        task: TaskContext,
        proposals: Sequence[AcquisitionProposal],
        *,
        observations: Sequence[AcquisitionObservation] = (),
        used_action_sha256: frozenset[str] = frozenset(),
        max_actions: int = 2,
    ) -> AcquisitionReceipt:
        if max_actions < 1:
            raise ValueError("max_actions must be at least 1")
        for digest in used_action_sha256:
            _require_digest("used_action_sha256", digest)
        pending = tuple(
            _uncertainty_digest(item.label, item.claim_kind)
            for item in task.uncertainties
            if item.decisive and not item.resolved
        )
        if not self.flags.targeted_acquisition:
            return AcquisitionReceipt(False, (), pending, len(observations), "feature_disabled")
        if not pending:
            return AcquisitionReceipt(True, (), (), len(observations), "no_pending_uncertainties")
        selected: list[str] = []
        seen = set(used_action_sha256)
        targets = set(pending)
        for proposal in proposals:
            if len(selected) >= max_actions:
                break
            if proposal.action_sha256 in seen or proposal.target_uncertainty_sha256 not in targets:
                continue
            seen.add(proposal.action_sha256)
            selected.append(proposal.action_sha256)
        reason = "budget_exhausted" if len(selected) == max_actions else "no_new_targeted_action"
        return AcquisitionReceipt(True, tuple(selected), pending, len(observations), reason)

    def select_challengers(
        self,
        candidates: Sequence[ChallengerCandidate],
        *,
        used_candidate_sha256: frozenset[str] = frozenset(),
        used_branch_sha256: frozenset[str] = frozenset(),
        max_candidates: int = 2,
    ) -> ChallengerReceipt:
        if not 2 <= max_candidates <= 4:
            raise ValueError("max_candidates must be between 2 and 4")
        for digest in (*used_candidate_sha256, *used_branch_sha256):
            _require_digest("used candidate or branch digest", digest)
        if not self.flags.challenger_search:
            return ChallengerReceipt(False, (), (), (), "feature_disabled")
        candidate_seen = set(used_candidate_sha256)
        branch_seen = set(used_branch_sha256)
        selected: list[ChallengerCandidate] = []
        for candidate in candidates:
            if len(selected) >= max_candidates:
                break
            if (
                candidate.candidate_sha256 in candidate_seen
                or candidate.branch_sha256 in branch_seen
            ):
                continue
            candidate_seen.add(candidate.candidate_sha256)
            branch_seen.add(candidate.branch_sha256)
            selected.append(candidate)
        reason = (
            "budget_exhausted"
            if len(selected) == max_candidates
            else "insufficient_distinct_candidates"
        )
        return ChallengerReceipt(
            True,
            tuple(item.candidate_sha256 for item in selected),
            tuple(item.branch_sha256 for item in selected),
            tuple(item.agreement_sha256 for item in selected if item.agreement_sha256 is not None),
            reason,
        )

    def plan_critic_repair(
        self,
        candidate_sha256: str,
        result: VerifierResult,
        *,
        prior_revisions: int = 0,
    ) -> RepairReceipt:
        _require_digest("candidate_sha256", candidate_sha256)
        if prior_revisions < 0:
            raise ValueError("prior_revisions must be non-negative")
        if not self.flags.critic_repair:
            return RepairReceipt(False, None, None, None, 0, False, "feature_disabled")
        if result.status is not VerifierStatus.FAIL:
            return RepairReceipt(True, None, None, None, 0, False, "no_concrete_verifier_failure")
        if result.failure_scope_sha256 is None:
            return RepairReceipt(True, None, None, None, 0, False, "failure_scope_unavailable")
        if prior_revisions >= 1:
            return RepairReceipt(
                True, None, result.failure_scope_sha256, None, 0, False, "revision_budget_exhausted"
            )
        return RepairReceipt(
            True,
            candidate_sha256,
            result.failure_scope_sha256,
            result.verifier,
            1,
            True,
            "repair_then_mandatory_recheck",
        )
