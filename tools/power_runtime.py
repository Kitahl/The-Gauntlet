"""Proofrig engineering-verification executor with explicit plans and hashed receipts.

The executor never uses a shell. Known verifier families have constrained command
shapes. Arbitrary custom commands are disabled unless the caller's environment
explicitly sets EGR_POWER_ALLOW_CUSTOM_COMMANDS=1, making that bypass visible at the
outer tool/command boundary rather than silently hidden inside this runtime.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import EvidenceClass, EvidenceRef, Receipt, Verdict, digest, text_digest


@dataclass(frozen=True)
class VerificationCheck:
    check_id: str
    kind: str
    command: tuple[str, ...]
    expected_exit: int = 0
    timeout_seconds: int = 60
    mandatory: bool = True
    defect_classes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationPlan:
    plan_id: str
    obligation_id: str
    system_boundary: str
    claim: str
    invariants: tuple[str, ...]
    checks: tuple[VerificationCheck, ...]


KNOWN_KINDS = {"python-unittest", "compileall", "pytest", "ruff", "z3", "semgrep", "mutmut", "custom"}
# Modules the constrained python-module families may invoke via `-m`.
ALLOWED_PY_MODULES = {"unittest", "pytest", "compileall", "ruff"}
# Flags that turn a constrained module command into an arbitrary-code vector:
# `-c` executes source, `-W` can import an arbitrary module, `-p` loads a plugin.
BLOCKED_MODULE_FLAGS = ("-c", "-W", "-p")
_PATHY_SUFFIXES = (".py", ".pyi", ".txt", ".cfg", ".toml", ".json", ".ini")


def _basename(value: str) -> str:
    return Path(value).name.lower()


def _has_sep(value: str) -> bool:
    return os.sep in value or "/" in value


def _same_file(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _looks_like_path(token: str) -> bool:
    if token == "discover":
        return True
    if _has_sep(token) or token.endswith(_PATHY_SUFFIXES):
        return True
    return Path(token).exists()


def _module_args_allowed(args: list[str], *, allow_custom: bool) -> tuple[bool, str | None]:
    """A constrained module command may carry only paths and safe flags.

    A bare non-path token after `-m unittest`/`-m pytest` is a dotted module name,
    which executes arbitrary code at import; that is exactly the vector this guards.
    """
    if allow_custom:
        return True, None
    for token in args:
        if token.startswith("-"):
            if any(token == flag or token.startswith(flag) for flag in BLOCKED_MODULE_FLAGS):
                return False, (
                    f"disallowed flag {token!r} in constrained module command; "
                    "set EGR_POWER_ALLOW_CUSTOM_COMMANDS=1 at the outer boundary to override"
                )
            continue
        if not _looks_like_path(token):
            return False, (
                f"argument {token!r} is not a path or safe flag; arbitrary module names are "
                "refused (set EGR_POWER_ALLOW_CUSTOM_COMMANDS=1 at the outer boundary to override)"
            )
    return True, None


def _command_shape_allowed(check: VerificationCheck) -> tuple[bool, str | None]:
    if check.kind not in KNOWN_KINDS:
        return False, f"unknown verifier kind: {check.kind}"
    if not check.command:
        return False, "empty command"
    command = list(check.command)
    exe = _basename(command[0])
    pythonish = exe.startswith("python") or exe in {"py"}
    allow_custom = os.environ.get("EGR_POWER_ALLOW_CUSTOM_COMMANDS") == "1"
    if check.kind == "custom":
        if not allow_custom:
            return False, "custom command disabled; set EGR_POWER_ALLOW_CUSTOM_COMMANDS=1 at the outer execution boundary"
        return True, None
    if check.kind in {"python-unittest", "compileall"}:
        module = "unittest" if check.kind == "python-unittest" else "compileall"
        if not (pythonish and command[1:3] == ["-m", module]):
            return False, f"{check.kind} command must be python -m {module} ..."
        return _module_args_allowed(command[3:], allow_custom=allow_custom)
    if check.kind == "pytest":
        if pythonish and command[1:3] == ["-m", "pytest"]:
            return _module_args_allowed(command[3:], allow_custom=allow_custom)
        if exe == "pytest":
            return _module_args_allowed(command[1:], allow_custom=allow_custom)
        return False, "pytest command must be pytest ... or python -m pytest ..."
    if check.kind == "ruff":
        if pythonish and command[1:3] == ["-m", "ruff"]:
            return _module_args_allowed(command[3:], allow_custom=allow_custom)
        if exe == "ruff":
            return _module_args_allowed(command[1:], allow_custom=allow_custom)
        return False, "ruff command must be ruff ... or python -m ruff ..."
    expected = {"z3": "z3", "semgrep": "semgrep", "mutmut": "mutmut"}[check.kind]
    return exe == expected, f"{check.kind} command must execute {expected} directly"


def _resolve_executable(check: VerificationCheck) -> tuple[str | None, str | None]:
    """Resolve argv[0] to a trusted absolute path or refuse it.

    Path-existence is not trust: a binary named `z3`/`ruff`/`pytest` sitting in a
    scratch directory must not run just because its file exists. Python families must
    be the active interpreter; direct-binary families must resolve on PATH by name.
    """
    argv0 = check.command[0]
    exe = _basename(argv0)
    pythonish = exe.startswith("python") or exe in {"py"}
    if pythonish or check.kind in {"python-unittest", "compileall"}:
        if _same_file(argv0, sys.executable):
            return sys.executable, None
        resolved = shutil.which(argv0)
        if resolved and _same_file(resolved, sys.executable):
            return resolved, None
        return None, f"python-family verifier must run the active interpreter (sys.executable), got {argv0!r}"
    on_path = shutil.which(exe)
    if on_path is None:
        return None, f"tool not found on PATH: {exe}"
    if _has_sep(argv0) and not _same_file(argv0, on_path):
        return None, f"refusing {argv0!r}: not the {exe} resolved on PATH"
    return on_path, None


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def run_check(root: Path, check: VerificationCheck) -> dict[str, Any]:
    allowed, reason = _command_shape_allowed(check)
    if not allowed:
        return {"check_id": check.check_id, "kind": check.kind, "verdict": Verdict.UNAVAILABLE.value, "reason": reason}
    resolved, resolve_reason = _resolve_executable(check)
    if resolved is None:
        return {"check_id": check.check_id, "kind": check.kind, "verdict": Verdict.UNAVAILABLE.value, "reason": resolve_reason}
    command = [resolved, *list(check.command)[1:]]
    started = time.monotonic()
    try:
        proc = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=check.timeout_seconds, shell=False)
    except subprocess.TimeoutExpired as exc:
        return {
            "check_id": check.check_id, "kind": check.kind, "verdict": Verdict.UNKNOWN.value,
            "reason": "timeout", "elapsed_seconds": time.monotonic() - started,
            "stdout_hash": text_digest(_as_text(exc.stdout)), "stderr_hash": text_digest(_as_text(exc.stderr)),
            "defect_classes": list(check.defect_classes),
        }
    except OSError as exc:
        return {"check_id": check.check_id, "kind": check.kind, "verdict": Verdict.UNAVAILABLE.value, "reason": type(exc).__name__}
    verdict = Verdict.CLEARED if proc.returncode == check.expected_exit else Verdict.ISSUE
    return {
        "check_id": check.check_id,
        "kind": check.kind,
        "verdict": verdict.value,
        "exit_code": proc.returncode,
        "expected_exit": check.expected_exit,
        "elapsed_seconds": time.monotonic() - started,
        "stdout_hash": text_digest(proc.stdout),
        "stderr_hash": text_digest(proc.stderr),
        "defect_classes": list(check.defect_classes),
    }


def run_plan(root: Path, plan: VerificationPlan) -> tuple[Receipt, dict[str, Any]]:
    store = RuntimeStore(root)
    results = [run_check(root, check) for check in plan.checks]
    by_id = {c.check_id: c for c in plan.checks}
    if len(by_id) != len(plan.checks):
        raise ValueError("verification check IDs must be unique")
    mandatory = [r for r in results if by_id[r["check_id"]].mandatory]
    if any(r["verdict"] == Verdict.ISSUE.value for r in mandatory):
        verdict = Verdict.ISSUE
    elif any(r["verdict"] == Verdict.UNKNOWN.value for r in mandatory):
        verdict = Verdict.UNKNOWN
    elif any(r["verdict"] == Verdict.UNAVAILABLE.value for r in mandatory):
        verdict = Verdict.UNAVAILABLE
    elif mandatory and all(r["verdict"] == Verdict.CLEARED.value for r in mandatory):
        verdict = Verdict.CLEARED
    else:
        verdict = Verdict.UNKNOWN
    coverage = {r["check_id"]: r.get("defect_classes", []) for r in results}
    result = {
        "plan_id": plan.plan_id,
        "verdict": verdict.value,
        "checks": results,
        "coverage": coverage,
        "coverage_boundary": "Only named checks/defect classes are covered; green checks do not imply exhaustive correctness.",
        "custom_commands_enabled": os.environ.get("EGR_POWER_ALLOW_CUSTOM_COMMANDS") == "1",
    }
    unresolved = []
    for row in mandatory:
        if row["verdict"] in (Verdict.UNAVAILABLE.value, Verdict.UNKNOWN.value):
            unresolved.append(f"{row['check_id']}: {row.get('reason', row['verdict'])}")
    receipt = Receipt(
        receipt_id=new_id("rcpt"), module="power", obligation_id=plan.obligation_id,
        verdict=verdict, action="verification-plan", input_hash=digest(plan), output_hash=digest(result),
        evidence=(EvidenceRef(evidence_class=EvidenceClass.MEASURED, verifier="power_runtime", metadata={"coverage": coverage}),),
        verifier="power_runtime", started_at=utcnow(), finished_at=utcnow(),
        unresolved=tuple(unresolved), notes=result["coverage_boundary"],
    )
    store.write_named_state("power", plan.plan_id, result)
    store.write_receipt(receipt)
    return receipt, result
