"""Formal Reasoning runtime adapters and candidate-directed proof challenges.

A receipt verifies only the supplied formal encoding. The module never upgrades a
natural-language claim merely because a solver, enumerator, or symbolic normalizer
returned successfully. Native challenges are bound to candidate, scope, and
obligation-set hashes through the neutral challenge contract.
"""
from __future__ import annotations

import ast
import importlib.util
import itertools
import json
import operator
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from egrt_challenge import (
    ChallengePolicy,
    ChallengeSelectionError,
    record_resolution,
    select_minimum_discriminator,
)
from egrt_challenge_types import (
    ChallengeKind,
    ChallengeOrigin,
    ChallengeRequest,
    ChallengeResolution,
    ChallengeState,
    DiscriminatorPlan,
    ResolutionOutcome,
)
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import (
    ArtifactRef,
    EvidenceClass,
    EvidenceRef,
    Receipt,
    Verdict,
    digest,
    text_digest,
)


@dataclass(frozen=True)
class ProofObligation:
    obligation_id: str
    natural_claim: str
    formal_claim: str
    assumptions: tuple[str, ...] = ()
    domain: str = "deductive"
    encoding_artifact: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FormalizationCandidate:
    candidate_id: str
    obligation_id: str
    natural_claim_hash: str
    formal_claim: str
    assumptions: tuple[str, ...]
    quantifier_map: tuple[str, ...]
    representation: str
    producer: str
    candidate_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProofChallengeBundle:
    bundle_id: str
    obligation_id: str
    base_candidate_id: str
    alternate_candidate_ids: tuple[str, ...]
    challenge_ids: tuple[str, ...]
    selected_plan_ids: tuple[str, ...]
    task_id: str | None = None
    base_candidate_hash: str | None = None
    scope_hash: str | None = None
    obligation_set_hash: str | None = None
    natural_scope_receipt_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
MAX_EXPRESSION_CHARS = 2048
MAX_AST_NODES = 128
MAX_ABS_EXPONENT = 1000
MAX_SYMBOLIC_AST_NODES = 256
MAX_SYMBOLIC_EXPONENT = 32
MAX_ENUMERATION_CASES = 10_000


def _number(node: ast.AST) -> Fraction | int:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return Fraction(str(node.value)) if isinstance(node.value, float) else node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_number(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left, right = _number(node.left), _number(node.right)
        if isinstance(node.op, ast.Div):
            return Fraction(left) / Fraction(right)
        if isinstance(node.op, ast.Pow):
            exponent = right
            if isinstance(exponent, Fraction) and exponent.denominator != 1:
                raise ValueError("fractional exponents are outside exact arithmetic scope")
            exp_int = int(exponent)
            if abs(exp_int) > MAX_ABS_EXPONENT:
                raise ValueError("exponent exceeds exact-arithmetic resource bound")
            return left**exp_int
        return _BINOPS[type(node.op)](left, right)
    raise ValueError("expression contains unsupported syntax")


def exact_arithmetic(expression: str) -> str:
    if len(expression) > MAX_EXPRESSION_CHARS:
        raise ValueError("expression exceeds exact-arithmetic size bound")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise ValueError("expression exceeds exact-arithmetic AST bound")
    value = _number(tree.body)
    if isinstance(value, Fraction):
        return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    return str(value)


def tool_available(tool: str) -> bool:
    return shutil.which(tool) is not None


def _z3_version() -> str | None:
    if not tool_available("z3"):
        return None
    try:
        proc = subprocess.run(["z3", "-version"], text=True, capture_output=True, timeout=5, shell=False)
        return (proc.stdout or proc.stderr).strip()[:200] if proc.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def run_z3_smt2(path: Path, timeout: int = 20) -> dict[str, Any]:
    if not path.is_file():
        return {"verdict": Verdict.UNAVAILABLE.value, "reason": "SMT2 encoding file not found"}
    if not tool_available("z3"):
        return {"verdict": Verdict.UNAVAILABLE.value, "reason": "z3 executable not found"}
    try:
        proc = subprocess.run(["z3", str(path)], text=True, capture_output=True, timeout=timeout, shell=False)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return {
            "verdict": Verdict.UNKNOWN.value,
            "reason": "z3 timeout",
            "solver_status": "timeout",
            "stdout_hash": text_digest(stdout),
            "stderr_hash": text_digest(stderr),
            "tool_version": _z3_version(),
        }
    first = (proc.stdout.strip().splitlines() or [""])[0].strip().lower()
    if proc.returncode != 0:
        verdict = Verdict.ISSUE
    elif first in ("sat", "unsat"):
        verdict = Verdict.CLEARED
    else:
        verdict = Verdict.UNKNOWN
    return {
        "verdict": verdict.value,
        "solver_status": first or "unknown",
        "exit_code": proc.returncode,
        "stdout_hash": text_digest(proc.stdout),
        "stderr_hash": text_digest(proc.stderr),
        "tool_version": _z3_version(),
    }


def _task_id(obligation: ProofObligation) -> str | None:
    value = obligation.metadata.get("task_id")
    return str(value) if value else None


def arithmetic_receipt(root: Path, obligation: ProofObligation, expression: str) -> Receipt:
    store = RuntimeStore(root)
    try:
        result = exact_arithmetic(expression)
        verdict = Verdict.CLEARED
        unresolved: tuple[str, ...] = ()
    except Exception as exc:
        result = type(exc).__name__
        verdict = Verdict.ISSUE
        unresolved = (str(exc),)
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="mind",
        obligation_id=obligation.obligation_id,
        verdict=verdict,
        action="exact-arithmetic",
        input_hash=digest({"obligation_id": obligation.obligation_id, "formal_claim": obligation.formal_claim, "expression": expression}),
        output_hash=text_digest(result),
        evidence=(EvidenceRef(
            evidence_class=EvidenceClass.MEASURED,
            verifier="mind:exact_arithmetic",
            metadata={"scope": "exact evaluation of the supplied bounded arithmetic encoding"},
        ),),
        verifier="mind:exact_arithmetic",
        tool_version="stdlib-ast+fractions",
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=unresolved,
        notes=f"result={result}; this receipt supports the supplied encoding, not an unstated English generalization",
        task_id=_task_id(obligation),
    )
    store.write_receipt(receipt)
    return receipt


