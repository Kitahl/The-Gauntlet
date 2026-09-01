"""Axiom formal-reasoning runtime adapters and proof/derivation receipts.

A receipt verifies only the supplied formal encoding. The module never upgrades an
English claim merely because a solver or arithmetic evaluator returned successfully.
"""
from __future__ import annotations

import ast
import json
import operator
import shutil
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import EvidenceClass, EvidenceRef, Receipt, Verdict, digest, text_digest


@dataclass(frozen=True)
class ProofObligation:
    obligation_id: str
    natural_claim: str
    formal_claim: str
    assumptions: tuple[str, ...] = ()
    domain: str = "deductive"
    encoding_artifact: str | None = None
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
            "verdict": Verdict.UNKNOWN.value, "reason": "z3 timeout", "solver_status": "timeout",
            "stdout_hash": text_digest(stdout), "stderr_hash": text_digest(stderr), "tool_version": _z3_version(),
        }
    first = (proc.stdout.strip().splitlines() or [""])[0].strip().lower()
    if proc.returncode != 0:
        verdict = Verdict.ISSUE
    elif first in ("sat", "unsat"):
        verdict = Verdict.CLEARED
    elif first == "unknown":
        verdict = Verdict.UNKNOWN
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
        receipt_id=new_id("rcpt"), module="mind", obligation_id=obligation.obligation_id,
        verdict=verdict, action="exact-arithmetic", input_hash=digest({"obligation": obligation, "expression": expression}),
        output_hash=text_digest(result),
        evidence=(EvidenceRef(
            evidence_class=EvidenceClass.MEASURED,
            verifier="mind:exact_arithmetic",
            metadata={"scope": "exact evaluation of the supplied bounded arithmetic encoding"},
        ),),
        verifier="mind:exact_arithmetic", tool_version="stdlib-ast+fractions",
        started_at=utcnow(), finished_at=utcnow(), unresolved=unresolved,
        notes=f"result={result}; this receipt supports the supplied encoding, not an unstated English generalization",
    )
    store.write_receipt(receipt)
    return receipt


def smt_receipt(root: Path, obligation: ProofObligation, smt2_path: Path) -> Receipt:
    store = RuntimeStore(root)
    if smt2_path.is_file():
        encoding_hash = text_digest(smt2_path.read_text(encoding="utf-8", errors="replace"))
    else:
        encoding_hash = digest({"missing": str(smt2_path)})
    result = run_z3_smt2(smt2_path)
    evidence_class = EvidenceClass.PROVEN if result.get("solver_status") in ("sat", "unsat") and result.get("verdict") == Verdict.CLEARED.value else EvidenceClass.OBSERVED
    receipt = Receipt(
        receipt_id=new_id("rcpt"), module="mind", obligation_id=obligation.obligation_id,
        verdict=Verdict(result["verdict"]), action="z3-smt2",
        input_hash=digest({"obligation": obligation, "encoding_sha256": encoding_hash}),
        output_hash=digest(result),
        evidence=(EvidenceRef(
            evidence_class=evidence_class, verifier="z3",
            metadata={"solver_status": result.get("solver_status"), "scope": "formal SMT2 encoding only", "encoding_sha256": encoding_hash},
        ),),
        verifier="z3", tool_version=result.get("tool_version"), started_at=utcnow(), finished_at=utcnow(),
        unresolved=() if result["verdict"] == Verdict.CLEARED.value else (result.get("reason", "solver did not return a conclusive sat/unsat result"),),
        notes=json.dumps({**result, "boundary": "sat/unsat establishes a property of the supplied encoding only"}, sort_keys=True),
    )
    store.write_receipt(receipt)
    return receipt
