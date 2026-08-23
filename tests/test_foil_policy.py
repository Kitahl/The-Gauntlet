"""Exhaustive enumeration of the bench bucket domain against the real V2 kernel.

`benchmarks/harness/bench_foil_session.py` declares a finite `(task, profile)`
domain and fourteen invariants. For a finite domain, enumeration is a proof, not
a sample, so this module runs the whole grid through the adapter and pins the
result — including the positive control, because fourteen "never routes"
invariants are all satisfied by a policy that never routes at all.

The enumeration is ~1.16M `decide()` calls and takes roughly 30 s. The task
contexts and profile signals are built once and cached by the adapter; if this
needs to get faster, cache harder — do not sample, because a sampled run stops
being a proof.
"""
from __future__ import annotations

import importlib.util
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

HARNESS_PATH = ROOT / "benchmarks" / "harness" / "bench_foil_session.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("bench_foil_session", HARNESS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # `dataclasses` resolves annotations through `sys.modules[cls.__module__]`,
    # so the module must be registered before it is executed.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bench = _load_harness()

#: Enumeration budget on this machine. Measured ~30 s; 60 s is the contract.
TIME_BUDGET_SECONDS = 60.0


class AdapterMapTests(unittest.TestCase):
    """The bucket -> kernel map is the only bridge; pin the load-bearing parts."""

    def test_complement_map_is_injective_and_total(self):
        self.assertEqual(sorted(bench.COMPLEMENT_KIND), sorted(bench.DOMAIN["complement_kind"]))
        self.assertEqual(len(set(bench.COMPLEMENT_KIND.values())), len(bench.COMPLEMENT_KIND))
        import foil_policy as fp
        for name in bench.COMPLEMENT_KIND.values():
            self.assertIn(name, fp.ComplementKind.__members__)

    def test_bucket_values_land_in_the_v2_tier_bands(self):
        """The map is derived from V2's own thresholds, not invented."""
        import foil_policy as fp
        policy = fp.RuntimePolicyV2()

        def tier(relevance: str, support: str, obs: int, transfer: int):
            return policy._profile_evidence_tier(fp.ProfileSignal(
                relevance=bench.RELEVANCE_VALUE[relevance],
                support=bench.SUPPORT_VALUE[support],
                independent_observations=obs,
                transfer_confirmations=transfer,
                direction=fp.EvidenceDirection.UNCERTAIN,
            ))

        self.assertIs(tier("none", "supported", 3, 2), fp.ProfileInfluence.NONE)
        self.assertIs(tier("low", "weak", 3, 2), fp.ProfileInfluence.LOW)
        self.assertIs(tier("medium", "supported", 3, 2), fp.ProfileInfluence.LOW)
        self.assertIs(tier("high", "supported", 3, 2), fp.ProfileInfluence.MODERATE)
        # The declared domain stops at 3 observations, so HIGH (>= 5) is out of reach.
        self.assertIs(tier("high", "supported", 2, 2), fp.ProfileInfluence.LOW)
        self.assertEqual(max(bench.DOMAIN["independent_observations"]), 3)

    def test_uncertainty_complement_is_outside_the_bucket_image(self):
        """This is what keeps I08/I09 honest - see the harness docstring.

        If a synthesised uncertainty could derive a complement a bench profile is
        able to name, V2 could legitimately route on it while the bench task
        declared a different single requirement, and I08 would report a
        counterexample that is an artefact of the projection.
        """
        import foil_policy as fp
        derived = fp.CLAIM_COMPLEMENTS[getattr(fp.ClaimKind, bench.UNCERTAINTY_CLAIM_KIND)]
        image = {getattr(fp.ComplementKind, n) for n in bench.COMPLEMENT_KIND.values()}
        self.assertEqual(derived & image, set())

    def test_regimes_do_not_manufacture_bucket_complements(self):
        """Same reason: the mapped regimes must add no complement a profile can name."""
        import foil_policy as fp
        policy = fp.RuntimePolicyV2()
        image = {getattr(fp.ComplementKind, n) for n in bench.COMPLEMENT_KIND.values()}
        for regime, flags in bench.REGIME_FLAGS.items():
            context = fp.TaskContext(**flags)
            derived = policy.task_complements(context, policy.classify_regime(context))
            self.assertEqual(derived & image, set(), regime)

    def test_every_declared_regime_has_a_mapping(self):
        self.assertEqual(sorted(bench.REGIME_FLAGS), sorted(bench.REGIMES))

    def test_reference_fallback_is_not_silently_accepted(self):
        """A reference-only run must never be mistaken for a candidate run."""
        code = bench.main(["invariants", "--policy-module", "foil_no_such_module_xyz", "--quiet"])
        self.assertEqual(code, 1)


class ExhaustiveInvariantTests(unittest.TestCase):
    """One enumeration, many assertions."""

    @classmethod
    def setUpClass(cls):
        policy, source = bench.load_policy(bench.DEFAULT_POLICY_MODULE, bench.DEFAULT_POLICY_CLASS)
        cls.source = source
        started = time.monotonic()
        cls.result = bench.run_invariants(policy)
        cls.elapsed = time.monotonic() - started

    def test_the_real_kernel_was_exercised(self):
        self.assertEqual(self.source, "foil_policy.RuntimePolicyV2")
        self.assertEqual(self.result["policy_errors"], [])

    def test_enumeration_is_exhaustive_over_the_declared_domain(self):
        expected_profiles = 1
        for values in bench.DOMAIN.values():
            expected_profiles *= len(values)
        self.assertEqual(self.result["profile_states"], expected_profiles + 1)
        expected_tasks = len(bench.REGIMES) * (len(bench.DOMAIN["complement_kind"]) + 1) * 2 * 2 * 2
        self.assertEqual(self.result["task_states"], expected_tasks)
        self.assertEqual(
            self.result["decide_calls"],
            self.result["task_states"] * self.result["profile_states"],
        )
        self.assertTrue(self.result["exhaustive"])

    def test_all_fourteen_invariants_hold(self):
        self.assertEqual(len(self.result["invariants"]), 14)
        for key, row in self.result["invariants"].items():
            with self.subTest(invariant=key):
                self.assertEqual(row["violations"], 0, f"{key}: {row['counterexamples']}")
                self.assertEqual(row["verdict"], "PASS")
                self.assertEqual(row["checked"], self.result["decide_calls"])

    def test_positive_control_the_policy_actually_routes(self):
        self.assertGreater(self.result["routed_states"], 0, bench.VACUOUS_MESSAGE)
        self.assertEqual(self.result["positive_control"]["verdict"], "PASS")
        self.assertEqual(self.result["verdict"], "PASS")

    def test_enumeration_finishes_inside_the_budget(self):
        self.assertLess(self.elapsed, TIME_BUDGET_SECONDS, f"{self.elapsed:.1f}s")


if __name__ == "__main__":
    unittest.main()