def smt_receipt(root: Path, obligation: ProofObligation, smt2_path: Path) -> Receipt:
    store = RuntimeStore(root)
    if smt2_path.is_file():
        encoding_text = smt2_path.read_text(encoding="utf-8", errors="replace")
        encoding_hash = text_digest(encoding_text)
    else:
        encoding_hash = digest({"missing": str(smt2_path)})
    result = run_z3_smt2(smt2_path)
    expected = str(obligation.metadata.get("expected_solver_status") or "unsat").lower()
    status = str(result.get("solver_status") or "unknown")
    if result.get("verdict") == Verdict.UNAVAILABLE.value:
        verdict = Verdict.UNAVAILABLE
    elif status in {"sat", "unsat"}:
        verdict = Verdict.CLEARED if status == expected else Verdict.ISSUE
    else:
        verdict = Verdict.UNKNOWN if result.get("verdict") != Verdict.ISSUE.value else Verdict.ISSUE
    evidence_class = EvidenceClass.PROVEN if verdict in {Verdict.CLEARED, Verdict.ISSUE} and status in {"sat", "unsat"} else EvidenceClass.OBSERVED
    counterexample_hash = result.get("stdout_hash") if status == "sat" and expected == "unsat" else None
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="mind",
        obligation_id=obligation.obligation_id,
        verdict=verdict,
        action="z3-smt2",
        input_hash=digest({
            "obligation_id": obligation.obligation_id,
            "candidate_hash": obligation.metadata.get("candidate_hash"),
            "scope_hash": obligation.metadata.get("scope_hash"),
            "encoding_sha256": encoding_hash,
            "expected_solver_status": expected,
            "negation_bound": bool(obligation.metadata.get("negation_bound", expected == "unsat")),
        }),
        output_hash=digest(result),
        evidence=(EvidenceRef(
            evidence_class=evidence_class,
            verifier="z3",
            artifact=ArtifactRef(f"hash:z3-output:{result.get('stdout_hash')}") if result.get("stdout_hash") else None,
            metadata={
                "solver_status": status,
                "expected_solver_status": expected,
                "scope": "formal SMT2 encoding only",
                "encoding_sha256": encoding_hash,
                "counterexample_hash": counterexample_hash,
            },
        ),),
        verifier="z3",
        tool_version=result.get("tool_version"),
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=() if verdict in {Verdict.CLEARED, Verdict.ISSUE} else (result.get("reason", "solver did not return the required conclusive status"),),
        notes=json.dumps({**result, "boundary": "solver status establishes a property of the supplied encoding only"}, sort_keys=True),
        task_id=_task_id(obligation),
    )
    store.write_receipt(receipt)
    return receipt


def _candidate_payload(
    obligation: ProofObligation,
    formal_claim: str,
    *,
    assumptions: tuple[str, ...],
    quantifier_map: tuple[str, ...],
    representation: str,
    producer: str,
) -> dict[str, Any]:
    return {
        "obligation_id": obligation.obligation_id,
        "natural_claim_hash": text_digest(obligation.natural_claim),
        "formal_claim": formal_claim,
        "assumptions": assumptions,
        "quantifier_map": quantifier_map,
        "representation": representation,
        "producer": producer,
    }


