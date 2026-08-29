"""User-facing FAST-P8 alpha command for the isolated Gauntlet runtime."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

from gauntlet_host.constants import (
    DEFAULT_LAUNCH_TIMEOUT_SECONDS,
    MODULE_CLI,
    REPO_ROOT,
    VENDOR_ROOT,
)
from gauntlet_host.finalizer import (
    FinalizationResult,
    encode_finalization,
    finalization_exit_code,
    print_human_finalization,
)
from gauntlet_host.launcher import run_gauntlet_turn

CLI_PROTOCOL_VERSION = "gauntlet.cli.v1"
OBLIGATION_KINDS = (
    "PROOF",
    "DISCOVERY",
    "SYNTHESIS",
    "ENGINEERING",
    "EVALUATION",
    "ASSURANCE",
    "PREFLIGHT",
    "REVIEW",
    "ADAPTATION",
    "ADVERSARY",
)


@dataclass(frozen=True, slots=True)
class TaskBinding:
    """Explicit canonical task binding used by one CLI session."""

    task_id: str
    created: bool
    obligation_id: str | None = None


class CliError(RuntimeError):
    """Typed, fail-closed CLI setup error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _version() -> str:
    path = REPO_ROOT / "VERSION"
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.5.1-fast-p8"
    return value or "0.5.1-fast-p8"


def _resolve_root(value: str) -> Path:
    requested = Path(value).expanduser().resolve(strict=False)
    expected = REPO_ROOT.resolve()
    if requested != expected:
        raise CliError(
            "CLI_ROOT_MISMATCH",
            (
                "FAST-P8 is repository-bound; --root must identify the checkout "
                f"containing this command ({expected})"
            ),
        )

    required = (
        requested / "tools" / "soul_runtime.py",
        MODULE_CLI,
        VENDOR_ROOT,
    )
    if not all(path.exists() for path in required):
        raise CliError(
            "CLI_RUNTIME_FILES_MISSING",
            "Gauntlet task, adapter, or pinned runtime files are missing",
        )
    return requested


def _json_subprocess(
    command: list[str],
    *,
    root: Path,
    environment: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any], str]:
    completed = subprocess.run(
        command,
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CliError(
            "CLI_SUBPROCESS_PROTOCOL_ERROR",
            (
                f"{Path(command[1]).name} returned invalid JSON "
                f"(exit {completed.returncode})"
            ),
        ) from exc
    if not isinstance(value, dict):
        raise CliError(
            "CLI_SUBPROCESS_PROTOCOL_ERROR",
            f"{Path(command[1]).name} returned a non-object JSON document",
        )
    return completed.returncode, value, completed.stderr


def _soul_command(root: Path, *arguments: str) -> dict[str, Any]:
    command = [
        sys.executable,
        str(root / "tools" / "soul_runtime.py"),
        "--root",
        str(root),
        *arguments,
    ]
    returncode, value, stderr = _json_subprocess(command, root=root)
    if returncode != 0:
        message = stderr.strip() or json.dumps(value, sort_keys=True)
        raise CliError(
            "CLI_SOUL_COMMAND_FAILED",
            f"Soul task setup failed: {message[:1000]}",
        )
    return value


def _task_status(root: Path, task_id: str) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["GAUNTLET_TASK_ID"] = task_id
    environment["PYTHONPATH"] = str(root)
    command = [
        sys.executable,
        str(MODULE_CLI),
        "--root",
        str(root),
        "task-status",
    ]
    returncode, value, stderr = _json_subprocess(
        command,
        root=root,
        environment=environment,
    )
    if returncode != 0 or value.get("status") != "OK":
        error = value.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or "CLI_TASK_STATUS_FAILED")
            message = str(error.get("message") or "task status is unavailable")
        else:
            code = "CLI_TASK_STATUS_FAILED"
            message = stderr.strip() or "task status is unavailable"
        raise CliError(code, message)
    return value


def _validate_task(root: Path, task_id: str) -> None:
    status = _task_status(root, task_id)
    task = status.get("task")
    if not isinstance(task, dict):
        raise CliError(
            "CLI_TASK_STATUS_INVALID",
            "canonical task status omitted the task projection",
        )
    if task.get("active") is not True or task.get("released") is True:
        raise CliError(
            "CLI_TASK_NOT_ACTIVE",
            f"task {task_id} is not an active unreleased task",
        )

    obligations = task.get("obligations")
    if not isinstance(obligations, list):
        raise CliError(
            "CLI_TASK_STATUS_INVALID",
            "canonical task status omitted the obligation projection",
        )
    load_bearing = [
        item
        for item in obligations
        if isinstance(item, dict) and item.get("load_bearing") is True
    ]
    if not load_bearing:
        raise CliError(
            "CLI_TASK_HAS_NO_LOAD_BEARING_OBLIGATION",
            (
                "the alpha refuses to run an empty task because an empty "
                "release surface cannot establish completed work"
            ),
        )


def _create_task(
    root: Path,
    *,
    goal: str,
    kind: str,
    claim: str,
) -> TaskBinding:
    started = _soul_command(root, "start", "--goal", goal)
    task_id = started.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise CliError(
            "CLI_TASK_START_PROTOCOL_ERROR",
            "Soul start did not return a task identifier",
        )

    added = _soul_command(
        root,
        "add",
        task_id,
        kind,
        "--claim",
        claim,
    )
    obligation_id = added.get("obligation_id")
    if not isinstance(obligation_id, str) or not obligation_id.strip():
        raise CliError(
            "CLI_OBLIGATION_PROTOCOL_ERROR",
            "Soul add did not return an obligation identifier",
        )

    _validate_task(root, task_id)
    return TaskBinding(
        task_id=task_id,
        created=True,
        obligation_id=obligation_id,
    )


