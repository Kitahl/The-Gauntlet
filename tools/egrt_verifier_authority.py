"""Closed verifier authority and replayable, content-bound execution evidence.

The trust boundary is the host process and the closed deterministic registry.
Callers may carry receipts, but admission reruns the registered verifier from the
canonical input and compares the complete observed result. A syntactically valid
digest or caller-selected PASS is therefore insufficient.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import Enum
from typing import Mapping

from egrt_types import canonical_json, digest
from egrt_verifiers import DEFAULT_REGISTRY, VerifierResult


CLAIM_BOUND_SCOPE = "CLAIM_BOUND"


class VerifierRole(str, Enum):
    STRUCTURAL_VERIFIER = "STRUCTURAL_VERIFIER"
    SEMANTIC_VERIFIER = "SEMANTIC_VERIFIER"


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _sha256(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{name} must be lowercase SHA-256 hex")
    return value


@dataclass(frozen=True)
class VerifierRegistration:
    authority_id: str
    verifier_id: str
    verifier_version: str
    implementation_digest: str
    authorized_roles: tuple[VerifierRole, ...]
    authorized_scope: str
    environment_digest: str
    active: bool = True

    def __post_init__(self) -> None:
        for name in (
            "authority_id",
            "verifier_id",
            "verifier_version",
            "authorized_scope",
        ):
            _text(name, getattr(self, name))
        for name in ("implementation_digest", "environment_digest"):
            _sha256(name, getattr(self, name))
        if not isinstance(self.authorized_roles, tuple) or not self.authorized_roles:
            raise ValueError("authorized_roles must be a non-empty tuple")
        roles = tuple(VerifierRole(item) for item in self.authorized_roles)
        if len(set(roles)) != len(roles):
            raise ValueError("authorized_roles must be unique")
        object.__setattr__(self, "authorized_roles", roles)
        if not isinstance(self.active, bool):
            raise TypeError("active must be bool")

    @property
    def registration_digest(self) -> str:
        return digest(
            {
                "authority_id": self.authority_id,
                "verifier_id": self.verifier_id,
                "verifier_version": self.verifier_version,
                "implementation_digest": self.implementation_digest,
                "authorized_roles": [item.value for item in self.authorized_roles],
                "authorized_scope": self.authorized_scope,
                "environment_digest": self.environment_digest,
                "active": self.active,
            }
        )


class VerifierAuthorityRegistry:
    """Read-only authority view over the host's closed verifier registry."""

    def __init__(self) -> None:
        self._registrations = {
            verifier_id: VerifierRegistration(
                authority_id="egrt.host.builtin",
                verifier_id=verifier_id,
                verifier_version=DEFAULT_REGISTRY.resolve(verifier_id).version,
                implementation_digest=DEFAULT_REGISTRY.implementation_digest(verifier_id),
                authorized_roles=(VerifierRole.STRUCTURAL_VERIFIER,),
                authorized_scope=CLAIM_BOUND_SCOPE,
                environment_digest=DEFAULT_REGISTRY.environment_digest,
            )
            for verifier_id in DEFAULT_REGISTRY.names()
        }

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._registrations))

    def resolve(self, verifier_id: str) -> VerifierRegistration:
        _text("verifier_id", verifier_id)
        try:
            return self._registrations[verifier_id]
        except KeyError as exc:
            raise KeyError(f"unregistered verifier authority: {verifier_id}") from exc

    def register(self, *_: object, **__: object) -> None:
        raise TypeError("the verifier authority registry is closed")


DEFAULT_AUTHORITY_REGISTRY = VerifierAuthorityRegistry()


@dataclass(frozen=True)
class VerifierEvidenceManifest:
    """Canonical evidence whose claimed digest and PASS are both rechecked."""

    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str
    authority_id: str
    verifier_id: str
    verifier_version: str
    implementation_digest: str
    role: VerifierRole
    authorized_scope: str
    registration_digest: str
    environment_digest: str
    canonical_input_json: str
    input_artifact_digests: tuple[str, ...]
    observed_result: VerifierResult
    evidence_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "base_digest",
            "candidate_digest",
            "scope_digest",
            "obligation_set_digest",
            "implementation_digest",
            "registration_digest",
            "environment_digest",
            "evidence_sha256",
        ):
            _sha256(name, getattr(self, name))
        for name in (
            "authority_id",
            "verifier_id",
            "verifier_version",
            "authorized_scope",
            "canonical_input_json",
        ):
            _text(name, getattr(self, name))
        object.__setattr__(self, "role", VerifierRole(self.role))
        if not isinstance(self.input_artifact_digests, tuple):
            raise TypeError("input_artifact_digests must be a tuple")
        for item in self.input_artifact_digests:
            _sha256("input_artifact_digest", item)
        if len(set(self.input_artifact_digests)) != len(self.input_artifact_digests):
            raise ValueError("input artifact digests must be unique")
        if not isinstance(self.observed_result, VerifierResult):
            raise TypeError("observed_result must be VerifierResult")

    def evidence_body(self) -> dict[str, object]:
        return {
            "schema": "egrt.verifier-evidence.v1",
            "base_digest": self.base_digest,
            "candidate_digest": self.candidate_digest,
            "scope_digest": self.scope_digest,
            "obligation_set_digest": self.obligation_set_digest,
            "authority_id": self.authority_id,
            "verifier_id": self.verifier_id,
            "verifier_version": self.verifier_version,
            "implementation_digest": self.implementation_digest,
            "role": self.role.value,
            "authorized_scope": self.authorized_scope,
            "registration_digest": self.registration_digest,
            "environment_digest": self.environment_digest,
            "canonical_input_sha256": digest(self.canonical_input_json),
            "input_artifact_digests": list(self.input_artifact_digests),
            "observed_result": self.observed_result,
        }

    @property
    def computed_evidence_sha256(self) -> str:
        return digest(self.evidence_body())

    def trace(self) -> dict[str, object]:
        body = self.evidence_body()
        body["evidence_sha256"] = self.evidence_sha256
        body["evidence_digest_recomputed"] = (
            self.evidence_sha256 == self.computed_evidence_sha256
        )
        body["raw_verifier_input_stored"] = False
        return body


