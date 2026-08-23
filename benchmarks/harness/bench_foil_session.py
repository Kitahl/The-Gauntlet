#!/usr/bin/env python3
"""FOIL session benchmark — runs entirely inside one session.

Why this exists
---------------
The prior plan spent 25 benchmark cells trying to establish two different kinds
of claim at once, and could establish neither:

* **Deterministic policy invariants.** `RuntimePolicyV2.decide()` is a pure
  function over a finite domain. Its invariants are decidable by enumeration —
  zero searches, zero items, zero gold exposure, and 100% power. They were
  instead assigned to receipts whose permitted trace fields do not record the
  state the invariants reference, making 7 of 14 unfalsifiable as specified.
* **Behavioural efficacy.** At five paired items the best attainable two-sided
  exact McNemar p is 0.0625, so the declared alpha of 0.05 is unreachable even
  on a perfect sweep.

This harness runs the first kind now and *sizes* the second kind honestly. It
never touches gold, never issues a search, and never spawns a child agent.

Model agnostic
--------------
Nothing here assumes a vendor. The invariant and power sections are model-free by
construction. The `models` section reads `.foil/models.json` (see
`tools/foil_setup.py`) and reports what is actually configured, which roles are
filled, and whether each model's determinism class forces replicates. The design
manifest is then sized against the models you actually have.

Subcommands
-----------
    invariants   exhaustively enumerate the ProfileSignal domain against the policy
    selfcheck    run the update regression suite
    models       report configured models, roles, determinism and replicate needs
    power        item/replicate sizing for the behavioural arm
    design       emit the behavioural-arm design manifest (blinding, gold pinning, grading)
    all          run everything and emit one hash-chained receipt

    python benchmarks/harness/bench_foil_session.py all
    python benchmarks/harness/bench_foil_session.py all --model-config .foil/models.json --live

Policy adapter — the bucket domain is a PROJECTION of the real kernel
---------------------------------------------------------------------
`ProfileSignal`/`TaskContext` below are a coarse **string-bucket domain**. The
real kernel (`tools/foil_policy.RuntimePolicyV2`, ported from
`experiments/foil_vnext/runtime_policy_v2.py` at `9540860`) is enum/float typed.
`_to_policy_inputs()` is the only bridge, and every value in it is derived from
V2's own thresholds in `_profile_evidence_tier` / `profile_gate` rather than
invented here:

* ``relevance``  none=0.0, low=0.35, medium=0.60, high=0.90.
  V2 tiers on 0.35 / 0.60 / 0.75 / 0.90; these four values sit one in each band,
  so ``low`` is the lowest value that can reach LOW influence and ``high`` is the
  lowest value that can reach MODERATE/HIGH.
* ``support``    unsupported=0.0, weak=0.40, supported=0.90.
  V2 tiers on 0.35 / 0.60 / 0.70 / 0.85; ``weak`` clears only the LOW floor and
  ``supported`` clears the MODERATE and HIGH floors.
* ``independent_observations`` and ``transfer_confirmations`` pass through
  unchanged (V2 compares them against 1/2/3/5 directly). The declared domain
  stops at 3 observations, so the HIGH tier (>= 5) is unreachable from this
  domain by construction; MODERATE is the highest tier the bucket domain can
  express, and MODERATE is enough to route.
* ``stale`` passes through unchanged.
* ``direction``  GAP/STRENGTH/UNCERTAIN -> ``EvidenceDirection``.
* ``complement_kind`` -> ``ComplementKind`` by ``COMPLEMENT_KIND`` below, an
  explicit and injective table. Injectivity matters: I08/I09 compare the routed
  complement against the task's declared requirement, which requires mapping the
  kernel's answer back to a bucket.
* ``requires_complement`` -> ``TaskContext.required_complements``
  (``frozenset()`` when the task declares no requirement).
* ``load_bearing_uncertainties`` -> ``TaskContext.uncertainties``, one
  ``LoadBearingUncertainty`` per count, claim kind ``EXECUTABLE``.
* ``viable_answer_exists`` -> ``has_viable_candidate``;
  ``mandatory_verifiers_complete`` -> ``completed_verifiers``.
* ``regime`` -> ``TaskContext`` flags by ``REGIME_FLAGS`` below.

Two adapter choices are load-bearing and are stated rather than hidden:

1. **Why the uncertainty claim kind is ``EXECUTABLE``.** V2 derives task
   complements from unresolved uncertainties via ``CLAIM_COMPLEMENTS``.
   ``EXECUTABLE`` derives exactly ``IMPLEMENTATION_EXECUTION``, which is *not*
   in the image of ``COMPLEMENT_KIND``. A profile in this domain therefore can
   never name a complement that an uncertainty manufactured, so the bench
   task's single declared ``requires_complement`` stays the whole truth about
   what the task requires — which is what I08/I09 assume.
2. **Why the regimes map onto flag combinations that classify as
   ``MIXED_TOOL_TASK`` / ``CLOSED_BOOK_TECHNICAL_REASONING``.** The other four
   V2 regimes add complements of their own (external retrieval adds
   ``TOOL_SELECTION``, freshness adds ``EVIDENCE_DISCIPLINE`` +
   ``TOOL_SELECTION``, closed-context multi-hop adds ``DECOMPOSITION``,
   abstract transformation adds ``TRANSFER_ADAPTATION`` + ``ERROR_DETECTION``),
   all of which *are* in the image of ``COMPLEMENT_KIND``. Under those regimes
   V2 can legitimately route on a complement the regime requires while the
   bench task declared a different single requirement — an I08/I09
   "counterexample" that is an artefact of the bucket domain being too coarse
   to express V2's requirement set, not a kernel defect. Those four regimes are
   therefore out of scope for this enumeration and are exercised directly by
   `tests/test_foil_policy_v2.py`. **This is a known limitation of the declared
   domain, recorded here rather than papered over.**

``--policy-module`` names the module exposing the candidate (default
``foil_policy``). If it cannot be imported the harness runs against
``ReferencePolicy`` below, marks ``policy_source: REFERENCE`` in the receipt and
**exits 1** unless ``--allow-reference`` was passed, so a reference-only run can
never be mistaken for a run against the real candidate.

Boundary: everything here is about mechanism. Nothing here is evidence that a
profile-driven complement improves any answer.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import itertools
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import comb
from pathlib import Path
from typing import Any, Callable, Iterator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

SCHEMA = "foil-session-bench/v1"
GENESIS = "0" * 64
DEFAULT_POLICY_MODULE = "foil_policy"
DEFAULT_POLICY_CLASS = "RuntimePolicyV2"
VACUOUS_MESSAGE = "invariants vacuous: policy never routes"

# --------------------------------------------------------------------------- #
# declared ProfileSignal domain                                                #
# --------------------------------------------------------------------------- #

DOMAIN: dict[str, list[Any]] = {
    "direction": ["GAP", "STRENGTH", "UNCERTAIN"],
    "complement_kind": ["METHOD", "EVIDENCE", "VERIFIER", "PREREQUISITE", "REPRESENTATION", "TOOL"],
    "relevance": ["none", "low", "medium", "high"],
    "support": ["unsupported", "weak", "supported"],
    "independent_observations": [0, 1, 2, 3],
    "transfer_confirmations": [0, 1, 2],
    "stale": [False, True],
}
#: Whether the task currently requires the complement the profile names.
TASK_REQUIREMENT = [True, False]


@dataclass(frozen=True)
class ProfileSignal:
    direction: str
    complement_kind: str
    relevance: str
    support: str
    independent_observations: int
    transfer_confirmations: int
    stale: bool


@dataclass(frozen=True)
class TaskContext:
    regime: str
    requires_complement: str | None
    load_bearing_uncertainties: int
    viable_answer_exists: bool
    mandatory_verifiers_complete: bool


@dataclass(frozen=True)
class Decision:
    profile_influence: bool
    profile_route_allowed: bool
    targeted_complement: str | None
    primary_effort_mode: str
    stop_reason: str | None
    extra_assistance: bool
    tool_budget_delta: int
    verifiers_removed: int


# --------------------------------------------------------------------------- #
# reference policy — the behaviour the invariants describe                     #
# --------------------------------------------------------------------------- #

class ReferencePolicy:
    """A minimal policy that satisfies the declared invariants.

    It exists so the harness is self-testing and so a counterexample against the
    real candidate can be compared to intended behaviour. It is NOT the candidate.
    """

    def decide(self, task: TaskContext, profile: ProfileSignal | None) -> Decision:
        allowed = self._route_allowed(task, profile)
        complement = profile.complement_kind if (allowed and profile) else None
        if task.viable_answer_exists and task.load_bearing_uncertainties == 0 and task.mandatory_verifiers_complete:
            stop, mode = "ANSWER_SETTLED", "COMMIT"
        else:
            stop, mode = None, "RESOLVE_UNCERTAINTY"
        return Decision(
            profile_influence=profile is not None,
            profile_route_allowed=allowed,
            targeted_complement=complement,
            primary_effort_mode=mode,
            stop_reason=stop,
            extra_assistance=allowed,
            tool_budget_delta=0,
            verifiers_removed=0,
        )

    @staticmethod
    def _route_allowed(task: TaskContext, profile: ProfileSignal | None) -> bool:
        if profile is None:
            return False
        if profile.direction != "GAP":
            return False                                  # only a GAP can route
        if profile.support != "supported":
            return False                                  # weak/unsupported never routes
        if profile.stale:
            return False                                  # stale never routes
        if profile.transfer_confirmations < 1:
            return False                                  # transfer confirmation required
        if profile.independent_observations < 2:
            return False
        if profile.relevance == "none":
            return False                                  # relevance alone is not competence
        if task.requires_complement != profile.complement_kind:
            return False                                  # must match a current requirement
        if task.viable_answer_exists and task.load_bearing_uncertainties == 0 \
                and task.mandatory_verifiers_complete:
            return False                                  # completed tasks get no gratuitous review
        return True


# --------------------------------------------------------------------------- #
# bucket domain  <->  real V2 kernel                                           #
# --------------------------------------------------------------------------- #

#: Bucket -> V2 `relevance` float. Values sit one per V2 tier band (see docstring).
RELEVANCE_VALUE: dict[str, float] = {"none": 0.0, "low": 0.35, "medium": 0.60, "high": 0.90}
#: Bucket -> V2 `support` float.
SUPPORT_VALUE: dict[str, float] = {"unsupported": 0.0, "weak": 0.40, "supported": 0.90}
#: Bucket -> V2 `ComplementKind` member name. Explicit and injective.
COMPLEMENT_KIND: dict[str, str] = {
    "METHOD": "DECOMPOSITION",
    "EVIDENCE": "EVIDENCE_DISCIPLINE",
    "VERIFIER": "ERROR_DETECTION",
    "PREREQUISITE": "FORMALIZATION",
    "REPRESENTATION": "TRANSFER_ADAPTATION",
    "TOOL": "TOOL_SELECTION",
}
COMPLEMENT_BUCKET: dict[str, str] = {v: k for k, v in COMPLEMENT_KIND.items()}
#: Bucket -> V2 `EvidenceDirection` member name.
DIRECTION_KIND: dict[str, str] = {
    "GAP": "GAP", "STRENGTH": "STRENGTH", "UNCERTAIN": "UNCERTAIN",
}
#: Bucket regime -> V2 `TaskContext` flags (see docstring for why these flags).
REGIME_FLAGS: dict[str, dict[str, Any]] = {
    "public_web": {"mixed_tool_task": True},
    "closed_book": {"closed_book": True, "technical_reasoning": True},
    "supplied_task_context_only": {"closed_context": True},
    "supplied_benchmark_context_only": {
        "closed_context": True, "benchmark": "supplied_benchmark_context_only",
    },
}
#: Claim kind used for a synthesised load-bearing uncertainty (see docstring).
UNCERTAINTY_CLAIM_KIND = "EXECUTABLE"
#: Actions counted as profile-driven extra assistance. `APPLY_TARGETED_COMPLEMENT`
#: is the only V2 action a profile can add; VERIFY_CANDIDATE, CHECK_OUTPUT_CONTRACT
#: and CHECK_RULE_AGAINST_ALL_EXAMPLES are the *task's own* obligations and fire
#: with no profile present, so counting them would make I04/I05/I13 meaningless.
EXTRA_ASSISTANCE_ACTIONS = ("APPLY_TARGETED_COMPLEMENT",)

assert len(COMPLEMENT_BUCKET) == len(COMPLEMENT_KIND), "COMPLEMENT_KIND must be injective"


def _to_policy_inputs(task: TaskContext, profile: ProfileSignal | None) -> tuple[Any, Any]:
    """Bucket domain -> real V2 kernel inputs. The only bridge; see module docstring."""
    import foil_policy as fp

    flags = dict(REGIME_FLAGS[task.regime])
    uncertainty = fp.LoadBearingUncertainty(
        "bench_load_bearing_uncertainty", getattr(fp.ClaimKind, UNCERTAINTY_CLAIM_KIND)
    )
    complete = frozenset(
        {fp.VerifierKind.OUTPUT_CONTRACT, fp.VerifierKind.EXECUTION_TEST}
    ) if task.mandatory_verifiers_complete else frozenset()
    context = fp.TaskContext(
        # `output_contract_required` is set on every task so that
        # `mandatory_verifiers_complete` actually binds: without a mandatory
        # verifier the bench flag would have no expression in the kernel and
        # V2's stop rule would not line up with the bench's completion rule.
        output_contract_required=True,
        has_viable_candidate=task.viable_answer_exists,
        uncertainties=tuple(uncertainty for _ in range(task.load_bearing_uncertainties)),
        completed_verifiers=complete,
        required_complements=(
            frozenset({getattr(fp.ComplementKind, COMPLEMENT_KIND[task.requires_complement])})
            if task.requires_complement else frozenset()
        ),
        **flags,
    )
    if profile is None:
        return context, None
    signal = fp.ProfileSignal(
        relevance=RELEVANCE_VALUE[profile.relevance],
        support=SUPPORT_VALUE[profile.support],
        independent_observations=profile.independent_observations,
        transfer_confirmations=profile.transfer_confirmations,
        stale=profile.stale,
        direction=getattr(fp.EvidenceDirection, DIRECTION_KIND[profile.direction]),
        complement=getattr(fp.ComplementKind, COMPLEMENT_KIND[profile.complement_kind]),
    )
    return context, signal


class V2PolicyAdapter:
    """Runs the real kernel over the bucket domain and adapts its `PolicyDecision`.

    Every state is decided twice — once with the profile and once without — so
    `tool_budget_delta` and `verifiers_removed` are *measured* differences rather
    than constants. Neither is clamped: clamping a positive budget delta to zero
    would make I11 unfalsifiable, which is the defect this harness exists to
    avoid. The no-profile decision depends only on the task, so it is cached.
    """

    def __init__(self, policy: Any) -> None:
        self.policy = policy
        self._contexts: dict[TaskContext, Any] = {}
        self._signals: dict[ProfileSignal, Any] = {}
        self._baseline: dict[TaskContext, Any] = {}

    def _context(self, task: TaskContext) -> Any:
        cached = self._contexts.get(task)
        if cached is None:
            cached, _ = _to_policy_inputs(task, None)
            self._contexts[task] = cached
        return cached

    def _signal(self, task: TaskContext, profile: ProfileSignal) -> Any:
        cached = self._signals.get(profile)
        if cached is None:
            _, cached = _to_policy_inputs(task, profile)
            self._signals[profile] = cached
        return cached

    def decide(self, task: TaskContext, profile: ProfileSignal | None) -> Decision:
        context = self._context(task)
        base = self._baseline.get(task)
        if base is None:
            base = self.policy.decide(context, None)
            self._baseline[task] = base
        raw = base if profile is None else self.policy.decide(context, self._signal(task, profile))

        targeted = raw.targeted_complement
        bucket = COMPLEMENT_BUCKET[targeted.name] if targeted is not None else None
        actions = {action.name for action in raw.actions}
        with_alloc, without_alloc = raw.resource_allocation, base.resource_allocation
        delta = (
            (with_alloc.search_query_priority + with_alloc.source_followup_priority)
            - (without_alloc.search_query_priority + without_alloc.source_followup_priority)
        )
        if with_alloc.retrieval_allowed and not without_alloc.retrieval_allowed:
            delta += 1
        elif without_alloc.retrieval_allowed and not with_alloc.retrieval_allowed:
            delta -= 1
        removed = len(set(base.required_verifiers) - set(raw.required_verifiers))
        return Decision(
            profile_influence=raw.profile_influence.name != "NONE",
            profile_route_allowed=bool(raw.profile_route_allowed),
            targeted_complement=bucket,
            primary_effort_mode=raw.primary_effort_mode.value,
            stop_reason=raw.stop_reason,
            extra_assistance=any(name in actions for name in EXTRA_ASSISTANCE_ACTIONS),
            tool_budget_delta=delta,
            verifiers_removed=removed,
        )


# --------------------------------------------------------------------------- #
# invariants                                                                   #
# --------------------------------------------------------------------------- #

Check = Callable[[TaskContext, "ProfileSignal | None", Decision], bool]


def _routed(d: Decision) -> bool:
    return bool(d.profile_route_allowed or d.targeted_complement is not None)


INVARIANTS: dict[str, tuple[str, Check]] = {
    "I01": ("relevance alone never becomes competence",
            lambda t, p, d: not (_routed(d) and p is not None and p.support != "supported")),
    "I02": ("stale profile evidence never routes",
            lambda t, p, d: not (_routed(d) and p is not None and p.stale)),
    "I03": ("weak profile evidence never routes",
            lambda t, p, d: not (_routed(d) and p is not None and p.support in {"unsupported", "weak"})),
    "I04": ("STRENGTH evidence never triggers extra assistance",
            lambda t, p, d: not (d.extra_assistance and p is not None and p.direction == "STRENGTH")),
    "I05": ("UNCERTAIN evidence never triggers extra assistance",
            lambda t, p, d: not (d.extra_assistance and p is not None and p.direction == "UNCERTAIN")),
    "I06": ("only supported GAP evidence can route",
            lambda t, p, d: not _routed(d) or (p is not None and p.direction == "GAP" and p.support == "supported")),
    "I07": ("transfer confirmation is required to route",
            lambda t, p, d: not (_routed(d) and p is not None and p.transfer_confirmations < 1)),
    "I08": ("routed complement matches a current task requirement",
            lambda t, p, d: d.targeted_complement is None or d.targeted_complement == t.requires_complement),
    "I09": ("wrong or irrelevant profile gaps are rejected",
            lambda t, p, d: not (_routed(d) and p is not None
                                 and (p.relevance == "none" or t.requires_complement != p.complement_kind))),
    "I10": ("at most one targeted complement per decision",
            lambda t, p, d: d.targeted_complement is None or isinstance(d.targeted_complement, str)),
    "I11": ("profile routing never expands the tool budget",
            lambda t, p, d: d.tool_budget_delta <= 0),
    "I12": ("profile routing never removes a mandatory verifier",
            lambda t, p, d: d.verifiers_removed == 0),
    "I13": ("a completed task receives no gratuitous extra review",
            lambda t, p, d: not (d.extra_assistance and t.viable_answer_exists
                                 and t.load_bearing_uncertainties == 0
                                 and t.mandatory_verifiers_complete)),
    "I14": ("no profile means no profile influence",
            lambda t, p, d: p is not None or not (d.profile_influence or _routed(d))),
}

REGIMES = ["public_web", "closed_book", "supplied_task_context_only", "supplied_benchmark_context_only"]


def iter_profiles() -> Iterator[ProfileSignal]:
    keys = list(DOMAIN)
    for combo in itertools.product(*(DOMAIN[k] for k in keys)):
        yield ProfileSignal(**dict(zip(keys, combo)))


def iter_tasks() -> Iterator[TaskContext]:
    for regime in REGIMES:
        for requirement in DOMAIN["complement_kind"] + [None]:
            for lbu in (0, 1):
                for viable in TASK_REQUIREMENT:
                    for verified in TASK_REQUIREMENT:
                        yield TaskContext(regime, requirement, lbu, viable, verified)


def load_policy(module_name: str | None, class_name: str) -> tuple[Any, str]:
    """Return `(decider, policy_source)`. `decider.decide(task, profile) -> Decision`."""
    if not module_name:
        return ReferencePolicy(), "REFERENCE"
    try:
        module = importlib.import_module(module_name)
        policy = getattr(module, class_name)()
        return V2PolicyAdapter(policy), f"{module_name}.{class_name}"
    except Exception as exc:  # noqa: BLE001 - any import failure must be visible, not silent
        print(f"[warn] could not load {module_name}.{class_name}: {exc}", file=sys.stderr)
        print("[warn] running against ReferencePolicy; receipt will say policy_source=REFERENCE",
              file=sys.stderr)
        return ReferencePolicy(), "REFERENCE"


def run_invariants(policy: Any, *, max_counterexamples: int = 3) -> dict[str, Any]:
    tasks = list(iter_tasks())
    profiles: list[ProfileSignal | None] = [None, *iter_profiles()]
    results = {
        key: {"statement": text, "checked": 0, "violations": 0, "counterexamples": []}
        for key, (text, _) in INVARIANTS.items()
    }
    checks = [(key, results[key], check) for key, (_, check) in INVARIANTS.items()]
    errors: list[dict[str, Any]] = []
    calls = 0
    routed_states = 0
    for task in tasks:
        for profile in profiles:
            calls += 1
            try:
                decision = policy.decide(task, profile)
            except Exception as exc:  # noqa: BLE001
                if len(errors) < max_counterexamples:
                    errors.append({"task": asdict(task),
                                   "profile": asdict(profile) if profile else None,
                                   "error": f"{type(exc).__name__}: {exc}"})
                continue
            if _routed(decision):
                routed_states += 1
            for _key, row, check in checks:
                row["checked"] += 1
                if not check(task, profile, decision):
                    row["violations"] += 1
                    if len(row["counterexamples"]) < max_counterexamples:
                        row["counterexamples"].append({
                            "task": asdict(task),
                            "profile": asdict(profile) if profile else None,
                            "decision": asdict(decision),
                        })
    for row in results.values():
        row["verdict"] = "PASS" if row["violations"] == 0 else "COUNTEREXAMPLE"
    clean = all(r["violations"] == 0 for r in results.values()) and not errors
    if routed_states == 0:
        verdict, note = "FAIL", VACUOUS_MESSAGE
    else:
        verdict, note = ("PASS" if clean else "COUNTEREXAMPLE"), None
    return {
        "decide_calls": calls,
        "task_states": len(tasks),
        "profile_states": len(profiles),
        "domain_sizes": {k: len(v) for k, v in DOMAIN.items()},
        "exhaustive": True,
        "policy_errors": errors,
        "invariants": results,
        # Positive control. Fourteen "never routes" invariants are all satisfied
        # by a policy that never routes at all, so the enumeration is only
        # evidence if the candidate demonstrably routes somewhere.
        "routed_states": routed_states,
        "positive_control": {
            "statement": "the candidate routes in at least one enumerated state",
            "verdict": "PASS" if routed_states else "FAIL",
            "message": note,
        },
        "verdict": verdict,
        "message": note,
        "boundary": ("Exhaustive over the declared domain: for this finite input space the "
                     "result is a proof, not a sample. It says nothing about answer quality."),
    }


# --------------------------------------------------------------------------- #
# models                                                                       #
# --------------------------------------------------------------------------- #

def run_models(config_path: Path | None, *, live: bool = False) -> dict[str, Any]:
    """Report the model pool without assuming any vendor.

    A missing config is a normal, reportable state: the invariant and power
    sections do not need a model at all.
    """
    try:
        import foil_models as fm
        import foil_setup as fs
    except ImportError as exc:  # pragma: no cover
        return {"verdict": "PASS", "configured": False,
                "reason": f"model layer unavailable: {exc}"}

    path = Path(config_path) if config_path else Path(fs.DEFAULT_CONFIG)
    if not path.is_file():
        return {
            "verdict": "PASS", "configured": False, "config": str(path),
            "reason": "no model configuration found",
            "next": "python tools/foil_setup.py init --auto  (then `add` your provider)",
            "note": ("The invariant and power sections need no model. Only the behavioural "
                     "arm does."),
        }
    config = fs.load_config(path)
    specs = fs.specs(config)
    providers = [fm.probe(spec, live=live) for spec in specs.values()]
    roles = config.get("roles", {})
    unfilled = [r for r in fs.ROLES if not roles.get(r)]
    needs_replicates = sorted(p["id"] for p in providers if p["requires_replicates"])
    ready = [p["id"] for p in providers if p["status"] == fm.ProviderStatus.READY.value]
    findings: list[str] = []
    if not roles.get("primary"):
        findings.append("no primary role assigned")
    if roles.get("primary") and roles["primary"] == roles.get("reviewer"):
        findings.append("primary and reviewer are the same model; critique is not independent")
    if unfilled:
        findings.append(f"unfilled roles: {unfilled} (report as NOT-MEASURED, do not substitute)")
    if needs_replicates:
        findings.append(f"models without seed control: {needs_replicates}; every benchmark cell "
                        f"using them requires replicates")
    if live and not ready:
        findings.append("no provider was live-verified")
    return {
        "verdict": "PASS", "configured": True, "config": str(path),
        "checked_live": live, "models": len(specs), "roles": roles,
        "providers": providers,
        "redacted_specs": [fm.redacted(spec) for spec in specs.values()],
        "replicates_forced_by": needs_replicates,
        "findings": findings,
        "boundary": ("Configured is not available and available is not used. Secrets are never "
                     "recorded: only the environment variable name and whether it is set."),
    }


# --------------------------------------------------------------------------- #
# power sizing                                                                 #
# --------------------------------------------------------------------------- #

def exact_two_sided(k: int, n: int) -> float:
    if n == 0:
        return 1.0
    point = comb(n, k) * 0.5 ** n
    return min(1.0, sum(comb(n, i) * 0.5 ** n for i in range(n + 1)
                        if comb(n, i) * 0.5 ** n <= point + 1e-15))


def mcnemar_power(n_items: int, p_disc: float, p_fav: float, reps: int = 1,
                  alpha: float = 0.05, sims: int = 20000, seed: int = 20260822) -> float:
    import random
    rng = random.Random(seed)
    hits = 0
    for _ in range(sims):
        nd = k = 0
        for _ in range(n_items):
            if rng.random() < p_disc:
                nd += 1
                wins = sum(1 for _ in range(reps) if rng.random() < p_fav)
                if wins * 2 > reps:
                    k += 1
                elif wins * 2 == reps and rng.random() < 0.5:
                    k += 1
        if nd and exact_two_sided(k, nd) < alpha:
            hits += 1
    return hits / sims


def run_power(target_power: float = 0.80, alpha: float = 0.05) -> dict[str, Any]:
    resolvability = {
        n: {"max_discordant": n, "best_two_sided_p": round(exact_two_sided(n, n), 5),
            "alpha_reachable": exact_two_sided(n, n) < alpha}
        for n in (5, 6, 10, 25)
    }
    grid, sizing = [], {}
    for p_disc, p_fav in ((0.20, 0.70), (0.30, 0.75), (0.30, 0.85)):
        for reps in (1, 3):
            row = {"p_discordant": p_disc, "p_favouring": p_fav, "replicates": reps, "power": {}}
            need = None
            for n in (5, 25, 50, 75, 100, 150, 200, 300):
                power = mcnemar_power(n, p_disc, p_fav, reps, alpha)
                row["power"][n] = round(power, 3)
                if need is None and power >= target_power:
                    need = n
            row["items_for_target_power"] = need
            grid.append(row)
            sizing[f"p_disc={p_disc},p_fav={p_fav},reps={reps}"] = need
    return {
        "alpha": alpha,
        "target_power": target_power,
        "resolvability": resolvability,
        "grid": grid,
        "items_for_target_power": sizing,
        "note": ("Six discordant pairs is the minimum at which a two-sided exact test can "
                 "reach alpha=0.05 at all. Replicates shrink per-item measurement noise and "
                 "roughly halve the items required."),
        "non_inferiority_warning": ("Published persona/profile results predict a null for the "
                                    "profile arm. A non-inferiority test against a stated harm "
                                    "margin needs more items than superiority, not fewer."),
    }


# --------------------------------------------------------------------------- #
# design manifest                                                              #
# --------------------------------------------------------------------------- #

def run_design(power_result: dict[str, Any] | None = None,
               model_result: dict[str, Any] | None = None) -> dict[str, Any]:
    sized = (power_result or {}).get("items_for_target_power", {})
    forced = (model_result or {}).get("replicates_forced_by") or []
    seeded_pool = bool(model_result and model_result.get("configured") and not forced)
    reps = 1 if seeded_pool else 3
    recommended = sized.get(f"p_disc=0.3,p_fav=0.75,reps={reps}")
    return {
        "schema": "foil-behavioural-arm-design/v1",
        "primary_endpoint": {
            "comparison": "VNEXT_NOPROFILE vs FOIL_GENERIC",
            "metric": "per-item pass rate across replicates",
            "test": "exact McNemar on replicate-majority item outcomes",
            "alpha": 0.05,
            "sided": "two",
            "rationale": ("One preregistered primary comparison. Every other contrast is "
                          "secondary and alpha-controlled by Holm."),
        },
        "secondary_endpoints": [
            {"comparison": "FOIL_GENERIC vs BASE", "family": "secondary"},
            {"comparison": "VNEXT_CORRECT_PROFILE vs VNEXT_NOPROFILE", "family": "secondary",
             "framing": "non-inferiority first, superiority only if non-inferiority holds"},
            {"comparison": "VNEXT_WRONG_PROFILE vs VNEXT_NOPROFILE", "family": "secondary",
             "framing": "non-inferiority against a preregistered harm margin"},
        ],
        "multiplicity": "Holm across the secondary family; primary is not adjusted.",
        "items": {
            "count": recommended,
            "selection_rule": ("Select for discriminability, not benchmark coverage: pilot each "
                               "candidate item under BASE with 5 replicates and keep items whose "
                               "pass rate lies in [0.2, 0.8]. Floored and ceilinged items carry "
                               "no information about the contrast."),
            "excluded_by_rule": ["items with BASE pass rate <0.2 or >0.8",
                                 "items whose benchmark reports sub-5% frontier accuracy",
                                 "items from a near-saturated benchmark subset"],
        },
        "replicates_per_cell": reps,
        "replicates_rationale": (
            "every configured model reports a seeded determinism class, so one sample per "
            "cell is defensible; verify the seed is actually honoured before relying on it"
            if seeded_pool else
            "at least one model in the pool has no seed control, so a single sample per cell "
            f"measures noise rather than effect (forced by: {forced or 'no model configured'})"),
        "model_pool": {
            "configured": bool(model_result and model_result.get("configured")),
            "roles": (model_result or {}).get("roles", {}),
            "requires_replicates": forced,
        },
        "model_agnostic": (
            "No condition in this design names a vendor. Conditions differ only in the policy "
            "text supplied. Record the resolved model id and decoding in every receipt so a "
            "result is attributable to a model without the design depending on one."),
        "blinding": {
            "condition_label_in_prompt": False,
            "mechanism": ("Deliver only the policy text. The harness holds the condition->policy "
                          "map; no unit prompt contains CONDITION= or the benchmark name."),
            "control_arm_instruction": ("None. Asking a control arm not to sandbag is unverifiable "
                                        "and is itself a treatment."),
            "placebo_arm": ("Include a length-matched, content-irrelevant scaffold arm so the "
                            "specific policy is separable from generic instruction volume."),
        },
        "ordering": {
            "rule": "randomise condition order within item; run an item's conditions adjacently",
            "reason": ("Condition-outer loops confound condition with elapsed time. For live-web "
                       "items the two arms otherwise query different web states."),
        },
        "gold_pinning": {
            "required_fields": ["dataset_revision", "as_of", "volatility_class", "scoring_mode"],
            "rule": ("Any dataset whose answers are maintained on a schedule must be pinned to a "
                     "revision and an as-of date, and its scoring mode preregistered where the "
                     "dataset defines more than one."),
        },
        "grading": {
            "graders": 2,
            "blind_to_condition": True,
            "agreement_statistic": "Cohen's kappa, reported with the result",
            "minimum_agreement": 0.80,
            "adjudication": "a third blinded grader resolves disagreements; log every adjudication",
        },
        "contamination": {
            "pre_run_checks": ["canary-string completion probe where the benchmark ships one",
                               "record the probe result in the receipt whether or not it fires"],
            "on_exposure": "mark the unit CONTAMINATED, keep the record, do not silently retry",
        },
        "receipt_required_fields": [
            "schema", "condition", "benchmark", "item_id", "replicate_index",
            "isolation_session_id", "model", "decoding", "final_answer",
            "prediction_sha256", "profile_payload_sha256", "dataset_revision", "as_of",
            "scoring_mode", "budget", "policy_trace", "timestamp", "status", "exclusion_reason",
        ],
        "failure_handling": {
            "rule": ("Preserve diagnostics on failure. Never delete the log or branch a failed "
                     "unit's error message points at; record status and continue so the matrix "
                     "stays auditable."),
        },
        "stop_rule": ("Preregister a group-sequential or anytime-valid boundary if you intend to "
                      "look at results before the full item set is complete. Unplanned peeking "
                      "invalidates the stated alpha."),
    }


# --------------------------------------------------------------------------- #
# selfcheck                                                                    #
# --------------------------------------------------------------------------- #

def run_selfcheck() -> dict[str, Any]:
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                          cwd=ROOT, capture_output=True, text=True)
    tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
    return {"returncode": proc.returncode,
            "verdict": "PASS" if proc.returncode == 0 else "FAIL",
            "summary": tail}


# --------------------------------------------------------------------------- #
# receipt                                                                      #
# --------------------------------------------------------------------------- #

def _digest(previous: str, payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(f"{previous}|{blob}".encode("utf-8")).hexdigest()


def build_receipt(sections: dict[str, Any], policy_source: str) -> dict[str, Any]:
    chain, previous = [], GENESIS
    for name, payload in sections.items():
        previous = _digest(previous, payload)
        chain.append({"section": name, "digest": previous})
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy_source": policy_source,
        "python": platform.python_version(),
        "gold_opened": False,
        "searches_issued": 0,
        "child_sessions_spawned": 0,
        "model_completions_issued": 0,
        "sections": sections,
        "chain": chain,
        "head": previous,
        "boundary": ("Invariant results are exhaustive over the declared domain and are a proof "
                     "for that domain. Power and design sections are calculations, not results. "
                     "Nothing here is evidence about answer quality."),
    }


def default_receipt_path() -> Path:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return ROOT / "benchmark_runs" / day / "foil_session_receipt.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOIL session benchmark")
    parser.add_argument("command",
                        choices=["invariants", "selfcheck", "models", "power", "design", "all"])
    parser.add_argument("--model-config", type=Path, default=None,
                        help="path to .foil/models.json; default is the setup tool's default")
    parser.add_argument("--live", action="store_true",
                        help="contact configured model endpoints when probing")
    parser.add_argument("--policy-module", default=DEFAULT_POLICY_MODULE,
                        help="module exposing the candidate policy (default: foil_policy)")
    parser.add_argument("--policy-class", default=DEFAULT_POLICY_CLASS)
    parser.add_argument("--allow-reference", action="store_true",
                        help="permit a ReferencePolicy fallback run to exit 0")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--target-power", type=float, default=0.80)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    policy, source = load_policy(args.policy_module, args.policy_class)
    sections: dict[str, Any] = {}
    if args.command in ("invariants", "all"):
        sections["invariants"] = run_invariants(policy)
    if args.command in ("selfcheck", "all"):
        sections["selfcheck"] = run_selfcheck()
    if args.command in ("power", "all"):
        sections["power"] = run_power(args.target_power)
    if args.command in ("models", "all"):
        sections["models"] = run_models(args.model_config, live=args.live)
    if args.command in ("design", "all"):
        sections["design"] = run_design(sections.get("power"), sections.get("models"))

    receipt = build_receipt(sections, source)
    out = args.out or (default_receipt_path() if args.command == "all" else None)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, default=str) + "\n",
                       encoding="utf-8")

    if not args.quiet:
        print(f"policy_source={source}  gold_opened=False  searches=0")
        inv = sections.get("invariants")
        if inv:
            print(f"\ninvariants: {inv['decide_calls']:,} decide() calls "
                  f"({inv['task_states']} task states x {inv['profile_states']} profile states) "
                  f"-> {inv['verdict']}")
            for key, row in inv["invariants"].items():
                mark = "ok  " if row["verdict"] == "PASS" else "FAIL"
                print(f"  {mark} {key} {row['statement']}"
                      + ("" if row["verdict"] == "PASS" else f"  ({row['violations']} violations)"))
                for example in row["counterexamples"]:
                    print(f"        witness: profile={example['profile']}")
                    print(f"                 task={example['task']}")
            control = inv["positive_control"]
            mark = "ok  " if control["verdict"] == "PASS" else "FAIL"
            print(f"  {mark} PC  routed_states={inv['routed_states']} "
                  f"({control['statement']})"
                  + (f"  -- {control['message']}" if control["message"] else ""))
        if "selfcheck" in sections:
            print(f"\nselfcheck: {sections['selfcheck']['verdict']} "
                  f"({'; '.join(sections['selfcheck']['summary'])})")
        if "models" in sections:
            block = sections["models"]
            if not block.get("configured"):
                print(f"\nmodels: none configured ({block.get('reason')})")
                if block.get("next"):
                    print(f"        {block['next']}")
            else:
                print(f"\nmodels: {block['models']} configured, roles={block.get('roles')}")
                for row in block["providers"]:
                    print(f"  {row['status']:<12} {row['id']:<16} {row['family']:<20} "
                          f"{row['determinism']}")
                for finding in block["findings"]:
                    print(f"  note: {finding}")
        if "power" in sections:
            print("\npower (two-sided exact McNemar, alpha=0.05):")
            for n, row in sections["power"]["resolvability"].items():
                print(f"  n={n:<4} best attainable p={row['best_two_sided_p']:.4f}  "
                      f"alpha reachable: {row['alpha_reachable']}")
            print("  items for 80% power:")
            for key, value in sections["power"]["items_for_target_power"].items():
                print(f"    {key:<38} -> {value if value else '>300'}")
        if "design" in sections:
            design = sections["design"]
            print(f"\ndesign: primary = {design['primary_endpoint']['comparison']}, "
                  f"items = {design['items']['count']}, "
                  f"replicates = {design['replicates_per_cell']}")
            print(f"        {design['replicates_rationale']}")
        if out:
            print(f"\nreceipt: {out}  head={receipt['head'][:16]}")

    failed = any(
        section.get("verdict") not in (None, "PASS")
        for section in sections.values()
        if isinstance(section, dict)
    )
    if source == "REFERENCE" and not args.allow_reference:
        print("\n[fail] policy_source=REFERENCE: the real candidate was not exercised. "
              "Fix the import or pass --allow-reference.", file=sys.stderr)
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