def _bind_task(
    root: Path,
    *,
    task_id: str | None,
    prompt: str,
    kind: str,
    claim: str | None,
) -> TaskBinding:
    if task_id:
        _validate_task(root, task_id)
        return TaskBinding(task_id=task_id, created=False)
    return _create_task(
        root,
        goal=prompt,
        kind=kind,
        claim=claim or prompt,
    )


def _run_bound_turn(
    root: Path,
    binding: TaskBinding,
    prompt: str,
    *,
    model: str | None,
    provider: str | None,
    toolsets: Sequence[str],
    timeout: float,
) -> FinalizationResult:
    return run_gauntlet_turn(
        prompt,
        task_id=binding.task_id,
        root=root,
        model=model,
        provider=provider,
        toolsets=toolsets,
        timeout_seconds=timeout,
    )


def _emit_result(result: FinalizationResult, *, json_output: bool) -> None:
    if json_output:
        print(encode_finalization(result))
    else:
        print_human_finalization(result)


def _emit_error(error: CliError, *, json_output: bool) -> None:
    if json_output:
        print(
            json.dumps(
                {
                    "schema": CLI_PROTOCOL_VERSION,
                    "status": "ERROR",
                    "error": {
                        "code": error.code,
                        "message": error.message,
                    },
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return
    print(f"gauntlet: {error.message} [{error.code}]", file=sys.stderr)


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        default=str(REPO_ROOT),
        help="active The-Gauntlet checkout; FAST-P8 is repository-bound",
    )
    parser.add_argument("--task-id")
    parser.add_argument(
        "--kind",
        type=str.upper,
        choices=OBLIGATION_KINDS,
        default="DISCOVERY",
        help="kind for the one load-bearing obligation created with a new task",
    )
    parser.add_argument(
        "--claim",
        help="claim for a newly created task; defaults to the submitted prompt",
    )
    parser.add_argument("--model")
    parser.add_argument("--provider")
    parser.add_argument("--toolset", action="append", default=[])
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_LAUNCH_TIMEOUT_SECONDS,
    )


def _run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gauntlet",
        description=(
            "Run one isolated Gauntlet-bundled agent turn and apply Soul's "
            "canonical release gate."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_version()} FAST-P8-alpha",
    )
    _add_common_arguments(parser)
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit the complete Soul-gated finalization document",
    )
    parser.add_argument("prompt", nargs="+")
    return parser


def _chat_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gauntlet chat",
        description=(
            "Run multiple turns against one explicitly bound canonical task. "
            "Use /task or /quit at the prompt."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_version()} FAST-P8-alpha",
    )
    _add_common_arguments(parser)
    return parser


def _run_command(argv: Sequence[str]) -> int:
    args = _run_parser().parse_args(argv)
    prompt = " ".join(args.prompt).strip()
    try:
        root = _resolve_root(args.root)
        binding = _bind_task(
            root,
            task_id=args.task_id,
            prompt=prompt,
            kind=args.kind,
            claim=args.claim,
        )
        if binding.created and not args.json_output:
            print(f"[GAUNTLET TASK] {binding.task_id}", file=sys.stderr)
        result = _run_bound_turn(
            root,
            binding,
            prompt,
            model=args.model,
            provider=args.provider,
            toolsets=args.toolset,
            timeout=args.timeout,
        )
    except CliError as exc:
        _emit_error(exc, json_output=args.json_output)
        return 2

    _emit_result(result, json_output=args.json_output)
    return finalization_exit_code(result)


def _chat_command(argv: Sequence[str]) -> int:
    args = _chat_parser().parse_args(argv)
    try:
        root = _resolve_root(args.root)
        binding: TaskBinding | None = None
        if args.task_id:
            _validate_task(root, args.task_id)
            binding = TaskBinding(task_id=args.task_id, created=False)
    except CliError as exc:
        _emit_error(exc, json_output=False)
        return 2

    print("Gauntlet FAST-P8 alpha chat. Commands: /task, /quit.")
    while True:
        try:
            prompt = input("gauntlet> ").strip()
        except EOFError:
            print()
            return 0

        if not prompt:
            continue
        if prompt.lower() in {"/quit", "/exit", "quit", "exit"}:
            return 0
        if prompt.lower() == "/task":
            print(binding.task_id if binding else "No task has been created yet.")
            continue

        try:
            if binding is None:
                binding = _create_task(
                    root,
                    goal=prompt,
                    kind=args.kind,
                    claim=args.claim or prompt,
                )
                print(f"[GAUNTLET TASK] {binding.task_id}")
            result = _run_bound_turn(
                root,
                binding,
                prompt,
                model=args.model,
                provider=args.provider,
                toolsets=args.toolset,
                timeout=args.timeout,
            )
        except CliError as exc:
            _emit_error(exc, json_output=False)
            return 2
        _emit_result(result, json_output=False)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "chat":
        return _chat_command(arguments[1:])
    if arguments and arguments[0] == "run":
        arguments = arguments[1:]
    return _run_command(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