def issue_verifier_evidence(
    *,
    verifier_id: str,
    role: VerifierRole,
    base_digest: str,
    candidate_digest: str,
    scope_digest: str,
    obligation_set_digest: str,
    input_data: Mapping[str, object],
    input_artifact_digests: tuple[str, ...] = (),
) -> VerifierEvidenceManifest:
    """Run a closed host verifier and issue evidence from the observed result."""

    role = VerifierRole(role)
    registration = DEFAULT_AUTHORITY_REGISTRY.resolve(verifier_id)
    if not registration.active:
        raise ValueError("verifier registration is stale")
    if role not in registration.authorized_roles:
        raise ValueError("verifier is not authorized for requested role")
    canonical_input = canonical_json(dict(input_data))
    parsed = json.loads(canonical_input)
    if not isinstance(parsed, dict):
        raise TypeError("canonical verifier input must be a JSON object")
    result = DEFAULT_REGISTRY.run(verifier_id, parsed)
    bound_artifacts = tuple(
        dict.fromkeys(
            (
                base_digest,
                candidate_digest,
                scope_digest,
                obligation_set_digest,
                *input_artifact_digests,
            )
        )
    )
    provisional = VerifierEvidenceManifest(
        base_digest,
        candidate_digest,
        scope_digest,
        obligation_set_digest,
        registration.authority_id,
        registration.verifier_id,
        registration.verifier_version,
        registration.implementation_digest,
        role,
        registration.authorized_scope,
        registration.registration_digest,
        registration.environment_digest,
        canonical_input,
        bound_artifacts,
        result,
        "0" * 64,
    )
    return replace(provisional, evidence_sha256=provisional.computed_evidence_sha256)


def validate_verifier_evidence(
    manifest: VerifierEvidenceManifest,
    *,
    required_role: VerifierRole,
    expected_bindings: tuple[str, str, str, str] | None = None,
) -> tuple[bool, str]:
    """Recompute identity, evidence content, and the verifier observation."""

    if not isinstance(manifest, VerifierEvidenceManifest):
        raise TypeError("manifest must be VerifierEvidenceManifest")
    required_role = VerifierRole(required_role)
    try:
        registration = DEFAULT_AUTHORITY_REGISTRY.resolve(manifest.verifier_id)
    except KeyError:
        return False, "verifier_unregistered"
    if not registration.active:
        return False, "verifier_registration_stale"
    if required_role not in registration.authorized_roles or manifest.role is not required_role:
        return False, "verifier_role_unauthorized"
    if manifest.authority_id != registration.authority_id:
        return False, "verifier_authority_mismatch"
    if manifest.verifier_version != registration.verifier_version:
        return False, "verifier_version_mismatch"
    if manifest.implementation_digest != registration.implementation_digest:
        return False, "verifier_implementation_mismatch"
    if manifest.authorized_scope != registration.authorized_scope:
        return False, "verifier_scope_unauthorized"
    if manifest.registration_digest != registration.registration_digest:
        return False, "verifier_registration_stale_or_forged"
    if manifest.environment_digest != registration.environment_digest:
        return False, "verifier_environment_stale_or_forged"
    if expected_bindings is not None:
        actual_bindings = (
            manifest.base_digest,
            manifest.candidate_digest,
            manifest.scope_digest,
            manifest.obligation_set_digest,
        )
        if actual_bindings != expected_bindings:
            return False, "evidence_candidate_scope_or_obligation_binding_mismatch"
        if not set(expected_bindings).issubset(set(manifest.input_artifact_digests)):
            return False, "evidence_binding_artifacts_missing"
    if manifest.evidence_sha256 != manifest.computed_evidence_sha256:
        return False, "evidence_digest_forged"
    try:
        parsed = json.loads(manifest.canonical_input_json)
    except json.JSONDecodeError:
        return False, "evidence_input_not_json"
    if not isinstance(parsed, dict):
        return False, "evidence_input_not_object"
    if canonical_json(parsed) != manifest.canonical_input_json:
        return False, "evidence_input_not_canonical"
    rerun = DEFAULT_REGISTRY.run(manifest.verifier_id, parsed)
    if rerun != manifest.observed_result:
        return False, "verifier_observation_replay_mismatch"
    return True, "registered_verifier_evidence_replayed"
