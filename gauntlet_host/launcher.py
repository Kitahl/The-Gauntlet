"""Parent-side launcher and Soul-gated finalizer for one runtime turn."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from gauntlet_host.constants import (
    DEFAULT_AGENT_RUN_BUDGET_SECONDS,
    DEFAULT_LAUNCH_TIMEOUT_SECONDS,
    GAUNTLET_TOOLSET,
    MAX_AGENT_RUN_BUDGET_SECONDS,
    MAX_LAUNCH_TIMEOUT_SECONDS,
    MODULE_CLI,
    OBSERVATION_BRIDGE,
    REPO_ROOT,
    TOKEN_MEASUREMENT_BRIDGE,
    VENDOR_ROOT,
    WORKER_MAIN,
)
from gauntlet_host.finalizer import (
    FinalizationResult,
    encode_finalization,
    finalization_exit_code,
    finalize_worker_result,
    print_human_finalization,
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
)
from gauntlet_host.lean_context import (
    LeanContextError,
    prefetch_lean_context,
)
from gauntlet_host.runtime_profile import (
    RuntimeProfile,
    RuntimeProfileError,
    prepare_runtime_profile,
)
from gauntlet_host.session_binding import (
    SessionBindingError,
    SessionTurnLockTimeout,
    derive_session_id,
    exclusive_session_turn_lock,
    session_turn_lock_path,
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
    task_root = Path(request.cwd or REPO_ROOT).expanduser().resolve(strict=False)
    environment["GAUNTLET_TASK_ID"] = request.task_id
    environment["GAUNTLET_REPO_ROOT"] = str(task_root)
    environment["GAUNTLET_MODULE_CLI"] = str(task_root / "gauntlet_host" / "module_cli.py")
    environment["GAUNTLET_OBSERVATION_BRIDGE"] = str(
        task_root / "gauntlet_host" / "observation_bridge.py"
    )
    environment["GAUNTLET_TOKEN_MEASUREMENT_BRIDGE"] = str(
        task_root / "gauntlet_host" / "token_measurement_bridge.py"
    )
    environment["GAUNTLET_TOKEN_MEASUREMENT_KEY"] = profile.token_measurement_key_path
    environment["GAUNTLET_TOKEN_MEASUREMENT_KEY_ID"] = profile.token_measurement_key_id
    environment["GAUNTLET_HOST_REQUEST_ID"] = request.request_id
    source_commit, source_tree = _source_identity()
    environment["GAUNTLET_SOURCE_COMMIT"] = source_commit
    environment["GAUNTLET_SOURCE_TREE"] = source_tree

    for inherited_bypass in (
        "HERMES_YOLO_MODE",
        "HERMES_ACCEPT_HOOKS",
        "HERMES_INTERACTIVE",
    ):
        environment.pop(inherited_bypass, None)
    return environment


def _source_identity() -> tuple[str, str]:
    """Resolve the repository-bound running source without network access."""

    values: list[str] = []
    for revision in ("HEAD^{commit}", "HEAD^{tree}"):
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "--verify", revision],
                cwd=REPO_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "", ""
        value = completed.stdout.strip().lower()
        if completed.returncode != 0 or len(value) != 40:
            return "", ""
        try:
            int(value, 16)
        except ValueError:
            return "", ""
        values.append(value)
    return values[0], values[1]


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
    jit_context: Sequence[dict[str, Any]] = (),
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

    deadline = time.monotonic() + timeout

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

    try:
        request = replace(
            request,
            session_id=derive_session_id(
                request.task_id,
                profile.session_binding_key_path,
            ),
        )
    except SessionBindingError as exc:
        return _failure(
            request,
            status=WorkerStatus.ERROR,
            event="launcher.session_binding_failed",
            code=exc.code,
            message=exc.message,
        )

    required_files = (
        WORKER_MAIN,
        MODULE_CLI,
        OBSERVATION_BRIDGE,
        TOKEN_MEASUREMENT_BRIDGE,
    )
    if not VENDOR_ROOT.is_dir() or not all(path.is_file() for path in required_files):
        return _failure(
            request,
            status=WorkerStatus.ERROR,
            event="launcher.start_failed",
            code="WORKER_FILES_MISSING",
            message=("vendored runtime, worker, module adapter, or observation bridge is missing"),
        )

    environment = _worker_environment(profile, request)
    command = [sys.executable, str(WORKER_MAIN)]
    lock_path = session_turn_lock_path(
        profile.session_lock_root,
        request.session_id or "",
    )

    try:
        lock_wait = max(0.0, deadline - time.monotonic())
        with exclusive_session_turn_lock(lock_path, timeout=lock_wait):
            remaining = deadline - time.monotonic()
            if remaining <= 5.0:
                raise SessionTurnLockTimeout(
                    "no launch budget remained after waiting for the session"
                )
            try:
                lean_context = prefetch_lean_context(
                    task_id=request.task_id,
                    repository_root=Path(request.cwd or REPO_ROOT),
                    runtime_home=Path(profile.runtime_home),
                    timeout_seconds=min(20.0, max(1.0, remaining - 5.0)),
                )
            except LeanContextError as exc:
                return _failure(
                    request,
                    status=WorkerStatus.UNAVAILABLE,
                    event="launcher.lean_prefetch_failed",
                    code=exc.code,
                    message=exc.message,
                )
            try:
                request.metadata["lean_context"] = lean_context.to_metadata(
                    session_binding_id=request.session_id or "",
                    profile_name=profile.profile_name,
                    selected_snippets=jit_context,
                )
            except LeanContextError as exc:
                return _failure(
                    request,
                    status=WorkerStatus.UNAVAILABLE,
                    event="launcher.lean_context_failed",
                    code=exc.code,
                    message=exc.message,
                )
            remaining = deadline - time.monotonic()
            if remaining <= 5.0:
                raise SessionTurnLockTimeout(
                    "no launch budget remained after parent context prefetch"
                )
            request.metadata["run_budget_seconds"] = min(
                MAX_AGENT_RUN_BUDGET_SECONDS,
                DEFAULT_AGENT_RUN_BUDGET_SECONDS,
                max(1.0, remaining - 5.0),
            )
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
                timeout=remaining,
                check=False,
            )
    except SessionTurnLockTimeout as exc:
        return _failure(
            request,
            status=WorkerStatus.UNAVAILABLE,
            event="launcher.session_busy_timeout",
            code="SESSION_TURN_BUSY",
            message=str(exc),
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


def run_gauntlet_turn(
    prompt: str,
    *,
    task_id: str,
    root: Path | str,
    model: str | None = None,
    provider: str | None = None,
    toolsets: Sequence[str] = (),
    timeout_seconds: float = DEFAULT_LAUNCH_TIMEOUT_SECONDS,
) -> FinalizationResult:
    """Run one worker turn and apply the existing Soul release gate."""

    resolved_root = Path(root).expanduser().resolve(strict=False)
    worker_result = run_worker_turn(
        prompt,
        task_id=task_id,
        cwd=resolved_root,
        model=model,
        provider=provider,
        toolsets=toolsets,
        timeout_seconds=timeout_seconds,
    )
    return finalize_worker_result(resolved_root, task_id, worker_result)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m gauntlet_host.launcher",
        description="Run one isolated Gauntlet-bundled agent turn and apply Soul's gate.",
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
        help="print the complete Soul-gated finalization result",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    task_id = args.task_id or f"task-runtime-{uuid.uuid4().hex[:16]}"
    result = run_gauntlet_turn(
        args.prompt,
        task_id=task_id,
        root=args.cwd,
        model=args.model,
        provider=args.provider,
        toolsets=args.toolset,
        timeout_seconds=args.timeout,
    )

    if args.json_output:
        print(encode_finalization(result))
    else:
        print_human_finalization(result)
    return finalization_exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
