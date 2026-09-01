#!/usr/bin/env python3
"""Codex plugin helper for the task-bound governed Hermes runtime."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

SOURCE_ROOT_CANDIDATE = Path(__file__).resolve().parents[3]
EXPECTED_HOST_COMMIT = "4fa83e750f82a1b56ad59b095f0283da877ea9cc"
EXPECTED_HERMES_COMMIT = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
PROVIDER_ENV_VARS = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "NOUS_API_KEY",
)


class PluginError(RuntimeError):
    pass


def _run_text(command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _looks_like_root(path: Path) -> bool:
    return (
        (path / "gauntlet_host" / "cli.py").is_file()
        and (path / "tools" / "soul_runtime.py").is_file()
        and (path / "vendor" / "hermes-agent").is_dir()
    )


def discover_root(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    configured = os.environ.get("HERMES_GAUNTLET_ROOT", "").strip()
    if configured:
        candidates.append(Path(configured))
    candidates.extend([Path.cwd(), *Path.cwd().parents, SOURCE_ROOT_CANDIDATE])

    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve(strict=False)
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        if _looks_like_root(resolved):
            return resolved

    requested = explicit or configured or "the current directory and plugin source ancestry"
    raise PluginError(
        "No valid The-Gauntlet checkout was found. "
        f"Set HERMES_GAUNTLET_ROOT or pass --root. Last requested location: {requested}"
    )


def _git_value(root: Path, *arguments: str) -> str:
    result = _run_text(("git", "-C", str(root), *arguments), cwd=root)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise PluginError(message)
    return result.stdout.strip()


def _implementation_present(root: Path) -> bool:
    result = _run_text(
        ("git", "-C", str(root), "merge-base", "--is-ancestor", EXPECTED_HOST_COMMIT, "HEAD"),
        cwd=root,
    )
    return result.returncode == 0


def _normal_hermes_home() -> Path:
    if os.name == "nt":
        roaming = os.environ.get("APPDATA", "").strip()
        base = Path(roaming).parent / "Local" if roaming else Path.home() / "AppData" / "Local"
        return base / "hermes"
    return Path.home() / ".hermes"


def diagnose(root: Path) -> dict[str, object]:
    head = _git_value(root, "rev-parse", "HEAD")
    branch = _git_value(root, "branch", "--show-current")
    vendor = root / "vendor" / "hermes-agent"
    vendor_head = _git_value(vendor, "rev-parse", "HEAD")
    vendor_tag_result = _run_text(
        ("git", "-C", str(vendor), "describe", "--tags", "--exact-match", "HEAD"),
        cwd=root,
    )
    normal_home = _normal_hermes_home()
    governed_home = normal_home / "profiles" / "gauntlet-governed"
    provider_env_present = sorted(
        name for name in PROVIDER_ENV_VARS if os.environ.get(name, "").strip()
    )
    config_exists = (normal_home / "config.yaml").is_file()
    auth_exists = (normal_home / "auth.json").is_file()
    model_env_present = bool(os.environ.get("HERMES_INFERENCE_MODEL", "").strip())

    return {
        "root": str(root),
        "branch": branch,
        "head": head,
        "expected_host_commit": EXPECTED_HOST_COMMIT,
        "governed_implementation_present": _implementation_present(root),
        "vendor_hermes_root": str(vendor),
        "vendor_hermes_head": vendor_head,
        "vendor_hermes_expected": EXPECTED_HERMES_COMMIT,
        "vendor_hermes_matches": vendor_head == EXPECTED_HERMES_COMMIT,
        "vendor_hermes_tag": vendor_tag_result.stdout.strip()
        if vendor_tag_result.returncode == 0
        else None,
        "normal_hermes_home": str(normal_home),
        "normal_config_exists": config_exists,
        "normal_auth_exists": auth_exists,
        "provider_environment_variables_present": provider_env_present,
        "model_environment_variable_present": model_env_present,
        "provider_or_auth_hint_present": bool(config_exists or auth_exists or provider_env_present),
        "model_hint_present": bool(config_exists or model_env_present),
        "governed_home": str(governed_home),
        "governed_home_exists": governed_home.is_dir(),
        "governed_config": str(governed_home / "config.yaml"),
        "governed_session_db": str(governed_home / "state.db"),
        "governed_session_db_exists": (governed_home / "state.db").is_file(),
    }


def _validate_for_launch(root: Path) -> dict[str, object]:
    report = diagnose(root)
    if not report["governed_implementation_present"]:
        raise PluginError(
            "This checkout does not contain governed-Hermes commit " + EXPECTED_HOST_COMMIT
        )
    if not report["vendor_hermes_matches"]:
        raise PluginError(
            "The vendored Hermes checkout does not match the governed runtime pin "
            + EXPECTED_HERMES_COMMIT
        )
    return report


def _append_runtime_overrides(command: list[str], args: argparse.Namespace) -> None:
    if getattr(args, "model", None):
        command.extend(("--model", args.model))
    if getattr(args, "provider", None):
        command.extend(("--provider", args.provider))
    if getattr(args, "timeout", None) is not None:
        command.extend(("--timeout", str(args.timeout)))


def _warn_if_unconfigured(report: dict[str, object], args: argparse.Namespace) -> None:
    model_override = bool(getattr(args, "model", None))
    provider_override = bool(getattr(args, "provider", None))
    if not report["provider_or_auth_hint_present"] and not provider_override:
        print(
            "WARNING: no normal Hermes auth/config or provider credential environment variable "
            "was detected; run this helper's setup command before the first real turn.",
            file=sys.stderr,
        )
    if not report["model_hint_present"] and not model_override:
        print(
            "WARNING: no normal Hermes config or HERMES_INFERENCE_MODEL was detected; "
            "run setup or pass --model.",
            file=sys.stderr,
        )


def _execute(command: Sequence[str], *, root: Path, dry_run: bool) -> int:
    if dry_run:
        print(subprocess.list2cmdline(list(command)))
        return 0
    return subprocess.call(list(command), cwd=str(root))


def command_doctor(args: argparse.Namespace) -> int:
    root = discover_root(args.root)
    report = diagnose(root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for key, value in report.items():
            print(f"{key}={value}")
    return 0 if report["governed_implementation_present"] and report["vendor_hermes_matches"] else 2


def command_setup(args: argparse.Namespace) -> int:
    root = discover_root(args.root)
    _validate_for_launch(root)
    vendor = root / "vendor" / "hermes-agent"
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(vendor) + (os.pathsep + existing if existing else "")
    command = [sys.executable, "-c", "from hermes_cli.main import main; main()", "setup"]
    if args.dry_run:
        print(subprocess.list2cmdline(command))
        return 0
    return subprocess.call(command, cwd=str(root), env=environment)


def _run_turn(args: argparse.Namespace, *, task_id: str | None) -> int:
    root = discover_root(args.root)
    report = _validate_for_launch(root)
    _warn_if_unconfigured(report, args)
    command = [
        sys.executable,
        "-m",
        "gauntlet_host.cli",
        "run",
        "--profile",
        "governed",
        "--root",
        str(root),
    ]
    if task_id:
        command.extend(("--task-id", task_id))
    _append_runtime_overrides(command, args)
    if getattr(args, "kind", None):
        command.extend(("--kind", args.kind))
    if getattr(args, "claim", None):
        command.extend(("--claim", args.claim))
    if getattr(args, "json", False):
        command.append("--json")
    command.append(args.prompt)
    return _execute(command, root=root, dry_run=args.dry_run)


def command_start(args: argparse.Namespace) -> int:
    return _run_turn(args, task_id=None)


def command_foil(args: argparse.Namespace) -> int:
    prompt = args.prompt.strip()
    if not prompt:
        raise PluginError("FOIL requires a non-empty prompt.")
    if prompt.split(maxsplit=1)[0].casefold() != "/foil":
        prompt = f"/foil {prompt}"
    foil_args = argparse.Namespace(**vars(args))
    foil_args.kind = "ADAPTATION"
    foil_args.prompt = prompt
    return _run_turn(foil_args, task_id=None)


def command_continue(args: argparse.Namespace) -> int:
    return _run_turn(args, task_id=args.task_id)


def command_chat(args: argparse.Namespace) -> int:
    root = discover_root(args.root)
    report = _validate_for_launch(root)
    _warn_if_unconfigured(report, args)
    command = [
        sys.executable,
        "-m",
        "gauntlet_host.cli",
        "chat",
        "--profile",
        "governed",
        "--root",
        str(root),
    ]
    if args.task_id:
        command.extend(("--task-id", args.task_id))
    _append_runtime_overrides(command, args)
    return _execute(command, root=root, dry_run=args.dry_run)


def command_release(args: argparse.Namespace) -> int:
    if not args.confirm_release:
        raise PluginError(
            "Release is an explicit canonical mutation. Re-run with --confirm-release only "
            "after the user requests release and the Soul finalization is CLEARED."
        )
    root = discover_root(args.root)
    _validate_for_launch(root)
    command = [
        sys.executable,
        str(root / "tools" / "soul_runtime.py"),
        "--root",
        str(root),
        "release",
        args.task_id,
    ]
    return _execute(command, root=root, dry_run=args.dry_run)


def _add_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", help="The-Gauntlet checkout; otherwise auto-discovered")


def _add_overrides(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model")
    parser.add_argument("--provider")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--dry-run", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch or resume The Gauntlet's governed Hermes runtime from Codex."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Inspect paths, pins, and setup hints")
    _add_root(doctor)
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=command_doctor)

    setup = subparsers.add_parser("setup", help="Run the pinned Hermes setup wizard")
    _add_root(setup)
    setup.add_argument("--dry-run", action="store_true")
    setup.set_defaults(func=command_setup)

    start = subparsers.add_parser("start", help="Create a new governed task and run one turn")
    _add_root(start)
    _add_overrides(start)
    start.add_argument("--kind")
    start.add_argument("--claim")
    start.add_argument("--json", action="store_true")
    start.add_argument("--prompt", required=True)
    start.set_defaults(func=command_start)

    foil = subparsers.add_parser(
        "foil", help="Create an explicit task-bound FOIL/Mirror adaptation task"
    )
    _add_root(foil)
    _add_overrides(foil)
    foil.add_argument("--claim")
    foil.add_argument("--json", action="store_true")
    foil.add_argument("--prompt", required=True)
    foil.set_defaults(func=command_foil)

    resume = subparsers.add_parser("continue", help="Run one turn on an existing task")
    _add_root(resume)
    _add_overrides(resume)
    resume.add_argument("--task-id", required=True)
    resume.add_argument("--json", action="store_true")
    resume.add_argument("--prompt", required=True)
    resume.set_defaults(func=command_continue)

    chat = subparsers.add_parser("chat", help="Open an interactive governed chat")
    _add_root(chat)
    _add_overrides(chat)
    chat.add_argument("--task-id")
    chat.set_defaults(func=command_chat)

    release = subparsers.add_parser("release", help="Explicitly release a CLEARED task")
    _add_root(release)
    release.add_argument("--task-id", required=True)
    release.add_argument("--confirm-release", action="store_true")
    release.add_argument("--dry-run", action="store_true")
    release.set_defaults(func=command_release)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except PluginError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
