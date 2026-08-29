"""Parent-side launcher for one isolated vendored runtime turn."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from typing import Sequence

from gauntlet_host.constants import (
    DEFAULT_AGENT_RUN_BUDGET_SECONDS,
    DEFAULT_LAUNCH_TIMEOUT_SECONDS,
    GAUNTLET_TOOLSET,
    MAX_AGENT_RUN_BUDGET_SECONDS,
    MAX_LAUNCH_TIMEOUT_SECONDS,
    MODULE_CLI,
    REPO_ROOT,
    VENDOR_ROOT,
    WORKER_MAIN,
)
from gauntlet_host.ipc import (
    IPCContractError,
    RuntimeRequest,
    RuntimeResult,
    WorkerError,
    WorkerOperation,
    WorkerStatus,
    decode_result,
    encode_request,
    encode_result,
)
from gauntlet_host.runtime_profile import (
    RuntimeProfile,
    RuntimeProfileError,
    prepare_runtime_profile,
)


def _failure(
    request: RuntimeRequest,
    *,
    status: WorkerStatus,
    event: str,
    code: str,
    message: str,
) -> RuntimeResult:
    return RuntimeResult(
        request_id=request.request_id,
        task_id=request.task_id,
        status=status,
        event=event,
        error=WorkerError(code=code, message=message),
    )


def _bounded_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("timeout must be a number")
    timeout = float(value)
    if timeout <= 0 or timeout > MAX_LAUNCH_TIMEOUT_SECONDS:
        raise ValueError(
            f"timeout must be greater than 0 and at most {MAX_LAUNCH_TIMEOUT_SECONDS:g}"
        )
    return timeout


def _worker_environment(profile: RuntimeProfile, request: RuntimeRequest) -> dict[str, str]:
    environment = dict(os.environ)
    environment["HERMES_HOME"] = profile.runtime_home
    environment["PYTHONPATH"] = str(VENDOR_ROOT)
    environment["PYTHONUNBUFFERED"] = "1"
    environment["GAUNTLET_TASK_ID"] = request.task_id
    environment["GAUNTLET_REPO_ROOT"] = str(REPO_ROOT)
    environment["GAUNTLET_MODULE_CLI"] = str(MODULE_CLI)

    for inherited_bypass in (
        "HERMES_YOLO_MODE",
        "HERMES_ACCEPT_HOOKS",
        "HERMES_INTERACTIVE",
    ):
        environment.pop(inherited_bypass, None)
    return environment


def _parse_worker_output(
    request: RuntimeRequest,
    *,
    stdout: str,
    returncode: int,
) -> RuntimeResult:
    records = [line for line in stdout.splitlines() if line.strip()]
    if len(records) != 1:
        return _failure(
            request,
            status=WorkerStatus.ERROR,
            event="launcher.protocol_failed",
            code="WORKER_PROTOCOL_VIOLATION",
            message=(
                "worker stdout must contain exactly one non-empty JSONL record; "
                f"received {len(records)}"
            ),
        )

    try:
        result = decode_result(records[0])
    except IPCContractError as exc:
        return _failure(
            request,
            status=WorkerStatus.ERROR,
            event="launcher.protocol_failed",
            code=exc.code,
            message=exc.message,
        )

    if result.request_id != request.request_id or result.task_id != request.task_id:
        return _failure(
            request,
            status=WorkerStatus.ERROR,
            event="launcher.protocol_failed",
            code="WORKER_CORRELATION_MISMATCH",
            message="worker result does not match the launched request and task identifiers",
        )

    expected_exit = {
        WorkerStatus.OK: 0,
        WorkerStatus.ERROR: 2,
        WorkerStatus.UNAVAILABLE: 3,
    }[result.status]
    if returncode != expected_exit:
        return _failure(
            request,
            status=WorkerStatus.ERROR,
            event="launcher.protocol_failed",
            code="WORKER_EXIT_STATUS_MISMATCH",
            message=(
                f"worker exited with {returncode}; status {result.status.value} "
                f"requires exit {expected_exit}"
            ),
        )

    if result.status is WorkerStatus.OK:
        final_response = result.payload.get("final_response")
        if not isinstance(final_response, str) or not final_response.strip():
            return _failure(
                request,
                status=WorkerStatus.ERROR,
                event="launcher.protocol_failed",
                code="WORKER_RESPONSE_MISSING",
                message="successful worker result did not contain a final response",
            )
    return result


def _effective_toolsets(toolsets: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*toolsets, GAUNTLET_TOOLSET)))


def run_worker_turn(
    prompt: str,
    *,
    task_id: str,
    cwd: Path | str | None = None,
    model: str | None = None,
    provider: str | None = None,
    toolsets: Sequence[str] = (),
    timeout_seconds: float = DEFAULT_LAUNCH_TIMEOUT_SECONDS,
) -> RuntimeResult:
    """Run one upstream AIAgent turn through the isolated JSONL worker."""

    request = RuntimeRequest(
        request_id=f"request-{uuid.uuid4().hex}",
        task_id=task_id,
        operation=WorkerOperation.RUN,
        prompt=prompt,
        cwd=str(Path(cwd or Path.cwd()).expanduser().resolve(strict=False)),
        model=model,
        provider=provider,
        toolsets=_effective_toolsets(toolsets),
        metadata={},
    )

    try:
        timeout = _bounded_timeout(timeout_seconds)
    except ValueError as exc:
        return _failure(
            request,
            status=WorkerStatus.ERROR,
            event="launcher.request_rejected",
            code="INVALID_LAUNCH_TIMEOUT",
            message=str(exc),
        )

    request.metadata["run_budget_seconds"] = min(
        MAX_AGENT_RUN_BUDGET_SECONDS,
        DEFAULT_AGENT_RUN_BUDGET_SECONDS,
        max(1.0, timeout - 5.0),
    )

    try:
        profile = prepare_runtime_profile()
    except RuntimeProfileError as exc:
        return _failure(
            request,
            status=WorkerStatus.ERROR,
            event="launcher.profile_failed",
            code=exc.code,
            message=exc.message,
        )

    required_files = (
        VENDOR_ROOT,
        WORKER_MAIN,
        MODULE_CLI,
    )
    if not VENDOR_ROOT.is_dir() or not all(path.is_file() for path in required_files[1:]):
        return _failure(
            request,
            status=WorkerStatus.ERROR,
            event="launcher.start_failed",
            code="WORKER_FILES_MISSING",
            message="vendored runtime, worker entry point, or module adapter is missing",
        )

    environment = _worker_environment(profile, request)
    command = [sys.executable, str(WORKER_MAIN)]

    try:
        completed = subprocess.run(
            command,
            input=encode_request(request) + "\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=VENDOR_ROOT,
            env=environment,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _failure(
            request,
            status=WorkerStatus.UNAVAILABLE,
            event="launcher.worker_timeout",
            code="WORKER_TIMEOUT",
            message=f"isolated runtime exceeded the {timeout:g}-second launcher bound",
        )
    except OSError as exc:
        return _failure(
            request,
            status=WorkerStatus.ERROR,
            event="launcher.start_failed",
            code="WORKER_START_FAILED",
            message=f"cannot start isolated runtime worker: {exc}",
        )
    except IPCContractError as exc:
        return _failure(
            request,
            status=WorkerStatus.ERROR,
            event="launcher.request_rejected",
            code=exc.code,
            message=exc.message,
        )

    return _parse_worker_output(
        request,
        stdout=completed.stdout,
        returncode=completed.returncode,
    )


def _error_document(result: RuntimeResult) -> str:
    assert result.error is not None
    return json.dumps(
        {
            "status": result.status.value,
            "event": result.event,
            "task_id": result.task_id,
            "error": {
                "code": result.error.code,
                "message": result.error.message,
            },
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m gauntlet_host.launcher",
        description="Run one isolated Gauntlet-bundled agent turn.",
    )
    parser.add_argument("prompt")
    parser.add_argument("--task-id")
    parser.add_argument("--cwd", default=str(Path.cwd()))
    parser.add_argument("--model")
    parser.add_argument("--provider")
    parser.add_argument("--toolset", action="append", default=[])
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_LAUNCH_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="print the complete transport result instead of only the answer",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    task_id = args.task_id or f"task-runtime-{uuid.uuid4().hex[:16]}"
    result = run_worker_turn(
        args.prompt,
        task_id=task_id,
        cwd=args.cwd,
        model=args.model,
        provider=args.provider,
        toolsets=args.toolset,
        timeout_seconds=args.timeout,
    )

    if args.json_output:
        print(encode_result(result))
    elif result.status is WorkerStatus.OK:
        print(result.payload["final_response"])
    else:
        print(_error_document(result), file=sys.stderr)

    return {
        WorkerStatus.OK: 0,
        WorkerStatus.ERROR: 2,
        WorkerStatus.UNAVAILABLE: 3,
    }[result.status]


if __name__ == "__main__":
    raise SystemExit(main())
