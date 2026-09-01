"""Parent-owned Soul release-gate finalization for completed worker turns."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from gauntlet_host.constants import (
    ADAPTER_PROTOCOL_VERSION,
    DEFAULT_ADAPTER_TIMEOUT_SECONDS,
    FINALIZATION_PROTOCOL_VERSION,
    MODULE_CLI,
)
from gauntlet_host.ipc import RuntimeResult, WorkerStatus

ALLOWED_VERDICTS = {"CLEARED", "ISSUE", "UNKNOWN", "UNAVAILABLE"}


@dataclass(frozen=True, slots=True)
class FinalizationResult:
    """A bounded parent-side result with an explicit Soul gate state."""

    schema: str
    task_id: str
    state: str
    accepted: bool
    final_response: str | None
    worker_status: str
    worker_event: str
    release_gate_invoked: bool
    release_gate_verdict: str | None
    release_eligible: bool
    task_release_performed: bool
    canonical_receipt_created: bool
    unresolved: dict[str, Any] | None
    error: dict[str, str] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinalizerError(RuntimeError):
    """Typed, fail-closed finalization error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _base(
    task_id: str,
    worker_result: RuntimeResult,
    *,
    state: str,
    accepted: bool,
    release_gate_invoked: bool,
    release_gate_verdict: str | None,
    release_eligible: bool,
    unresolved: dict[str, Any] | None = None,
    error: dict[str, str] | None = None,
) -> FinalizationResult:
    response = worker_result.payload.get("final_response")
    if not isinstance(response, str):
        response = None
    return FinalizationResult(
        schema=FINALIZATION_PROTOCOL_VERSION,
        task_id=task_id,
        state=state,
        accepted=accepted,
        final_response=response,
        worker_status=worker_result.status.value,
        worker_event=worker_result.event,
        release_gate_invoked=release_gate_invoked,
        release_gate_verdict=release_gate_verdict,
        release_eligible=release_eligible,
        task_release_performed=False,
        canonical_receipt_created=False,
        unresolved=unresolved,
        error=error,
    )


def _adapter_environment(root: Path, task_id: str) -> dict[str, str]:
    environment = dict(os.environ)
    environment["GAUNTLET_TASK_ID"] = task_id
    environment["PYTHONPATH"] = str(root)
    environment["PYTHONUNBUFFERED"] = "1"
    for bypass in (
        "HERMES_YOLO_MODE",
        "HERMES_ACCEPT_HOOKS",
        "HERMES_INTERACTIVE",
    ):
        environment.pop(bypass, None)
    return environment


def _read_release_gate(root: Path, task_id: str) -> dict[str, Any]:
    module_cli = (root / "gauntlet_host" / "module_cli.py").resolve()
    expected = MODULE_CLI.resolve()
    if module_cli != expected or not module_cli.is_file():
        raise FinalizerError(
            "FINALIZER_ADAPTER_MISSING",
            "finalizer adapter path does not match the active Gauntlet repository",
        )

    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(module_cli),
                "--root",
                str(root),
                "release-status",
            ],
            cwd=root,
            env=_adapter_environment(root, task_id),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=DEFAULT_ADAPTER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FinalizerError(
            "FINALIZER_GATE_TIMEOUT",
            "Soul release-gate status exceeded the bounded adapter timeout",
        ) from exc
    except OSError as exc:
        raise FinalizerError(
            "FINALIZER_GATE_START_FAILED",
            f"cannot start Soul release-gate adapter: {type(exc).__name__}",
        ) from exc

    records = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(records) != 1:
        raise FinalizerError(
            "FINALIZER_GATE_PROTOCOL_ERROR",
            "Soul release-gate adapter must return exactly one JSON record",
        )
    try:
        value = json.loads(records[0])
    except json.JSONDecodeError as exc:
        raise FinalizerError(
            "FINALIZER_GATE_PROTOCOL_ERROR",
            "Soul release-gate adapter returned invalid JSON",
        ) from exc
    if not isinstance(value, dict):
        raise FinalizerError(
            "FINALIZER_GATE_PROTOCOL_ERROR",
            "Soul release-gate adapter result must be a JSON object",
        )
    if value.get("schema") != ADAPTER_PROTOCOL_VERSION:
        raise FinalizerError(
            "FINALIZER_GATE_SCHEMA_MISMATCH",
            f"Soul release-gate adapter schema must be {ADAPTER_PROTOCOL_VERSION}",
        )
    if value.get("action") != "release-status" or value.get("task_id") != task_id:
        raise FinalizerError(
            "FINALIZER_GATE_CORRELATION_MISMATCH",
            "Soul release-gate result did not match the completed worker task",
        )
    if value.get("read_only") is not True or value.get("mutation_performed") is not False:
        raise FinalizerError(
            "FINALIZER_AUTHORITY_VIOLATION",
            "Soul release-gate adapter violated the read-only finalizer contract",
        )
    expected_exit = 0 if value.get("status") == "OK" else 2
    if completed.returncode != expected_exit:
        raise FinalizerError(
            "FINALIZER_GATE_EXIT_MISMATCH",
            "Soul release-gate adapter status and process exit did not agree",
        )
    if value.get("status") != "OK":
        error = value.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or "FINALIZER_GATE_UNAVAILABLE")
            message = str(error.get("message") or "Soul release gate is unavailable")
        else:
            code = "FINALIZER_GATE_UNAVAILABLE"
            message = "Soul release gate is unavailable"
        raise FinalizerError(code, message)
    return value


