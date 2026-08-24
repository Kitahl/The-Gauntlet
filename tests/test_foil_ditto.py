"""Adversarial contract tests for the bounded Ditto resolver."""

from __future__ import annotations

import ast
import inspect
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_ditto as ditto  # noqa: E402
from egrt_claims import ImmutableBindings  # noqa: E402
from foil_candidate_state import (  # noqa: E402
    AuthorityIssuer,
    CandidateBinding,
    CandidateDecision,
    CandidateState,
)
from foil_v5_metrics import DiagnosticCapabilityRequirement  # noqa: E402

DIGEST = "a" * 64


def requirement(capability: str) -> DiagnosticCapabilityRequirement:
    return DiagnosticCapabilityRequirement(
        requirement_id="need-1",
        capability=capability,
        bindings=ImmutableBindings(
            a0_digest=DIGEST,
            task_digest=DIGEST,
            spec_digest=DIGEST,
            compiler_digest=DIGEST,
            config_digest=DIGEST,
        ),
    )


def manifest(capability: str, status: str = "READY") -> dict:
    return {
        "providers": [
            {
                "name": "closed-provider",
                "capability": capability,
                "status": status,
                "priority": 1,
            }
        ]
    }


class DittoResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.binding = CandidateBinding(
            candidate_id="candidate-1",
            task_digest="b" * 64,
            base_answer_digest="c" * 64,
            protocol_digest="d" * 64,
            config_digest="e" * 64,
            partition_digest="f" * 64,
            budget_ceiling_digest="0" * 64,
        )
        self.issuer = AuthorityIssuer("host-issuer", b"s" * 32)
        self.now = "2026-08-24T12:00:00+00:00"
        token = self.issuer.mint(
            self.binding,
            CandidateState.ACTIVE,
            "1" * 64,
            issued_at="2026-08-24T00:00:00+00:00",
            expires_at="2026-08-25T00:00:00+00:00",
            nonce="active-token",
        )
        self.active = CandidateDecision(CandidateState.ACTIVE, "verified", token)

    def resolve(
        self,
        required: DiagnosticCapabilityRequirement,
        provider_manifest: dict,
        *,
        claim_type: str,
        candidate: CandidateDecision | CandidateState,
        **kwargs: object,
    ) -> ditto.DittoResolution:
        return ditto.resolve_diagnostic_requirement(
            required,
            provider_manifest,
            claim_type=claim_type,
            candidate=candidate,
            binding=self.binding,
            issuer=self.issuer,
            now=self.now,
            **kwargs,
        )

    def test_dormant_candidate_can_only_suggest(self) -> None:
        result = self.resolve(
            requirement("WEB_SEARCH"),
            manifest("WEB_SEARCH"),
            claim_type="current_fact",
            candidate=CandidateState.DORMANT,
        )

        self.assertEqual(result.disposition, ditto.DittoDisposition.SUGGEST)
        self.assertEqual(result.reason_code, "candidate_not_active")
        self.assertIsNone(result.provider_name)
        self.assertFalse(result.execution_authorized)
        self.assertTrue(result.host_action_required)

    def test_ready_active_exact_route_returns_host_denied_use(self) -> None:
        result = self.resolve(
            requirement("WEB_SEARCH"),
            manifest("WEB_SEARCH"),
            claim_type="current_fact",
            candidate=self.active,
        )

        self.assertEqual(result.disposition, ditto.DittoDisposition.USE)
        self.assertEqual(result.provider_name, "closed-provider")
        self.assertEqual(result.route_status, "READY")
        self.assertFalse(result.execution_authorized)
        self.assertTrue(result.host_action_required)

    def test_configured_not_ready_fails_closed(self) -> None:
        result = self.resolve(
            requirement("WEB_SEARCH"),
            manifest("WEB_SEARCH", "CONFIGURED"),
            claim_type="current_fact",
            candidate=self.active,
        )

        self.assertEqual(result.disposition, ditto.DittoDisposition.UNAVAILABLE)
        self.assertEqual(result.reason_code, "route_unavailable")

    def test_wrong_ready_route_fails_closed_without_fallback(self) -> None:
        result = self.resolve(
            requirement("WEB_SEARCH"),
            manifest("SCHOLARLY_SEARCH"),
            claim_type="prior_art",
            candidate=self.active,
        )

        self.assertEqual(result.disposition, ditto.DittoDisposition.UNAVAILABLE)
        self.assertEqual(result.reason_code, "route_capability_mismatch")

    def test_closed_recipe_requires_exact_active_ready_capability(self) -> None:
        result = self.resolve(
            requirement("CODE_EXECUTION"),
            manifest("CODE_EXECUTION"),
            claim_type="software_behavior",
            candidate=self.active,
            recipe_id="deterministic-code-check-v1",
        )

        self.assertEqual(result.disposition, ditto.DittoDisposition.METHOD_ONLY)
        self.assertEqual(result.recipe_id, "deterministic-code-check-v1")
        self.assertFalse(result.execution_authorized)

        mismatch = self.resolve(
            requirement("WEB_SEARCH"),
            manifest("WEB_SEARCH"),
            claim_type="current_fact",
            candidate=self.active,
            recipe_id="deterministic-code-check-v1",
        )
        self.assertEqual(mismatch.disposition, ditto.DittoDisposition.UNAVAILABLE)
        self.assertEqual(mismatch.reason_code, "recipe_capability_mismatch")

    def test_unknown_capability_and_recipe_fail_closed(self) -> None:
        unknown_capability = self.resolve(
            requirement("UNRECOGNIZED"),
            manifest("WEB_SEARCH"),
            claim_type="current_fact",
            candidate=self.active,
        )
        self.assertEqual(unknown_capability.disposition, ditto.DittoDisposition.UNAVAILABLE)
        self.assertEqual(unknown_capability.reason_code, "unknown_required_capability")

        unknown_recipe = self.resolve(
            requirement("WEB_SEARCH"),
            manifest("WEB_SEARCH"),
            claim_type="current_fact",
            candidate=self.active,
            recipe_id="caller-supplied-code",
        )
        self.assertEqual(unknown_recipe.disposition, ditto.DittoDisposition.UNAVAILABLE)
        self.assertEqual(unknown_recipe.reason_code, "recipe_not_reviewed")

    def test_active_requires_a_verified_bound_unexpired_authority_token(self) -> None:
        cases = (
            ("raw_active", CandidateState.ACTIVE, self.binding, self.issuer, self.now),
            (
                "no_token",
                CandidateDecision(CandidateState.ACTIVE, "forged-state"),
                self.binding,
                self.issuer,
                self.now,
            ),
            (
                "forged_token",
                CandidateDecision(
                    CandidateState.ACTIVE,
                    "tampered",
                    replace(self.active.token, signature="0" * 64),
                ),
                self.binding,
                self.issuer,
                self.now,
            ),
            (
                "expired_token",
                CandidateDecision(
                    CandidateState.ACTIVE,
                    "expired",
                    self.issuer.mint(
                        self.binding,
                        CandidateState.ACTIVE,
                        "2" * 64,
                        issued_at="2026-08-20T00:00:00+00:00",
                        expires_at="2026-08-21T00:00:00+00:00",
                        nonce="expired-token",
                    ),
                ),
                self.binding,
                self.issuer,
                self.now,
            ),
            (
                "wrong_binding",
                self.active,
                CandidateBinding(
                    candidate_id="candidate-2",
                    task_digest="2" * 64,
                    base_answer_digest="3" * 64,
                    protocol_digest="4" * 64,
                    config_digest="5" * 64,
                    partition_digest="6" * 64,
                    budget_ceiling_digest="7" * 64,
                ),
                self.issuer,
                self.now,
            ),
        )
        for name, candidate, binding, issuer, now in cases:
            with self.subTest(name=name):
                result = ditto.resolve_diagnostic_requirement(
                    requirement("WEB_SEARCH"),
                    manifest("WEB_SEARCH"),
                    claim_type="current_fact",
                    candidate=candidate,
                    binding=binding,
                    issuer=issuer,
                    now=now,
                )
                self.assertEqual(result.disposition, ditto.DittoDisposition.UNAVAILABLE)
                self.assertEqual(result.reason_code, "active_authority_missing_or_invalid")

    def test_module_has_no_execution_or_external_runtime_path(self) -> None:
        source = inspect.getsource(ditto)
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        forbidden = {
            "subprocess",
            "socket",
            "requests",
            "urllib",
            "http",
            "foil_tool_broker",
            "gauntlet_runtime",
            "mastermind_runtime",
        }
        self.assertFalse(imported & forbidden)
        self.assertNotIn("def execute", source)
        self.assertNotIn("def invoke", source)
        self.assertNotIn("def call_provider", source)


if __name__ == "__main__":
    unittest.main()
