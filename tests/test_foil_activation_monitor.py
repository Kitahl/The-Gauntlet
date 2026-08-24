from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_activation_monitor as monitor_module  # noqa: E402
from foil_activation_monitor import (  # noqa: E402
    ActivationEvent,
    ActivationOutcome,
    ContinuationLease,
    FeatureMode,
    FoilActivationMonitor,
    ReasonCode,
    parse_feature_mode,
)
from foil_signal_boundary import SignalAuthority  # noqa: E402


def profile_loader():
    calls = []
    profile = object()

    def load():
        calls.append(True)
        return profile

    return load, calls, profile


class FoilActivationMonitorTests(unittest.TestCase):
    def test_feature_mode_parser_uses_caller_legacy_default_and_fails_closed(self):
        self.assertIs(
            parse_feature_mode(None, legacy_default=FeatureMode.OBSERVE),
            FeatureMode.OBSERVE,
        )
        self.assertIs(parse_feature_mode("smart"), FeatureMode.SMART)
        self.assertIs(parse_feature_mode(FeatureMode.SMART), FeatureMode.SMART)
        self.assertIs(parse_feature_mode("not-a-mode"), FeatureMode.OFF)

    def test_off_and_l0_inactive_never_call_injected_dependencies(self):
        loader, calls, _ = profile_loader()
        routed = []
        rendered = []
        monitor = FoilActivationMonitor(
            loader,
            lambda *_: routed.append(True) or True,
            lambda _: rendered.append(True) or "context",
        )
        self.assertIs(
            monitor.evaluate(ActivationEvent("/foil please"), FeatureMode.OFF).outcome,
            ActivationOutcome.INACTIVE_NO_TRIGGER,
        )
        self.assertIs(
            monitor.evaluate(ActivationEvent("ordinary request"), FeatureMode.SMART).outcome,
            ActivationOutcome.INACTIVE_NO_TRIGGER,
        )
        self.assertEqual(calls, [])
        self.assertEqual(routed, [])
        self.assertEqual(rendered, [])

    def test_legacy_is_a_no_load_delegation_state(self):
        loader, calls, _ = profile_loader()
        result = FoilActivationMonitor(loader).evaluate(
            ActivationEvent("/foil"), FeatureMode.LEGACY
        )
        self.assertIs(result.outcome, ActivationOutcome.UNAVAILABLE)
        self.assertIn(ReasonCode.LEGACY_DELEGATED, result.trace.reason_codes)
        self.assertEqual(calls, [])

    def test_explicit_activation_is_event_driven_and_context_is_capped(self):
        loader, calls, _ = profile_loader()
        result = FoilActivationMonitor(loader, context_renderer=lambda _: "x" * 1400).evaluate(
            ActivationEvent("please use FOIL now"), FeatureMode.SMART
        )
        self.assertIs(result.outcome, ActivationOutcome.ACTIVE_EXPLICIT)
        self.assertTrue(result.state_transition_required)
        self.assertEqual(len(result.active_context), 1200)
        self.assertEqual(result.trace.context_chars, 1200)
        self.assertEqual(result.trace.routing_decisions, 0)
        self.assertEqual(len(calls), 1)

    def test_frozen_binding_activates_without_task_matching(self):
        result = FoilActivationMonitor().evaluate(
            ActivationEvent("ordinary", frozen_run_binding="frozen-42"),
            FeatureMode.SMART,
        )
        self.assertIs(result.outcome, ActivationOutcome.ACTIVE_FROZEN_RUN)

    def test_opaque_requirement_and_profile_use_one_router_decision(self):
        loader, _, profile = profile_loader()
        requirement = object()
        router_calls = []

        def router(candidate, loaded):
            router_calls.append((candidate, loaded))
            return candidate is requirement and loaded is profile

        result = FoilActivationMonitor(loader, router).evaluate(
            ActivationEvent("ordinary", task_requirement=requirement, requirement_joinable=True),
            FeatureMode.SMART,
        )
        self.assertIs(result.outcome, ActivationOutcome.ACTIVE_TASK_RELEVANCE)
        self.assertEqual(result.trace.routing_decisions, 1)
        self.assertEqual(router_calls, [(requirement, profile)])

    def test_unknown_or_ambiguous_task_stands_down(self):
        loader, _, _ = profile_loader()
        result = FoilActivationMonitor(loader, lambda *_: False).evaluate(
            ActivationEvent("ordinary", task_requirement=object(), requirement_joinable=True),
            FeatureMode.SMART,
        )
        self.assertIs(result.outcome, ActivationOutcome.UNAVAILABLE)
        self.assertEqual(result.active_context, "")
        self.assertFalse(result.state_transition_required)
        self.assertIn(ReasonCode.UNKNOWN_OR_AMBIGUOUS, result.trace.reason_codes)

    def test_continuation_is_bounded_and_expiry_stands_down_without_load(self):
        loader, calls, _ = profile_loader()
        expired = ContinuationLease(issued_at_monotonic=10.0, expires_at_monotonic=20.0)
        result = FoilActivationMonitor(loader).evaluate(
            ActivationEvent("ordinary", continuation_lease=expired, now_monotonic=20.0),
            FeatureMode.SMART,
        )
        self.assertIs(result.outcome, ActivationOutcome.INACTIVE_NO_TRIGGER)
        self.assertIn(ReasonCode.CONTINUATION_EXPIRED, result.trace.reason_codes)
        self.assertEqual(calls, [])
        active = ContinuationLease(issued_at_monotonic=10.0, expires_at_monotonic=20.0)
        self.assertIs(
            FoilActivationMonitor()
            .evaluate(
                ActivationEvent("ordinary", continuation_lease=active, now_monotonic=19.0),
                FeatureMode.SMART,
            )
            .outcome,
            ActivationOutcome.ACTIVE_CONTINUATION,
        )
        too_long = ContinuationLease(issued_at_monotonic=0.0, expires_at_monotonic=301.0)
        self.assertIs(
            FoilActivationMonitor()
            .evaluate(
                ActivationEvent("ordinary", continuation_lease=too_long, now_monotonic=1.0),
                FeatureMode.SMART,
            )
            .outcome,
            ActivationOutcome.INACTIVE_NO_TRIGGER,
        )

    def test_cost_cap_and_observe_never_emit_context_or_update_profile(self):
        loader, calls, _ = profile_loader()
        render_calls = []
        monitor = FoilActivationMonitor(
            loader,
            context_renderer=lambda _: render_calls.append(True) or "sensitive profile",
        )
        capped = monitor.evaluate(
            ActivationEvent("/foil", available_context_chars=0), FeatureMode.SMART
        )
        self.assertIs(capped.outcome, ActivationOutcome.STAND_DOWN_COST_CAP)
        self.assertEqual(calls, [])
        observed = monitor.evaluate(ActivationEvent("/foil"), FeatureMode.OBSERVE)
        self.assertIs(observed.outcome, ActivationOutcome.ACTIVE_EXPLICIT)
        self.assertEqual(observed.active_context, "")
        self.assertEqual(observed.trace.context_chars, 0)
        self.assertFalse(observed.profile_update_required)
        self.assertFalse(observed.state_transition_required)
        self.assertEqual(render_calls, [])

    def test_renderer_faults_and_non_text_results_fail_soft(self):
        loader, _, _ = profile_loader()

        def explode(_):
            raise RuntimeError("renderer unavailable")

        for renderer in (explode, lambda _: None):
            with self.subTest(renderer=renderer):
                result = FoilActivationMonitor(loader, context_renderer=renderer).evaluate(
                    ActivationEvent("/foil"), FeatureMode.SMART
                )
                self.assertEqual(result.active_context, "")
                self.assertIn(ReasonCode.PROFILE_UNAVAILABLE, result.trace.reason_codes)

    def test_trace_has_only_hashes_and_control_only_signals(self):
        raw_prompt = "/foil do not expose: S3CR3T"
        result = FoilActivationMonitor().evaluate(ActivationEvent(raw_prompt), FeatureMode.SMART)
        trace_text = repr(result.trace)
        self.assertNotIn(raw_prompt, trace_text)
        self.assertNotIn("S3CR3T", trace_text)
        self.assertEqual(len(result.trace.prompt_hash), 64)
        self.assertTrue(
            all(signal.boundary is SignalAuthority.CONTROL_ONLY for signal in result.trace.signals)
        )
        self.assertLessEqual(result.trace.routing_decisions, 1)

    def test_module_has_no_model_or_network_imports_by_construction(self):
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(ast.parse(inspect.getsource(monitor_module)))
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(
            {"requests", "socket", "urllib", "httpx", "openai", "subprocess"}.isdisjoint(imports)
        )


if __name__ == "__main__":
    unittest.main()