def finalize_worker_result(
    root: Path,
    task_id: str,
    worker_result: RuntimeResult,
) -> FinalizationResult:
    """Apply the existing Soul release gate after a completed worker turn."""

    root = root.expanduser().resolve(strict=False)
    if worker_result.task_id != task_id:
        return _base(
            task_id,
            worker_result,
            state="FINALIZER_ERROR",
            accepted=False,
            release_gate_invoked=False,
            release_gate_verdict=None,
            release_eligible=False,
            error={
                "code": "FINALIZER_TASK_MISMATCH",
                "message": "worker result task identity differs from finalizer task identity",
            },
        )
    if worker_result.status is not WorkerStatus.OK:
        error = None
        if worker_result.error is not None:
            error = {
                "code": worker_result.error.code,
                "message": worker_result.error.message,
            }
        return _base(
            task_id,
            worker_result,
            state="WORKER_NOT_COMPLETED",
            accepted=False,
            release_gate_invoked=False,
            release_gate_verdict=None,
            release_eligible=False,
            error=error,
        )

    try:
        gate = _read_release_gate(root, task_id)
        release = gate.get("release")
        if not isinstance(release, dict):
            raise FinalizerError(
                "FINALIZER_GATE_PROTOCOL_ERROR",
                "Soul release-gate result omitted the release projection",
            )
        verdict = str(release.get("verdict") or "")
        if verdict not in ALLOWED_VERDICTS:
            raise FinalizerError(
                "FINALIZER_GATE_VERDICT_INVALID",
                "Soul release gate returned an unsupported verdict",
            )
        eligible = release.get("release_eligible") is True
        if eligible != (verdict == "CLEARED"):
            raise FinalizerError(
                "FINALIZER_GATE_CONTRADICTION",
                "Soul release eligibility contradicted its canonical verdict",
            )
        detail = release.get("detail")
        unresolved = detail if isinstance(detail, dict) else {"detail": detail}
        if verdict == "CLEARED":
            return _base(
                task_id,
                worker_result,
                state="CLEARED",
                accepted=True,
                release_gate_invoked=True,
                release_gate_verdict=verdict,
                release_eligible=True,
                unresolved=None,
            )
        return _base(
            task_id,
            worker_result,
            state="UNRESOLVED",
            accepted=False,
            release_gate_invoked=True,
            release_gate_verdict=verdict,
            release_eligible=False,
            unresolved=unresolved,
        )
    except FinalizerError as exc:
        return _base(
            task_id,
            worker_result,
            state="FINALIZER_ERROR",
            accepted=False,
            release_gate_invoked=True,
            release_gate_verdict=None,
            release_eligible=False,
            error={"code": exc.code, "message": exc.message},
        )


def encode_finalization(result: FinalizationResult) -> str:
    return json.dumps(
        result.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def finalization_exit_code(result: FinalizationResult) -> int:
    if result.state == "CLEARED":
        return 0
    if result.state == "WORKER_NOT_COMPLETED" and result.worker_status == "UNAVAILABLE":
        return 3
    return 2


def print_human_finalization(result: FinalizationResult) -> None:
    if result.final_response:
        print(result.final_response)
    if result.state != "CLEARED":
        print()
        print("[GAUNTLET STATUS]")
        print(
            json.dumps(
                {
                    "state": result.state,
                    "task_id": result.task_id,
                    "release_gate_invoked": result.release_gate_invoked,
                    "verdict": result.release_gate_verdict,
                    "release_eligible": result.release_eligible,
                    "unresolved": result.unresolved,
                    "error": result.error,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
