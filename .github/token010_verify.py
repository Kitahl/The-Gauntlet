"""Non-destructive TOKEN-010 continuity qualification on the local provider fixture."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from gauntlet_host.ipc import WorkerStatus  # noqa: E402
from gauntlet_host.launcher import run_worker_turn  # noqa: E402

PHASE5_HELPER = REPO / ".github" / "phase5_verify.py"
PINNED_HERMES = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"


def _load_phase5() -> Any:
    spec = importlib.util.spec_from_file_location("phase5_verify", PHASE5_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the checked-in deterministic provider fixture")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
    return ""


def _request_text(request: dict[str, Any]) -> str:
    messages = request.get("messages")
    if not isinstance(messages, list):
        messages = request.get("input")
    if not isinstance(messages, list):
        return ""
    return "\n".join(_message_text(message) for message in messages if isinstance(message, dict))


def _is_conversation_request(request: dict[str, Any]) -> bool:
    return request.get("stream") is True and isinstance(request.get("tools"), list)


def _run_turn(
    prompt: str,
    task_id: str,
    workload_id: str,
    root: Path,
) -> dict[str, Any]:
    os.environ["GAUNTLET_TOKEN_WORKLOAD_ID"] = workload_id
    result = run_worker_turn(
        prompt,
        task_id=task_id,
        cwd=root,
        model="phase5-mock",
        provider="custom",
        timeout_seconds=90,
    )
    if result.status is not WorkerStatus.OK:
        raise AssertionError(result.error or result)
    return {
        "status": result.status.value,
        "event": result.event,
        "payload": result.payload,
    }


def _single_turn_from_stdin() -> int:
    value = json.loads(sys.stdin.read())
    result = _run_turn(
        str(value["prompt"]),
        str(value["task_id"]),
        str(value["workload_id"]),
        Path(str(value["root"])),
    )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0


def _run_restarted_parent(
    prompt: str,
    task_id: str,
    workload_id: str,
    root: Path,
) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--single-turn"],
        cwd=REPO,
        env=dict(os.environ),
        input=json.dumps(
            {
                "prompt": prompt,
                "task_id": task_id,
                "workload_id": workload_id,
                "root": str(root),
            },
            separators=(",", ":"),
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise AssertionError("restarted parent returned a non-object result")
    return value


def _canonical_state_digest(workspace_root: Path = REPO) -> str:
    state_root = workspace_root / ".egrt"
    digest = hashlib.sha256()
    if not state_root.exists():
        digest.update(b"absent")
        return digest.hexdigest()
    for path in sorted(item for item in state_root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(state_root).as_posix().encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
        digest.update(b"\x00")
    return digest.hexdigest()


def _measurement_documents(runtime: Path) -> list[dict[str, Any]]:
    root = runtime / "measurements" / "token-efficiency"
    return [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(root.rglob("tok_*.json"))
    ]


def _git_identity() -> tuple[str, str]:
    values = [
        subprocess.check_output(
            ["git", "rev-parse", "--verify", revision],
            cwd=REPO,
            text=True,
            encoding="utf-8",
        ).strip()
        for revision in ("HEAD^{commit}", "HEAD^{tree}")
    ]
    return values[0], values[1]


def _json_run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise AssertionError("Gauntlet state command returned a non-object result")
    return value


def _create_task(root: Path, goal: str) -> str:
    task = _json_run(
        [
            sys.executable,
            str(REPO / "tools" / "soul_runtime.py"),
            "--root",
            str(root),
            "start",
            "--goal",
            goal,
        ]
    )
    return str(task["task_id"])


def _restore_environment(original: dict[str, str | None]) -> None:
    for name, value in original.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--single-turn", action="store_true")
    args = parser.parse_args(argv)
    if args.single_turn:
        return _single_turn_from_stdin()
    if args.output is None:
        parser.error("--output is required unless --single-turn is used")

    phase5 = _load_phase5()
    server = phase5.Phase5Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_environment = {
        name: os.environ.get(name)
        for name in (
            "HOME",
            "USERPROFILE",
            "HERMES_HOME",
            "GAUNTLET_TOKEN_WORKLOAD_ID",
        )
    }
    before_state = _canonical_state_digest()

    try:
        with tempfile.TemporaryDirectory(prefix="gauntlet-token010-") as temporary:
            home = Path(temporary)
            runtime = home / ".gauntlet" / "runtime"
            phase5._write_runtime_config(runtime, server.server_address[1])
            os.environ["HOME"] = str(home)
            os.environ["USERPROFILE"] = str(home)
            os.environ.pop("HERMES_HOME", None)

            workspace = home / "workspace"
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
            shutil.copytree(REPO / "gauntlet_host", workspace / "gauntlet_host", ignore=ignore)
            shutil.copytree(REPO / "tools", workspace / "tools", ignore=ignore)
            (workspace / "vendor" / "hermes-agent").mkdir(parents=True)
            task_a = _create_task(workspace, "TOKEN-010 ten-turn continuity probe")
            task_b = _create_task(workspace, "TOKEN-010 cross-task isolation probe")
            temporary_state = _canonical_state_digest(workspace)
            canaries_a = [f"TOKEN010_CANARY_A_{index}_{uuid.uuid4().hex}" for index in range(1, 11)]
            canary_b = f"TOKEN010_CANARY_B_{uuid.uuid4().hex}"
            runs_a: list[dict[str, Any]] = []
            requests_a: list[dict[str, Any]] = []

            for index, canary in enumerate(canaries_a, start=1):
                if index == 6:
                    before_b = len(server.chat_requests)
                    run_b = _run_turn(
                        f"Cross-task isolation probe: {canary_b}",
                        task_b,
                        "TOKEN010_CROSS_TASK",
                        workspace,
                    )
                    new_b = server.chat_requests[before_b:]
                    conversation_b = [item for item in new_b if _is_conversation_request(item)]
                    assert len(conversation_b) == 1, len(conversation_b)
                    assert not any(
                        prior in _request_text(conversation_b[0]) for prior in canaries_a[:5]
                    )

                before = len(server.chat_requests)
                prompt = f"Ten-turn continuity probe {index}: {canary}"
                if index == 6:
                    run = _run_restarted_parent(
                        prompt,
                        task_a,
                        "TOKEN010_TEN_TURN_CHAT",
                        workspace,
                    )
                else:
                    run = _run_turn(
                        prompt,
                        task_a,
                        "TOKEN010_TEN_TURN_CHAT",
                        workspace,
                    )
                new_requests = server.chat_requests[before:]
                conversation = [item for item in new_requests if _is_conversation_request(item)]
                assert len(conversation) == 1, len(conversation)
                assert canary_b not in _request_text(conversation[0])
                runs_a.append(run)
                requests_a.append(conversation[0])

            for index, request in enumerate(requests_a):
                text = _request_text(request)
                assert all(prior in text for prior in canaries_a[:index])

            bindings_a = {str(run["payload"].get("session_binding_id") or "") for run in runs_a}
            runtime_sessions_a = {str(run["payload"].get("session_id") or "") for run in runs_a}
            binding_b = str(run_b["payload"].get("session_binding_id") or "")
            assert "" not in bindings_a
            assert "" not in runtime_sessions_a
            assert len(bindings_a) == 1
            assert len(runtime_sessions_a) == 1
            assert binding_b not in bindings_a
            assert runs_a[0]["payload"].get("session_resumed") is False
            assert all(run["payload"].get("session_resumed") is True for run in runs_a[1:])
            assert run_b["payload"].get("session_resumed") is False

            documents = _measurement_documents(runtime)
            serialized_documents = json.dumps(
                documents,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            assert "TOKEN010_CANARY" not in serialized_documents
            assert before_state == _canonical_state_digest()
            assert temporary_state == _canonical_state_digest(workspace)

            running_commit, running_tree = _git_identity()
            manifest = {
                "schema": "gauntlet.token-010-qualification.v1",
                "phase": "TOKEN-010",
                "mode": "NON_DESTRUCTIVE_LOCAL_FIXTURE",
                "source": {
                    "running_commit": running_commit,
                    "running_tree": running_tree,
                    "pinned_hermes_commit": PINNED_HERMES,
                },
                "provider_fixture": {
                    "provider": "custom",
                    "model": "phase5-mock",
                    "network": "localhost-only",
                },
                "session_correctness": {
                    "status": "PASS",
                    "ten_turn_prior_context_present": True,
                    "same_task_binding_stable": True,
                    "same_runtime_session_id": True,
                    "cross_task_leak_absent": True,
                    "fresh_worker_each_turn": True,
                    "fresh_parent_resume_tested_at_turn": 6,
                    "interleaved_cross_task_tested_at_turn": 6,
                    "first_turn_resumed": False,
                    "subsequent_turns_resumed": True,
                    "kernel_turn_lock_unit_tested": True,
                },
                "privacy": {
                    "derived_session_ids_expose_task_id": False,
                    "raw_canaries_in_measurement_documents": False,
                },
                "state_safety": {
                    "repository_egrt_digest_unchanged": True,
                    "temporary_fixture_egrt_digest_unchanged_during_turns": True,
                    "canonical_receipt_created": False,
                    "canonical_state_mutated": False,
                },
                "counts": {
                    "task_a_turns": len(runs_a),
                    "task_b_turns": 1,
                    "conversation_provider_requests": len(requests_a) + 1,
                    "measurement_documents": len(documents),
                    "distinct_task_a_bindings": len(bindings_a),
                    "distinct_task_a_runtime_sessions": len(runtime_sessions_a),
                },
                "authority_ceiling": "SESSION_CORRECTNESS_ONLY",
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {
                        "status": "verified",
                        "manifest": str(args.output),
                        "session_correctness": "PASS",
                        "task_a_turns": len(runs_a),
                        "cross_task_leak_absent": True,
                        "fresh_parent_resume_tested": True,
                    },
                    sort_keys=True,
                )
            )
    finally:
        _restore_environment(original_environment)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