def _formalization_candidate(
    obligation: ProofObligation,
    formal_claim: str,
    *,
    assumptions: Sequence[str] | None = None,
    quantifier_map: Sequence[str] | None = None,
    representation: str | None = None,
    producer: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> FormalizationCandidate:
    assumptions_tuple = tuple(str(item) for item in (assumptions if assumptions is not None else obligation.assumptions))
    quantifiers = tuple(str(item) for item in (quantifier_map or ()))
    representation_value = representation or obligation.domain or "deductive"
    producer_value = producer or "mind:native-formalizer"
    payload = _candidate_payload(
        obligation,
        formal_claim,
        assumptions=assumptions_tuple,
        quantifier_map=quantifiers,
        representation=representation_value,
        producer=producer_value,
    )
    candidate_hash = digest(payload)
    return FormalizationCandidate(
        candidate_id=f"fcand-{candidate_hash[:16]}",
        obligation_id=obligation.obligation_id,
        natural_claim_hash=payload["natural_claim_hash"],
        formal_claim=formal_claim,
        assumptions=assumptions_tuple,
        quantifier_map=quantifiers,
        representation=representation_value,
        producer=producer_value,
        candidate_hash=candidate_hash,
        metadata=dict(metadata or {}),
    )


def propose_formalizations(obligation: ProofObligation) -> tuple[FormalizationCandidate, ...]:
    """Construct explicit candidates from supplied encodings; never invent hidden scope."""
    candidates: list[FormalizationCandidate] = []
    if obligation.formal_claim.strip():
        candidates.append(_formalization_candidate(
            obligation,
            obligation.formal_claim.strip(),
            quantifier_map=tuple(obligation.metadata.get("quantifier_map") or ()),
            representation=str(obligation.metadata.get("representation") or obligation.domain),
            producer=str(obligation.metadata.get("producer") or "mind:native-formalizer"),
        ))
    alternates = obligation.metadata.get("alternate_formalizations") or ()
    if not isinstance(alternates, Sequence) or isinstance(alternates, (str, bytes)):
        raise TypeError("alternate_formalizations must be a sequence")
    for alternate in alternates:
        if isinstance(alternate, str):
            row: Mapping[str, Any] = {"formal_claim": alternate}
        elif isinstance(alternate, Mapping):
            row = alternate
        else:
            raise TypeError("each alternate formalization must be str or mapping")
        formal_claim = str(row.get("formal_claim") or "").strip()
        if not formal_claim:
            raise ValueError("alternate formalization requires formal_claim")
        candidates.append(_formalization_candidate(
            obligation,
            formal_claim,
            assumptions=tuple(row.get("assumptions") or obligation.assumptions),
            quantifier_map=tuple(row.get("quantifier_map") or ()),
            representation=str(row.get("representation") or obligation.domain),
            producer=str(row.get("producer") or "mind:native-formalizer"),
            metadata={key: value for key, value in row.items() if key not in {"formal_claim", "assumptions", "quantifier_map", "representation", "producer"}},
        ))
    unique: dict[str, FormalizationCandidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.candidate_hash, candidate)
    return tuple(unique.values())


def _challenge_id(kind: ChallengeKind, base: FormalizationCandidate, refuter: str, alternative_hash: str | None = None) -> str:
    return f"chal-{digest({'kind': kind.value, 'candidate': base.candidate_hash, 'refuter': refuter, 'alternative': alternative_hash})[:16]}"


def generate_native_challenges(
    base: FormalizationCandidate,
    alternates: Sequence[FormalizationCandidate],
    *,
    task_id: str | None = None,
    scope_hash: str | None = None,
    obligation_set_hash: str | None = None,
    proposer: str = "mind:native-challenge",
) -> tuple[ChallengeRequest, ...]:
    """Generate candidate-bound alternate-formalization and counterexample challenges."""
    task = task_id or f"task-{base.obligation_id}"
    scope = scope_hash or digest({
        "natural_claim_hash": base.natural_claim_hash,
        "assumptions": base.assumptions,
        "quantifier_map": base.quantifier_map,
    })
    obligation_set = obligation_set_hash or digest({"obligation_id": base.obligation_id})
    requests: list[ChallengeRequest] = []
    for alternate in alternates:
        if alternate.obligation_id != base.obligation_id:
            raise ValueError("alternate candidate obligation mismatch")
        if alternate.candidate_hash == base.candidate_hash:
            continue
        refuter = "exact equivalence or a claim-native evaluation that distinguishes the encodings"
        requests.append(ChallengeRequest(
            challenge_id=_challenge_id(ChallengeKind.ALTERNATE_FORMALIZATION, base, refuter, alternate.candidate_hash),
            task_id=task,
            obligation_id=base.obligation_id,
            target_module="mind",
            origin=ChallengeOrigin.MODULE_NATIVE,
            kind=ChallengeKind.ALTERNATE_FORMALIZATION,
            hypothesis="A plausible alternate formalization changes the proposition or answer.",
            alternative=alternate.formal_claim,
            refuter=refuter,
            consequence_if_true="The base encoding cannot warrant the natural-language claim.",
            load_bearing=True,
            required_capability="SYMBOLIC_EQUIVALENCE",
            candidate_hash=base.candidate_hash,
            scope_hash=scope,
            obligation_set_hash=obligation_set,
            proposer=proposer,
            proposer_provenance=base.producer,
            information_rank=3,
            risk_rank=3,
            cost_rank=1,
            metadata={"alternate_candidate_id": alternate.candidate_id, "alternate_candidate_hash": alternate.candidate_hash},
        ))
    refuter = "a verified witness in the declared domain or an unsatisfied negated encoding"
    requests.append(ChallengeRequest(
        challenge_id=_challenge_id(ChallengeKind.COUNTEREXAMPLE, base, refuter),
        task_id=task,
        obligation_id=base.obligation_id,
        target_module="mind",
        origin=ChallengeOrigin.MODULE_NATIVE,
        kind=ChallengeKind.COUNTEREXAMPLE,
        hypothesis="The base formalization fails on a declared edge case or domain witness.",
        alternative=f"not ({base.formal_claim})",
        refuter=refuter,
        consequence_if_true="The universal or load-bearing formal claim is false.",
        load_bearing=True,
        required_capability="FINITE_ENUMERATION_OR_SMT",
        candidate_hash=base.candidate_hash,
        scope_hash=scope,
        obligation_set_hash=obligation_set,
        proposer=proposer,
        proposer_provenance=base.producer,
        information_rank=3,
        risk_rank=3,
        cost_rank=2,
        metadata={"base_candidate_id": base.candidate_id},
    ))
    return tuple(requests)


def _capability_available(capabilities: Mapping[str, bool] | Iterable[str], name: str) -> bool:
    if isinstance(capabilities, Mapping):
        return bool(capabilities.get(name) or capabilities.get(name.lower()))
    values = {str(value).upper() for value in capabilities}
    return name.upper() in values


def _plan_for_challenge(
    challenge: ChallengeRequest,
    capabilities: Mapping[str, bool] | Iterable[str],
) -> list[DiscriminatorPlan]:
    plans: list[DiscriminatorPlan] = []
    if challenge.kind in {ChallengeKind.ALTERNATE_FORMALIZATION, ChallengeKind.REPRESENTATION_SWAP}:
        plans.append(DiscriminatorPlan(
            plan_id=f"plan-sym-{challenge.challenge_id[-12:]}",
            challenge_id=challenge.challenge_id,
            mode="symbolic-equivalence",
            action="compare base and alternate formal encodings exactly",
            verifier_module="mind",
            required_capability="SYMBOLIC_EQUIVALENCE",
            expected_support_signal="normalized residual is exactly zero",
            expected_refute_signal="a non-zero exact residual or distinguishing witness",
            timeout_seconds=20,
            max_cost_rank=1,
            metadata={
                "capability_available": _capability_available(capabilities, "SYMBOLIC_EQUIVALENCE"),
                "discrimination_rank": 3,
                "information_rank": 3,
                "risk_reduction_rank": 3,
                "irreversibility_rank": 0,
            },
        ))
    if challenge.kind in {ChallengeKind.COUNTEREXAMPLE, ChallengeKind.CLAIM_NEGATION}:
        plans.append(DiscriminatorPlan(
            plan_id=f"plan-enum-{challenge.challenge_id[-12:]}",
            challenge_id=challenge.challenge_id,
            mode="exact-enumeration",
            action="enumerate the declared finite domain and search for a witness",
            verifier_module="mind",
            required_capability="FINITE_ENUMERATION",
            expected_support_signal="all declared cases satisfy the predicate",
            expected_refute_signal="a verified counterexample witness is produced",
            timeout_seconds=20,
            max_cost_rank=2,
            metadata={
                "capability_available": _capability_available(capabilities, "FINITE_ENUMERATION"),
                "discrimination_rank": 3,
                "information_rank": 3,
                "risk_reduction_rank": 3,
                "irreversibility_rank": 0,
            },
        ))
        plans.append(DiscriminatorPlan(
            plan_id=f"plan-smt-{challenge.challenge_id[-12:]}",
            challenge_id=challenge.challenge_id,
            mode="smt-negation",
            action="check satisfiability of assumptions and claim negation",
            verifier_module="mind",
            required_capability="SMT",
            expected_support_signal="negated claim is unsatisfiable",
            expected_refute_signal="solver returns a satisfying witness",
            timeout_seconds=20,
            max_cost_rank=2,
            metadata={
                "capability_available": _capability_available(capabilities, "SMT"),
                "discrimination_rank": 3,
                "information_rank": 3,
                "risk_reduction_rank": 3,
                "irreversibility_rank": 0,
            },
        ))
    return plans


def select_proof_discriminator(
    challenges: Sequence[ChallengeRequest],
    capabilities: Mapping[str, bool] | Iterable[str],
    *,
    root: Path | None = None,
    policy: ChallengePolicy | None = None,
) -> DiscriminatorPlan:
    """Select the weakest load-bearing proof hinge and its minimum available check."""
    if not challenges:
        raise ChallengeSelectionError("no proof challenges supplied")
    ordered = sorted(
        challenges,
        key=lambda item: (
            not item.load_bearing,
            -(item.risk_rank or 0),
            -(item.information_rank or 0),
            item.cost_rank if item.cost_rank is not None else 10**9,
            item.challenge_id,
        ),
    )
    challenge = ordered[0]
    plans = _plan_for_challenge(challenge, capabilities)
    if not plans:
        raise ChallengeSelectionError("no claim-native discriminator for challenge kind")
    if root is not None:
        return select_minimum_discriminator(
            root,
            challenge.challenge_id,
            plans,
            policy=policy or ChallengePolicy.from_root(root),
        )
    available = [plan for plan in plans if plan.metadata.get("capability_available")]
    if available:
        available.sort(key=lambda item: (item.max_cost_rank if item.max_cost_rank is not None else 10**9, item.plan_id))
        return available[0]
    plans.sort(key=lambda item: (item.max_cost_rank if item.max_cost_rank is not None else 10**9, item.plan_id))
    return plans[0]


# --- Exact symbolic equivalence for a bounded expression fragment -----------------
Monomial = tuple[tuple[str, int], ...]
Polynomial = dict[Monomial, Fraction]


def _mono(items: Mapping[str, int]) -> Monomial:
    return tuple(sorted((name, power) for name, power in items.items() if power))


def _poly_clean(poly: Polynomial) -> Polynomial:
    return {monomial: coefficient for monomial, coefficient in poly.items() if coefficient}


def _poly_add(left: Polynomial, right: Polynomial, scale: Fraction = Fraction(1)) -> Polynomial:
    out = dict(left)
    for monomial, coefficient in right.items():
        out[monomial] = out.get(monomial, Fraction(0)) + scale * coefficient
    return _poly_clean(out)


def _poly_mul(left: Polynomial, right: Polynomial) -> Polynomial:
    out: Polynomial = {}
    for lm, lc in left.items():
        left_map = dict(lm)
        for rm, rc in right.items():
            powers = dict(left_map)
            for name, power in rm:
                powers[name] = powers.get(name, 0) + power
            monomial = _mono(powers)
            out[monomial] = out.get(monomial, Fraction(0)) + lc * rc
    return _poly_clean(out)


def _poly_pow(poly: Polynomial, exponent: int) -> Polynomial:
    if exponent < 0 or exponent > MAX_SYMBOLIC_EXPONENT:
        raise ValueError("symbolic exponent outside supported bound")
    result: Polynomial = {(): Fraction(1)}
    base = poly
    value = exponent
    while value:
        if value & 1:
            result = _poly_mul(result, base)
        value >>= 1
        if value:
            base = _poly_mul(base, base)
    return result


def _symbolic_atom(name: str) -> Polynomial:
    return {((name, 1),): Fraction(1)}


def _canonical_arg(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def _symbolic_poly(node: ast.AST) -> Polynomial:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return {(): Fraction(str(node.value))}
    if isinstance(node, ast.Name):
        if node.id.startswith("_"):
            raise ValueError("private names are not allowed")
        return _symbolic_atom(f"var:{node.id}")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _symbolic_poly(node.operand)
        return value if isinstance(node.op, ast.UAdd) else {m: -c for m, c in value.items()}
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            return _poly_add(_symbolic_poly(node.left), _symbolic_poly(node.right))
        if isinstance(node.op, ast.Sub):
            return _poly_add(_symbolic_poly(node.left), _symbolic_poly(node.right), Fraction(-1))
        if isinstance(node.op, ast.Mult):
            return _poly_mul(_symbolic_poly(node.left), _symbolic_poly(node.right))
        if isinstance(node.op, ast.Div):
            denominator = _symbolic_poly(node.right)
            if set(denominator) != {()} or denominator[()] == 0:
                raise ValueError("only division by a non-zero exact constant is supported")
            return {m: c / denominator[()] for m, c in _symbolic_poly(node.left).items()}
        if isinstance(node.op, ast.Pow):
            exponent = _number(node.right)
            if isinstance(exponent, Fraction) and exponent.denominator != 1:
                raise ValueError("fractional symbolic exponents are unsupported")
            return _poly_pow(_symbolic_poly(node.left), int(exponent))
        raise ValueError("unsupported symbolic operator")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in {"sin", "cos"}:
            raise ValueError("only sin() and cos() calls are supported by the built-in exact normalizer")
        if len(node.args) != 1 or node.keywords:
            raise ValueError("sin() and cos() require one positional argument")
        arg = _canonical_arg(node.args[0])
        return _symbolic_atom(f"{node.func.id}:{arg}")
    raise ValueError("expression is outside the built-in symbolic fragment")


def _reduce_trig(poly: Polynomial) -> Polynomial:
    """Canonical reduction modulo sin(x)^2 + cos(x)^2 - 1 for each argument."""
    pending = list(poly.items())
    out: Polynomial = {}
    while pending:
        monomial, coefficient = pending.pop()
        powers = dict(monomial)
        reducible = next((name for name, power in powers.items() if name.startswith("sin:") and power >= 2), None)
        if reducible is None:
            out[monomial] = out.get(monomial, Fraction(0)) + coefficient
            continue
        arg = reducible[4:]
        cos_name = f"cos:{arg}"
        powers[reducible] -= 2
        base = _mono(powers)
        pending.append((base, coefficient))
        powers[cos_name] = powers.get(cos_name, 0) + 2
        pending.append((_mono(powers), -coefficient))
    return _poly_clean(out)




def _stable_value(value: Any) -> Any:
    """Convert bounded verifier inputs to deterministic JSON-safe metadata."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Fraction):
        return {"fraction": [value.numerator, value.denominator]}
    if isinstance(value, range):
        return {"range": [value.start, value.stop, value.step]}
    if isinstance(value, Mapping):
        return {str(key): _stable_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_stable_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_stable_value(item) for item in value), key=repr)
    return {"type": f"{type(value).__module__}.{type(value).__qualname__}", "repr": repr(value)}


def _polynomial_payload(poly: Polynomial) -> list[dict[str, Any]]:
    return [
        {
            "monomial": [[name, power] for name, power in monomial],
            "coefficient": [coefficient.numerator, coefficient.denominator],
        }
        for monomial, coefficient in sorted(poly.items())
    ]

def _relation_normal_form(node: ast.AST) -> tuple[str, Polynomial]:
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise ValueError("chained comparisons are outside the built-in symbolic fragment")
        left = _symbolic_poly(node.left)
        right = _symbolic_poly(node.comparators[0])
        op = node.ops[0]
        if isinstance(op, ast.GtE):
            return "ge", _poly_add(left, right, Fraction(-1))
        if isinstance(op, ast.LtE):
            return "ge", _poly_add(right, left, Fraction(-1))
        if isinstance(op, ast.Gt):
            return "gt", _poly_add(left, right, Fraction(-1))
        if isinstance(op, ast.Lt):
            return "gt", _poly_add(right, left, Fraction(-1))
        if isinstance(op, ast.Eq):
            return "eq", _poly_add(left, right, Fraction(-1))
        if isinstance(op, ast.NotEq):
            return "ne", _poly_add(left, right, Fraction(-1))
        raise ValueError("unsupported comparison operator")
    return "expr", _symbolic_poly(node)


def _built_in_equivalence(left: str, right: str) -> tuple[bool, str]:
    if max(len(left), len(right)) > MAX_EXPRESSION_CHARS:
        raise ValueError("symbolic expression exceeds size bound")
    left_tree = ast.parse(left, mode="eval")
    right_tree = ast.parse(right, mode="eval")
    if sum(1 for _ in ast.walk(left_tree)) + sum(1 for _ in ast.walk(right_tree)) > MAX_SYMBOLIC_AST_NODES:
        raise ValueError("symbolic expression exceeds AST bound")
    left_kind, left_poly = _relation_normal_form(left_tree.body)
    right_kind, right_poly = _relation_normal_form(right_tree.body)
    residual = _reduce_trig(_poly_add(left_poly, right_poly, Fraction(-1)))
    equivalent = left_kind == right_kind and not residual
    return equivalent, digest({"left_kind": left_kind, "right_kind": right_kind, "residual": _polynomial_payload(residual)})


def _sympy_available() -> bool:
    return importlib.util.find_spec("sympy") is not None


def _sympy_equivalence(left: str, right: str, assumptions: Sequence[str], timeout_seconds: int) -> tuple[str, str]:
    script = r'''
import ast, json, sys
import sympy as s
payload = json.loads(sys.stdin.read())
allowed_calls = {"sin": s.sin, "cos": s.cos, "sqrt": s.sqrt, "exp": s.exp, "log": s.log}
def parse(text):
    tree = ast.parse(text, mode="eval")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
               ast.UAdd, ast.USub, ast.Constant, ast.Name, ast.Load, ast.Call)
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise ValueError("unsupported syntax")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ValueError("private name")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in allowed_calls):
            raise ValueError("unsupported call")
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} - set(allowed_calls)
    local = {name: s.Symbol(name) for name in names}
    local.update(allowed_calls)
    return s.sympify(text, locals=local, evaluate=True)
residual = s.simplify(parse(payload["left"]) - parse(payload["right"]))
print(json.dumps({"equivalent": bool(residual == 0), "residual_hash": __import__("hashlib").sha256(s.srepr(residual).encode()).hexdigest()}))
'''
    try:
        process = subprocess.run(
            [sys.executable, "-c", script],
            input=json.dumps({"left": left, "right": right, "assumptions": list(assumptions)}),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return "timeout", digest({"timeout": timeout_seconds})
    if process.returncode != 0:
        return "error", text_digest(process.stderr)
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError:
        return "error", text_digest(process.stdout)
    return ("equivalent" if result.get("equivalent") else "different"), str(result.get("residual_hash"))


def symbolic_equivalence_receipt(
    root: Path,
    obligation: ProofObligation,
    left: str,
    right: str,
    assumptions: Sequence[str] = (),
    *,
    timeout_seconds: int = 20,
) -> Receipt:
    started = utcnow()
    engine = "stdlib-exact-symbolic"
    try:
        equivalent, residual_hash = _built_in_equivalence(left, right)
        status = "equivalent" if equivalent else "different"
    except (SyntaxError, ValueError) as built_in_error:
        if not _sympy_available():
            status = "unavailable"
            residual_hash = digest({"reason": str(built_in_error)})
            engine = "sympy-unavailable"
        else:
            status, residual_hash = _sympy_equivalence(left, right, assumptions, timeout_seconds)
            engine = "sympy-subprocess"
    if status == "equivalent":
        verdict = Verdict.CLEARED
        evidence_class = EvidenceClass.PROVEN
        unresolved: tuple[str, ...] = ()
    elif status == "different":
        verdict = Verdict.ISSUE
        evidence_class = EvidenceClass.PROVEN
        unresolved = ("formal expressions are not equivalent in the supported exact scope",)
    elif status == "unavailable":
        verdict = Verdict.UNAVAILABLE
        evidence_class = EvidenceClass.OBSERVED
        unresolved = ("required symbolic capability is unavailable for this expression fragment",)
    else:
        verdict = Verdict.UNKNOWN
        evidence_class = EvidenceClass.OBSERVED
        unresolved = (f"symbolic verifier returned {status}",)
    result = {
        "status": status,
        "residual_hash": residual_hash,
        "engine": engine,
        "assumptions_hash": digest(tuple(assumptions)),
    }
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="mind",
        obligation_id=obligation.obligation_id,
        verdict=verdict,
        action="symbolic-equivalence",
        input_hash=digest({
            "obligation_id": obligation.obligation_id,
            "candidate_hash": obligation.metadata.get("candidate_hash"),
            "scope_hash": obligation.metadata.get("scope_hash"),
            "left": left,
            "right": right,
            "assumptions": tuple(assumptions),
        }),
        output_hash=digest(result),
        evidence=(EvidenceRef(
            evidence_class=evidence_class,
            verifier=f"mind:{engine}",
            metadata={
                "scope": "exact equivalence of the supplied formal expressions only",
                "status": status,
                "residual_hash": residual_hash,
                "assumptions": tuple(assumptions),
            },
        ),),
        verifier=f"mind:{engine}",
        tool_version="egrt.challenge.v1",
        started_at=started,
        finished_at=utcnow(),
        unresolved=unresolved,
        notes=json.dumps(result, sort_keys=True),
        task_id=_task_id(obligation),
    )
    RuntimeStore(root).write_receipt(receipt)
    return receipt


def _predicate_hash(predicate: Callable[..., bool]) -> str:
    code = getattr(predicate, "__code__", None)
    if code is None:
        return digest({"callable": type(predicate).__qualname__, "repr": repr(predicate)})
    return digest({
        "module": getattr(predicate, "__module__", None),
        "qualname": getattr(predicate, "__qualname__", None),
        "bytecode": code.co_code.hex(),
        "constants": tuple(repr(item) for item in code.co_consts),
        "names": code.co_names,
    })


def _enumeration_cases(domain_spec: Any) -> tuple[Iterable[Any], int | None, str]:
    if isinstance(domain_spec, Mapping):
        names = tuple(str(name) for name in domain_spec)
        values = [tuple(domain_spec[name]) for name in domain_spec]
        total = 1
        for value in values:
            total *= len(value)
        return (
            ({name: item for name, item in zip(names, combination, strict=True)} for combination in itertools.product(*values)),
            total,
            "cartesian-mapping",
        )
    if isinstance(domain_spec, Sequence) and not isinstance(domain_spec, (str, bytes)):
        return iter(domain_spec), len(domain_spec), "declared-sequence"
    if isinstance(domain_spec, Iterable) and not isinstance(domain_spec, (str, bytes)):
        return iter(domain_spec), None, "declared-iterable"
    raise TypeError("domain_spec must be a mapping or finite iterable")


def _call_predicate(predicate: Callable[..., bool], case: Any) -> bool:
    if isinstance(case, Mapping):
        try:
            result = predicate(**case)
        except TypeError:
            result = predicate(case)
    elif isinstance(case, tuple):
        try:
            result = predicate(*case)
        except TypeError:
            result = predicate(case)
    else:
        result = predicate(case)
    if not isinstance(result, bool):
        raise TypeError("predicate must return bool")
    return result


def exact_enumeration_receipt(
    root: Path,
    obligation: ProofObligation,
    domain_spec: Any,
    predicate: Callable[..., bool],
    *,
    max_cases: int = MAX_ENUMERATION_CASES,
) -> Receipt:
    started = utcnow()
    if not callable(predicate):
        raise TypeError("predicate must be callable")
    cases, declared_size, domain_kind = _enumeration_cases(domain_spec)
    code_hash = _predicate_hash(predicate)
    checked = 0
    witness: Any | None = None
    failure: str | None = None
    exhausted = False
    if declared_size is not None and declared_size > max_cases:
        failure = f"declared domain size {declared_size} exceeds bound {max_cases}"
    else:
        try:
            for case in cases:
                if checked >= max_cases:
                    failure = f"enumeration exceeded bound {max_cases} before exhaustion"
                    break
                checked += 1
                if not _call_predicate(predicate, case):
                    witness = case
                    break
            else:
                exhausted = True
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
    if witness is not None:
        verdict = Verdict.ISSUE
        evidence_class = EvidenceClass.PROVEN
        unresolved = ("verified finite-domain counterexample",)
        status = "COUNTEREXAMPLE"
    elif exhausted:
        verdict = Verdict.CLEARED
        evidence_class = EvidenceClass.PROVEN
        unresolved = ()
        status = "EXHAUSTED_DECLARED_DOMAIN"
    elif failure and "exceeds bound" in failure:
        verdict = Verdict.UNAVAILABLE
        evidence_class = EvidenceClass.OBSERVED
        unresolved = (failure,)
        status = "RESOURCE_BOUND"
    else:
        verdict = Verdict.UNKNOWN
        evidence_class = EvidenceClass.OBSERVED
        unresolved = (failure or "enumeration incomplete",)
        status = "INCOMPLETE"
    witness_hash = digest(_stable_value(witness)) if witness is not None else None
    result = {
        "status": status,
        "checked": checked,
        "declared_size": declared_size,
        "domain_kind": domain_kind,
        "predicate_code_hash": code_hash,
        "witness_hash": witness_hash,
        "complete": exhausted,
    }
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="mind",
        obligation_id=obligation.obligation_id,
        verdict=verdict,
        action="exact-enumeration",
        input_hash=digest({
            "obligation_id": obligation.obligation_id,
            "candidate_hash": obligation.metadata.get("candidate_hash"),
            "scope_hash": obligation.metadata.get("scope_hash"),
            "domain_spec_hash": digest(_stable_value(domain_spec)),
            "predicate_code_hash": code_hash,
            "max_cases": max_cases,
        }),
        output_hash=digest(result),
        evidence=(EvidenceRef(
            evidence_class=evidence_class,
            artifact=ArtifactRef(f"hash:counterexample:{witness_hash}") if witness_hash else None,
            verifier="mind:exact_enumeration",
            metadata={
                "scope": "complete declared finite domain only" if exhausted else "bounded declared finite-domain search",
                **result,
            },
        ),),
        verifier="mind:exact_enumeration",
        tool_version="stdlib-itertools+callable-code-hash",
        started_at=started,
        finished_at=utcnow(),
        unresolved=unresolved,
        notes=json.dumps(result, sort_keys=True),
        task_id=_task_id(obligation),
    )
    RuntimeStore(root).write_receipt(receipt)
    return receipt


def counterexample_receipt(
    root: Path,
    obligation: ProofObligation,
    candidate: FormalizationCandidate,
    witness: Any,
    *,
    validator: Callable[[Any], bool] | None = None,
) -> Receipt:
    """Verify a supplied witness; an unverified model assertion remains UNKNOWN."""
    verifier = validator or candidate.metadata.get("witness_validator")
    started = utcnow()
    witness_hash = digest(_stable_value(witness))
    if not callable(verifier):
        verdict = Verdict.UNKNOWN
        status = "UNVERIFIED_WITNESS"
        evidence_class = EvidenceClass.HEURISTIC
        unresolved = ("no claim-native witness validator supplied",)
        code_hash = None
    else:
        code_hash = _predicate_hash(verifier)
        try:
            is_counterexample = verifier(witness)
            if not isinstance(is_counterexample, bool):
                raise TypeError("witness validator must return bool")
        except Exception as exc:
            verdict = Verdict.UNKNOWN
            status = "VALIDATOR_ERROR"
            evidence_class = EvidenceClass.OBSERVED
            unresolved = (f"{type(exc).__name__}: {exc}",)
        else:
            verdict = Verdict.ISSUE if is_counterexample else Verdict.CLEARED
            status = "COUNTEREXAMPLE" if is_counterexample else "WITNESS_DOES_NOT_REFUTE"
            evidence_class = EvidenceClass.PROVEN
            unresolved = ("verified counterexample",) if is_counterexample else ()
    result = {"status": status, "witness_hash": witness_hash, "validator_code_hash": code_hash}
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="mind",
        obligation_id=obligation.obligation_id,
        verdict=verdict,
        action="counterexample-check",
        input_hash=digest({
            "obligation_id": obligation.obligation_id,
            "candidate_hash": candidate.candidate_hash,
            "witness_hash": witness_hash,
            "validator_code_hash": code_hash,
        }),
        output_hash=digest(result),
        evidence=(EvidenceRef(
            evidence_class=evidence_class,
            artifact=ArtifactRef(f"hash:counterexample:{witness_hash}"),
            verifier="mind:counterexample_validator" if callable(verifier) else "mind:model-only",
            metadata={"scope": "supplied formal candidate and witness only", **result},
        ),),
        verifier="mind:counterexample_validator" if callable(verifier) else "mind:model-only",
        tool_version="callable-code-hash",
        started_at=started,
        finished_at=utcnow(),
        unresolved=unresolved,
        notes=json.dumps(result, sort_keys=True),
        task_id=_task_id(obligation),
    )
    RuntimeStore(root).write_receipt(receipt)
    return receipt


def resolve_proof_challenge(
    root: Path,
    challenge: ChallengeRequest,
    receipt: Receipt,
    *,
    resolver: str = "mind:challenge-resolution",
    resolver_provenance: str | None = None,
) -> ChallengeResolution:
    """Create and store a neutral resolution from a bound Mind verifier receipt."""
    if receipt.module != "mind" or receipt.obligation_id != challenge.obligation_id:
        raise ValueError("receipt is not a claim-native Mind receipt for this obligation")
    if receipt.verdict is Verdict.CLEARED:
        outcome = ResolutionOutcome.SUPPORTS_BASE
    elif receipt.verdict is Verdict.ISSUE:
        outcome = ResolutionOutcome.REFUTES_BASE
    elif receipt.verdict is Verdict.UNAVAILABLE:
        resolution = ChallengeResolution(
            resolution_id=new_id("cres"),
            challenge_id=challenge.challenge_id,
            state=ChallengeState.UNAVAILABLE,
            outcome=ResolutionOutcome.INCONCLUSIVE,
            verifier_receipt_id=receipt.receipt_id,
            verifier_module=receipt.module,
            evidence_hash=RuntimeStore(root).read_receipt(receipt.receipt_id).get("content_hash"),
            candidate_hash=challenge.candidate_hash,
            scope_hash=challenge.scope_hash,
            obligation_set_hash=challenge.obligation_set_hash,
            resolver=resolver,
            resolver_provenance=resolver_provenance,
            reason="mandatory claim-native verifier unavailable",
        )
        record_resolution(root, resolution)
        return resolution
    else:
        resolution = ChallengeResolution(
            resolution_id=new_id("cres"),
            challenge_id=challenge.challenge_id,
            state=ChallengeState.UNRESOLVED,
            outcome=ResolutionOutcome.INCONCLUSIVE,
            verifier_receipt_id=receipt.receipt_id,
            verifier_module=receipt.module,
            evidence_hash=RuntimeStore(root).read_receipt(receipt.receipt_id).get("content_hash"),
            candidate_hash=challenge.candidate_hash,
            scope_hash=challenge.scope_hash,
            obligation_set_hash=challenge.obligation_set_hash,
            resolver=resolver,
            resolver_provenance=resolver_provenance,
            reason="claim-native verifier inconclusive",
        )
        record_resolution(root, resolution)
        return resolution
    stored = RuntimeStore(root).read_receipt(receipt.receipt_id)
    if stored is None:
        raise ValueError("receipt must be stored before challenge resolution")
    resolution = ChallengeResolution(
        resolution_id=new_id("cres"),
        challenge_id=challenge.challenge_id,
        state=ChallengeState.RESOLVED,
        outcome=outcome,
        verifier_receipt_id=receipt.receipt_id,
        verifier_module=receipt.module,
        evidence_hash=stored["content_hash"],
        candidate_hash=challenge.candidate_hash,
        scope_hash=challenge.scope_hash,
        obligation_set_hash=challenge.obligation_set_hash,
        resolver=resolver,
        resolver_provenance=resolver_provenance,
        reason="bound claim-native Mind verifier receipt",
    )
    record_resolution(root, resolution)
    return resolution


def _scope_receipt_valid(store: RuntimeStore, bundle: ProofChallengeBundle) -> tuple[bool, str]:
    if not bundle.natural_scope_receipt_id:
        return False, "natural-language-to-formal scope receipt missing"
    receipt = store.read_receipt(bundle.natural_scope_receipt_id)
    if receipt is None:
        return False, "natural-language-to-formal scope receipt missing or corrupt"
    if receipt.get("module") != "mind" or receipt.get("obligation_id") != bundle.obligation_id:
        return False, "natural-language-to-formal scope receipt has wrong module or obligation"
    if receipt.get("verdict") != Verdict.CLEARED.value or receipt.get("action") != "natural-formal-scope":
        return False, "natural-language-to-formal scope remains unverified"
    expected = digest({
        "obligation_id": bundle.obligation_id,
        "candidate_hash": bundle.base_candidate_hash,
        "scope_hash": bundle.scope_hash,
    })
    if receipt.get("input_hash") != expected:
        return False, "natural-language-to-formal scope receipt binding mismatch"
    return True, "ok"


def natural_formal_scope_receipt(
    root: Path,
    obligation: ProofObligation,
    candidate: FormalizationCandidate,
    *,
    scope_hash: str,
    verifier: str,
    supported: bool,
    provenance_group: str | None = None,
) -> Receipt:
    """Record an explicit scope-alignment check; it is never inferred from solver success."""
    verdict = Verdict.CLEARED if supported else Verdict.UNKNOWN
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="mind",
        obligation_id=obligation.obligation_id,
        verdict=verdict,
        action="natural-formal-scope",
        input_hash=digest({
            "obligation_id": obligation.obligation_id,
            "candidate_hash": candidate.candidate_hash,
            "scope_hash": scope_hash,
        }),
        output_hash=digest({"supported": supported, "verifier": verifier}),
        evidence=(EvidenceRef(
            evidence_class=EvidenceClass.DERIVED,
            verifier=verifier,
            provenance_group=provenance_group,
            metadata={
                "scope": "alignment between the stated natural claim and this formal encoding",
                "candidate_hash": candidate.candidate_hash,
                "scope_hash": scope_hash,
                "independent_verification_claimed": False,
            },
        ),),
        verifier=verifier,
        tool_version="scope-alignment-v1",
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=() if supported else ("natural/formal scope alignment not established",),
        notes="Scope alignment is a separate obligation; DERIVED evidence is not an independent proof.",
        task_id=_task_id(obligation),
    )
    RuntimeStore(root).write_receipt(receipt)
    return receipt


def finalize_proof_bundle(root: Path, bundle: ProofChallengeBundle) -> Receipt:
    """Finalize only after all bound load-bearing challenges and scope checks resolve."""
    store = RuntimeStore(root)
    verdict = Verdict.CLEARED
    unresolved: list[str] = []
    linked_receipts: list[str] = []
    if not bundle.base_candidate_hash or not bundle.scope_hash or not bundle.obligation_set_hash:
        verdict = Verdict.UNKNOWN
        unresolved.append("base formal encoding or binding hashes missing")
    for challenge_id in bundle.challenge_ids:
        challenge = store.read_challenge(challenge_id)
        if challenge is None:
            verdict = Verdict.UNKNOWN if verdict is not Verdict.ISSUE else verdict
            unresolved.append(f"challenge missing or corrupt: {challenge_id}")
            continue
        if challenge.get("obligation_id") != bundle.obligation_id:
            verdict = Verdict.ISSUE
            unresolved.append(f"challenge obligation mismatch: {challenge_id}")
            continue
        for key, expected in (
            ("candidate_hash", bundle.base_candidate_hash),
            ("scope_hash", bundle.scope_hash),
            ("obligation_set_hash", bundle.obligation_set_hash),
        ):
            if challenge.get(key) != expected:
                verdict = Verdict.ISSUE
                unresolved.append(f"challenge {key} mismatch: {challenge_id}")
        state = str(challenge.get("state"))
        resolution = store.latest_resolution(challenge_id)
        if state == ChallengeState.UNAVAILABLE.value:
            if verdict is not Verdict.ISSUE:
                verdict = Verdict.UNAVAILABLE
            unresolved.append(f"mandatory verifier unavailable: {challenge_id}")
        elif state != ChallengeState.RESOLVED.value or resolution is None:
            if verdict not in {Verdict.ISSUE, Verdict.UNAVAILABLE}:
                verdict = Verdict.UNKNOWN
            unresolved.append(f"load-bearing proof challenge unresolved: {challenge_id}")
        else:
            outcome = str(resolution.get("outcome"))
            receipt_id = resolution.get("verifier_receipt_id")
            if receipt_id:
                linked_receipts.append(str(receipt_id))
            if outcome == ResolutionOutcome.REFUTES_BASE.value:
                verdict = Verdict.ISSUE
                unresolved.append(f"candidate refuted: {challenge_id}")
            elif outcome == ResolutionOutcome.SCOPE_SPLIT.value:
                if verdict not in {Verdict.ISSUE, Verdict.UNAVAILABLE}:
                    verdict = Verdict.UNKNOWN
                unresolved.append(f"scope split requires regenerated candidate: {challenge_id}")
            elif outcome != ResolutionOutcome.SUPPORTS_BASE.value:
                if verdict not in {Verdict.ISSUE, Verdict.UNAVAILABLE}:
                    verdict = Verdict.UNKNOWN
                unresolved.append(f"challenge inconclusive: {challenge_id}")
    scope_ok, scope_reason = _scope_receipt_valid(store, bundle)
    if not scope_ok and verdict is Verdict.CLEARED:
        verdict = Verdict.UNKNOWN
    if not scope_ok:
        unresolved.append(scope_reason)
    else:
        linked_receipts.append(str(bundle.natural_scope_receipt_id))
    result = {
        "bundle_id": bundle.bundle_id,
        "base_candidate_hash": bundle.base_candidate_hash,
        "scope_hash": bundle.scope_hash,
        "obligation_set_hash": bundle.obligation_set_hash,
        "challenge_ids": bundle.challenge_ids,
        "selected_plan_ids": bundle.selected_plan_ids,
        "linked_receipt_ids": tuple(linked_receipts),
        "scope_verified": scope_ok,
        "verdict": verdict.value,
    }
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="mind",
        obligation_id=bundle.obligation_id,
        verdict=verdict,
        action="finalize-proof-bundle",
        input_hash=digest({
            "bundle_id": bundle.bundle_id,
            "base_candidate_hash": bundle.base_candidate_hash,
            "scope_hash": bundle.scope_hash,
            "obligation_set_hash": bundle.obligation_set_hash,
            "challenge_ids": bundle.challenge_ids,
            "selected_plan_ids": bundle.selected_plan_ids,
        }),
        output_hash=digest(result),
        evidence=(EvidenceRef(
            evidence_class=EvidenceClass.DERIVED,
            verifier="mind:proof_bundle_gate",
            metadata={
                "scope": "mechanical integration of separately stored claim-native receipts",
                **result,
            },
        ),),
        verifier="mind:proof_bundle_gate",
        tool_version="egrt.challenge.v1",
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=tuple(dict.fromkeys(unresolved)),
        notes=json.dumps(result, sort_keys=True),
        task_id=bundle.task_id,
    )
    store.write_receipt(receipt)
    return receipt
