"""Non-destructive TOKEN-100/600 qualification on the local provider fixture."""

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
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from gauntlet_host.ipc import WorkerStatus  # noqa: E402
from gauntlet_host.launcher import run_worker_turn  # noqa: E402

PHASE5_HELPER = REPO / ".github" / "phase5_verify.py"
PINNED_HERMES = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
PREFETCH_PROMPT = "Use the parent-prefetched canonical status and answer without calling tools."
BATCH_PROMPT = "Refresh compact task status and release status in one batch, then answer."
STATUS_CALL_ID = "token100-status"
RELEASE_CALL_ID = "token100-release"
LEAN_MARKER = "[GAUNTLET LEAN VOLATILE CONTEXT]"
RAW_CLAIM = "TOKEN100 exact claim must remain out of compact context"


def _load_phase5() -> Any:
    spec = importlib.util.spec_from_file_location("phase5_verify", PHASE5_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the checked-in deterministic provider fixture")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


phase5 = _load_phase5()


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
    return ""


def _latest_user_text(body: dict[str, Any]) -> str:
    messages = body.get("messages", [])
    for message in reversed(messages if isinstance(messages, list) else []):
        if isinstance(message, dict) and message.get("role") == "user":
            return _message_text(message)
    return ""


def _tool_result_ids(body: dict[str, Any]) -> set[str]:
    messages = body.get("messages", [])
    return {
        str(message.get("tool_call_id"))
        for message in messages
        if isinstance(message, dict)
        and message.get("role") == "tool"
        and message.get("tool_call_id")
    }


class LeanServer(phase5.Phase5Server):
    def __init__(self) -> None:
        ThreadingHTTPServer.__init__(self, ("127.0.0.1", 0), LeanHandler)
        self.lock = threading.Lock()
        self.chat_requests: list[dict[str, Any]] = []


class LeanHandler(phase5.Phase5Handler):
    @property
    def lean_server(self) -> LeanServer:
        return self.server  # type: ignore[return-value]

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        if not path.endswith("/chat/completions"):
            self._send_json({"ok": True})
            return

        server = self.lean_server
        with server.lock:
            server.chat_requests.append(body)

        created = int(time.time())
        latest = _latest_user_text(body)
        result_ids = _tool_result_ids(body)
        if (
            BATCH_PROMPT in latest
            and {
                STATUS_CALL_ID,
                RELEASE_CALL_ID,
            }
            <= result_ids
        ):
            self._final_response(body, created, "batch refresh observed")
        elif BATCH_PROMPT in latest:
            self._batch_tool_response(body, created)
        elif PREFETCH_PROMPT in latest:
            self._final_response(body, created, "prefetch observed")
        else:
            self._final_response(body, created, "lean auxiliary response")

    @staticmethod
    def _calls() -> list[dict[str, Any]]:
        return [
            {
                "id": STATUS_CALL_ID,
                "type": "function",
                "function": {
                    "name": "gauntlet_task_status_compact",
                    "arguments": "{}",
                },
            },
            {
                "id": RELEASE_CALL_ID,
                "type": "function",
                "function": {
                    "name": "gauntlet_release_status",
                    "arguments": "{}",
                },
            },
        ]

    def _batch_tool_response(self, body: dict[str, Any], created: int) -> None:
        calls = self._calls()
        if body.get("stream"):
            self._send_stream(
                [
                    {
                        "id": "chatcmpl-token100-tools",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "phase5-mock",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "tool_calls": [
                                        {"index": index, **call} for index, call in enumerate(calls)
                                    ],
                                },
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        "id": "chatcmpl-token100-tools",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "phase5-mock",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "finish_reason": "tool_calls",
                            }
                        ],
                    },
                    self._usage(created),
                ]
            )
            return
        self._send_json(
            {
                "id": "chatcmpl-token100-tools",
                "object": "chat.completion",
                "created": created,
                "model": "phase5-mock",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": calls,
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            }
        )


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


def _create_task(root: Path) -> tuple[str, str]:
    task = _json_run(
        [
            sys.executable,
            str(REPO / "tools" / "soul_runtime.py"),
            "--root",
            str(root),
            "start",
            "--goal",
            "TOKEN-100/600 lean runtime qualification",
        ]
    )
    task_id = str(task["task_id"])
    obligation = _json_run(
        [
            sys.executable,
            str(REPO / "tools" / "soul_runtime.py"),
            "--root",
            str(root),
            "add",
            task_id,
            "DISCOVERY",
            "--claim",
            RAW_CLAIM,
        ]
    )
    return task_id, str(obligation["obligation_id"])


def _canonical_state_digest(workspace_root: Path) -> str:
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


def _conversation_requests(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in requests
        if item.get("stream") is True and isinstance(item.get("tools"), list)
    ]


def _tool_names(request: dict[str, Any]) -> set[str]:
    return {
        str(item.get("function", {}).get("name"))
        for item in request.get("tools", [])
        if isinstance(item, dict) and isinstance(item.get("function"), dict)
    }


def _user_texts(request: dict[str, Any]) -> list[str]:
    return [
        _message_text(message)
        for message in request.get("messages", [])
        if isinstance(message, dict) and message.get("role") == "user"
    ]


def _system_text(request: dict[str, Any]) -> str:
    return "\n".join(
        _message_text(message)
        for message in request.get("messages", [])
        if isinstance(message, dict) and message.get("role") == "system"
    )


def _tool_results(request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for message in request.get("messages", []):
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        call_id = message.get("tool_call_id")
        if call_id not in {STATUS_CALL_ID, RELEASE_CALL_ID}:
            continue
        results[str(call_id)] = json.loads(_message_text(message))
    return results


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


def _restore_environment(original: dict[str, str | None]) -> None:
    for name, value in original.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    manifest_snapshot = json.loads(
        (REPO / "vendor" / "HERMES_SNAPSHOT.json").read_text(encoding="utf-8")
    )
    assert manifest_snapshot["upstream_commit"] == PINNED_HERMES
    submodule_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO / "vendor" / "hermes-agent",
        text=True,
        encoding="utf-8",
    ).strip()
    assert submodule_commit == PINNED_HERMES

    server = LeanServer()
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
    repository_state_before = _canonical_state_digest(REPO)

    try:
        with tempfile.TemporaryDirectory(prefix="gauntlet-token100-") as temporary:
            home = Path(temporary)
            runtime = home / ".gauntlet" / "runtime"
            phase5._write_runtime_config(runtime, server.server_address[1])
            os.environ["HOME"] = str(home)
            os.environ["USERPROFILE"] = str(home)
            os.environ.pop("HERMES_HOME", None)
            os.environ["GAUNTLET_TOKEN_WORKLOAD_ID"] = "TOKEN100_600_LIVE"

            workspace = home / "workspace"
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
            shutil.copytree(
                REPO / "gauntlet_host",
                workspace / "gauntlet_host",
                ignore=ignore,
            )
            shutil.copytree(REPO / "tools", workspace / "tools", ignore=ignore)
            (workspace / "vendor" / "hermes-agent").mkdir(parents=True)
            task_id, obligation_id = _create_task(workspace)
            workspace_state_before = _canonical_state_digest(workspace)

            first = run_worker_turn(
                PREFETCH_PROMPT,
                task_id=task_id,
                cwd=workspace,
                model="phase5-mock",
                provider="custom",
                timeout_seconds=180,
            )
            if first.status is not WorkerStatus.OK:
                raise AssertionError(
                    {
                        "worker_error": str(first.error or first),
                        "provider_requests": len(server.chat_requests),
                    }
                )
            before_second = len(server.chat_requests)
            second = run_worker_turn(
                BATCH_PROMPT,
                task_id=task_id,
                cwd=workspace,
                model="phase5-mock",
                provider="custom",
                timeout_seconds=180,
            )
            if second.status is not WorkerStatus.OK:
                raise AssertionError(
                    {
                        "worker_error": str(second.error or second),
                        "provider_requests": len(server.chat_requests),
                    }
                )

            requests = _conversation_requests(server.chat_requests)
            first_requests = _conversation_requests(server.chat_requests[:before_second])
            second_requests = _conversation_requests(server.chat_requests[before_second:])
            assert len(first_requests) == 1, len(first_requests)
            assert len(second_requests) == 2, len(second_requests)
            assert len(requests) == 3, len(requests)

            active_names = _tool_names(first_requests[0])
            assert active_names == {
                "gauntlet_task_status_compact",
                "gauntlet_obligation_get",
                "gauntlet_release_status",
            }
            assert all(_tool_names(request) == active_names for request in requests)

            first_user = _user_texts(first_requests[0])
            assert len(first_user) == 1
            assert first_user[0].startswith(PREFETCH_PROMPT + "\n\n")
            assert first_user[0].count(LEAN_MARKER) == 1
            assert RAW_CLAIM not in first_user[0]
            assert '"required_module"' in first_user[0]
            assert '"space"' in first_user[0]

            second_user = _user_texts(second_requests[0])
            assert second_user[0] == PREFETCH_PROMPT, second_user
            assert second_user[-1].startswith(BATCH_PROMPT + "\n\n")
            assert "".join(second_user).count(LEAN_MARKER) == 1
            assert RAW_CLAIM not in "".join(second_user)
            assert _system_text(first_requests[0]) == _system_text(second_requests[0])

            results = _tool_results(second_requests[1])
            assert set(results) == {STATUS_CALL_ID, RELEASE_CALL_ID}
            compact = results[STATUS_CALL_ID]
            release = results[RELEASE_CALL_ID]
            assert compact["action"] == "task-status-compact"
            assert compact["compact_status"]["task_id"] == task_id
            assert RAW_CLAIM not in json.dumps(compact)
            assert release["action"] == "release-status"
            assert release["release"]["verdict"] == "UNKNOWN"
            assert compact["read_only"] is True
            assert release["read_only"] is True
            assert compact["mutation_performed"] is False
            assert release["mutation_performed"] is False

            assert first.payload["usage"]["api_calls"] == 1
            assert second.payload["usage"]["api_calls"] == 2
            assert first.payload["final_response"] == "prefetch observed"
            assert second.payload["final_response"] == "batch refresh observed"
            assert first.payload["session_resumed"] is False
            assert second.payload["session_resumed"] is True
            assert second.payload["stale_lean_context_rows_dropped"] == 1
            first_lean = first.payload["lean_context"]
            second_lean = second.payload["lean_context"]
            assert first_lean["prefetched_by_parent"] is True
            assert first_lean["extra_model_calls"] == 0
            assert first_lean["capsule_metrics"]["route_estimated_tokens"] <= 512
            assert first_lean["capsule_metrics"]["status_estimated_tokens"] <= 1024
            assert set(first_lean["route_capsule"]) == {
                "route_hash",
                "route_revision",
                "primary_mode",
                "selected_capability_ids",
                "required_verifier_ids",
                "missing_capability_ids",
                "should_stop",
            }
            assert first_lean["active_manifest_hash"] == second_lean["active_manifest_hash"]
            assert first_lean["route_record_path"] == second_lean["route_record_path"]
            route_record = Path(first_lean["route_record_path"])
            assert route_record.is_file()
            route = json.loads(route_record.read_text(encoding="utf-8"))
            assert route["content_hash"] == first_lean["route_capsule"]["route_hash"]
            assert route["capability_snapshot"]["source"] == (
                "PARENT_COMPILED_GAUNTLET_STATUS_MANIFEST"
            )

            import yaml

            config = yaml.safe_load((runtime / "config.yaml").read_text())
            assert config["toolsets"] == ["gauntlet"]
            assert config["memory"]["memory_enabled"] is False
            assert config["memory"]["user_profile_enabled"] is False
            assert config["memory"]["provider"] == ""
            assert config["skills"]["project_discovery"] is False
            assert config["skills"]["external_dirs"] == []
            assert config["agent"]["execution_guidance"] is False
            assert config["agent"]["task_completion_guidance"] is False
            assert config["agent"]["parallel_tool_call_guidance"] is True
            assert config["agent"]["coding_context"] == "off"
            assert config["agent"]["intent_ack_continuation"] is False
            assert not (home / ".hermes").exists()

            assert workspace_state_before == _canonical_state_digest(workspace)
            assert repository_state_before == _canonical_state_digest(REPO)
            assert not any((workspace / ".egrt" / "state" / "runtime" / "receipts").glob("*.json"))

            running_commit, running_tree = _git_identity()
            manifest = {
                "schema": "gauntlet.token-100-600-qualification.v1",
                "phases": ["TOKEN-100", "TOKEN-600"],
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
                "gates": {
                    "status": "PASS",
                    "parent_prefetch_before_first_model_call": True,
                    "first_turn_status_tool_calls": 0,
                    "foil_extra_model_calls": 0,
                    "independent_refresh_calls_batched": True,
                    "deterministic_required_module_injected": True,
                    "stable_system_prompt_bytes": True,
                    "volatile_context_not_persisted": True,
                    "active_manifest_frozen": True,
                    "route_capsule_fields_exact": True,
                    "route_capsule_estimated_tokens": first_lean["capsule_metrics"][
                        "route_estimated_tokens"
                    ],
                    "compact_status_estimated_tokens": first_lean["capsule_metrics"][
                        "status_estimated_tokens"
                    ],
                    "full_route_content_addressed": True,
                    "exact_claim_absent_from_compact_context": True,
                    "exact_obligation_tool_available": True,
                    "memory_profile_reads_disabled": True,
                    "skills_discovery_disabled": True,
                    "unused_guidance_disabled": True,
                    "parallel_batch_guidance_enabled": True,
                    "canonical_state_unchanged": True,
                    "canonical_receipts_created": 0,
                },
                "counts": {
                    "turns": 2,
                    "provider_requests": len(requests),
                    "first_turn_provider_requests": len(first_requests),
                    "batch_refresh_provider_requests": len(second_requests),
                    "model_visible_tools": len(active_names),
                    "task_obligations": 1,
                },
                "task_id": task_id,
                "obligation_id": obligation_id,
                "authority_ceiling": "TOKEN_EFFICIENCY_ONLY",
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
                        "provider_requests": len(requests),
                        "first_turn_status_tool_calls": 0,
                        "batched_refresh": True,
                        "route_tokens_estimated": first_lean["capsule_metrics"][
                            "route_estimated_tokens"
                        ],
                        "status_tokens_estimated": first_lean["capsule_metrics"][
                            "status_estimated_tokens"
                        ],
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
