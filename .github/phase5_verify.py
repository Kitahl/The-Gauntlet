"""Temporary bounded Phase 5 verification harness."""

from __future__ import annotations

import ast
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"
TASKS = REPO / ".egrt" / "state" / "runtime" / "tasks"
EVENTS = REPO / ".egrt" / "state" / "runtime" / "events"
RECEIPTS = REPO / ".egrt" / "state" / "runtime" / "receipts"
TARGET_PROMPT = "Use gauntlet_task_status"
TARGET_CALL_ID = "call-phase5-status"


def _json_run(command: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"command failed ({completed.returncode}): {command}\n{completed.stderr}"
        )
    return json.loads(completed.stdout)


def _source_boundary() -> None:
    subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "gauntlet_host"],
        cwd=REPO,
        check=True,
    )
    violations: list[str] = []
    for path in sorted((REPO / "gauntlet_host").glob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if len(line) > 100:
                violations.append(f"{path.relative_to(REPO)}:{number}:{len(line)}")
    assert not violations, "lines over 100 characters:\n" + "\n".join(violations)

    plugin_tree = ast.parse(
        (REPO / "gauntlet_host" / "gauntlet_plugin.py").read_text(encoding="utf-8")
    )
    adapter_tree = ast.parse(
        (REPO / "gauntlet_host" / "module_cli.py").read_text(encoding="utf-8")
    )
    forbidden_imports = {"egrt_store", "soul_runtime", "tools"}
    for node in ast.walk(plugin_tree):
        if isinstance(node, ast.Import):
            assert not forbidden_imports.intersection(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_imports
    for node in ast.walk(adapter_tree):
        if isinstance(node, ast.Name):
            assert node.id not in {"release_task", "write_receipt"}
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"release_task", "write_receipt"}


def _create_task() -> str:
    subprocess.run(["rm", "-rf", ".egrt"], cwd=REPO, check=True)
    task = _json_run(
        [
            sys.executable,
            str(TOOLS / "soul_runtime.py"),
            "--root",
            str(REPO),
            "start",
            "--goal",
            "Phase 5 read-only status verification",
        ]
    )
    task_id = task["task_id"]
    _json_run(
        [
            sys.executable,
            str(TOOLS / "soul_runtime.py"),
            "--root",
            str(REPO),
            "add",
            task_id,
            "DISCOVERY",
            "--claim",
            "Find a canonical source before release.",
        ]
    )
    return task_id


def _message_content(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(item.get("text") or "")
            for item in content
            if isinstance(item, dict)
        )
    return ""


def _has_target_prompt(body: dict[str, Any]) -> bool:
    return any(
        TARGET_PROMPT in _message_content(message)
        for message in body.get("messages", [])
        if isinstance(message, dict)
    )


def _has_target_tool_result(body: dict[str, Any]) -> bool:
    return any(
        message.get("role") == "tool"
        and message.get("tool_call_id") == TARGET_CALL_ID
        for message in body.get("messages", [])
        if isinstance(message, dict)
    )


def _exposes_status_tool(body: dict[str, Any]) -> bool:
    return any(
        isinstance(tool, dict)
        and tool.get("function", {}).get("name") == "gauntlet_task_status"
        for tool in body.get("tools", [])
    )


class Phase5Server(ThreadingHTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), Phase5Handler)
        self.lock = threading.Lock()
        self.chat_requests: list[dict[str, Any]] = []


class Phase5Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def phase5_server(self) -> Phase5Server:
        return self.server  # type: ignore[return-value]

    def _send_json(self, value: dict[str, Any]) -> None:
        data = json.dumps(value).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_stream(self, chunks: list[dict[str, Any]]) -> None:
        body = "".join(
            f"data: {json.dumps(chunk)}\n\n"
            for chunk in chunks
        ) + "data: [DONE]\n\n"
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        model = {
            "id": "phase5-mock",
            "object": "model",
            "owned_by": "gauntlet-phase5",
            "context_length": 131072,
        }
        if path.endswith("/models"):
            self._send_json({"object": "list", "data": [model]})
        elif "/models/" in path:
            self._send_json(model)
        else:
            self._send_json({"ok": True})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        if not path.endswith("/chat/completions"):
            self._send_json({"ok": True})
            return

        server = self.phase5_server
        with server.lock:
            server.chat_requests.append(body)

        created = int(time.time())
        if _has_target_tool_result(body):
            self._final_response(body, created, "phase5 status observed")
        elif _has_target_prompt(body) and _exposes_status_tool(body):
            self._tool_call_response(body, created)
        else:
            self._final_response(body, created, "phase5 auxiliary response")

    def _usage(self, created: int) -> dict[str, Any]:
        return {
            "id": "chatcmpl-phase5",
            "object": "chat.completion.chunk",
            "created": created,
            "model": "phase5-mock",
            "choices": [],
            "usage": {
                "prompt_tokens": 16,
                "completion_tokens": 6,
                "total_tokens": 22,
            },
        }

    def _tool_call_response(self, body: dict[str, Any], created: int) -> None:
        call = {
            "id": TARGET_CALL_ID,
            "type": "function",
            "function": {
                "name": "gauntlet_task_status",
                "arguments": "{}",
            },
        }
        if body.get("stream"):
            self._send_stream(
                [
                    {
                        "id": "chatcmpl-phase5",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "phase5-mock",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "tool_calls": [{"index": 0, **call}],
                                },
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        "id": "chatcmpl-phase5",
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
                "id": "chatcmpl-phase5",
                "object": "chat.completion",
                "created": created,
                "model": "phase5-mock",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [call],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            }
        )

    def _final_response(
        self,
        body: dict[str, Any],
        created: int,
        final: str,
    ) -> None:
        if body.get("stream"):
            self._send_stream(
                [
                    {
                        "id": "chatcmpl-phase5-final",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "phase5-mock",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": final,
                                },
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        "id": "chatcmpl-phase5-final",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "phase5-mock",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop",
                            }
                        ],
                    },
                    self._usage(created),
                ]
            )
            return
        self._send_json(
            {
                "id": "chatcmpl-phase5-final",
                "object": "chat.completion",
                "created": created,
                "model": "phase5-mock",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": final},
                        "finish_reason": "stop",
                    }
                ],
            }
        )


def _write_runtime_config(runtime: Path, port: int) -> None:
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "config.yaml").write_text(
        f"""model:
  default: phase5-mock
  provider: custom
  base_url: http://127.0.0.1:{port}/v1
  api_key: local-phase5-key
  api_mode: chat_completions
  context_length: 131072
agent:
  api_max_retries: 1
  tool_use_enforcement: false
  execution_guidance: false
  task_completion_guidance: false
  parallel_tool_call_guidance: false
  coding_context: off
  verify_on_stop: false
tools:
  tool_search:
    enabled: off
toolsets: []
plugins:
  enabled: []
  disabled:
    - gauntlet
auxiliary:
  background_review:
    enabled: true
memory:
  write_approval: false
skills:
  write_approval: false
""",
        encoding="utf-8",
    )


def _task_state(task_id: str) -> dict[str, Any]:
    task_path = TASKS / f"{task_id}.json"
    return {
        "task_sha256": hashlib.sha256(task_path.read_bytes()).hexdigest(),
        "events": sorted(path.name for path in EVENTS.glob("*.json")),
    }


def _tool_request(requests: list[dict[str, Any]]) -> dict[str, Any]:
    for request in requests:
        if _has_target_prompt(request) and _exposes_status_tool(request):
            return request
    raise AssertionError("no target model request exposed gauntlet_task_status")


def _result_request(requests: list[dict[str, Any]]) -> dict[str, Any]:
    for request in requests:
        if _has_target_tool_result(request):
            return request
    raise AssertionError("no target model request contained the Gauntlet tool result")


def main() -> None:
    _source_boundary()
    task_id = _create_task()
    before = _task_state(task_id)
    server = Phase5Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with tempfile.TemporaryDirectory(prefix="gauntlet-phase5-") as temporary:
            home = Path(temporary)
            runtime = home / ".gauntlet" / "runtime"
            _write_runtime_config(runtime, server.server_address[1])
            environment = dict(os.environ)
            environment.update(
                {
                    "HOME": str(home),
                    "HERMES_YOLO_MODE": "1",
                    "HERMES_ACCEPT_HOOKS": "1",
                    "HERMES_INTERACTIVE": "1",
                }
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gauntlet_host.launcher",
                    "Use gauntlet_task_status, then report that status was observed.",
                    "--task-id",
                    task_id,
                    "--model",
                    "phase5-mock",
                    "--provider",
                    "custom",
                    "--timeout",
                    "90",
                    "--json",
                ],
                cwd=REPO,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            print(completed.stdout, end="")
            if completed.stderr:
                print(completed.stderr, file=sys.stderr, end="")
            assert completed.returncode == 0
            result = json.loads(completed.stdout)

            assert result["status"] == "OK"
            assert result["event"] == "worker.turn_completed"
            assert result["task_id"] == task_id
            assert result["payload"]["final_response"] == "phase5 status observed"
            assert result["payload"]["usage"]["api_calls"] == 2

            tool_request = _tool_request(server.chat_requests)
            result_request = _result_request(server.chat_requests)
            names = {
                item["function"]["name"]
                for item in tool_request.get("tools", [])
            }
            assert {"gauntlet_task_status", "gauntlet_release_status"} <= names
            tool_messages = [
                message
                for message in result_request.get("messages", [])
                if message.get("tool_call_id") == TARGET_CALL_ID
            ]
            assert len(tool_messages) == 1
            status = json.loads(tool_messages[0]["content"])
            assert status["schema"] == "gauntlet.adapter.v1"
            assert status["action"] == "task-status"
            assert status["status"] == "OK"
            assert status["task_id"] == task_id
            assert status["task"]["task_id"] == task_id
            assert status["release"]["verdict"] == "UNKNOWN"
            assert status["release"]["release_eligible"] is False
            assert status["read_only"] is True
            assert status["mutation_performed"] is False
            assert all(value is False for value in status["authority"].values())

            import yaml

            config = yaml.safe_load((runtime / "config.yaml").read_text())
            assert "gauntlet" in config["plugins"]["enabled"]
            assert "gauntlet" not in config["plugins"]["disabled"]
            assert config["auxiliary"]["background_review"]["enabled"] is False
            assert config["memory"]["write_approval"] is True
            assert config["skills"]["write_approval"] is True
            plugin = runtime / "plugins" / "gauntlet"
            assert (plugin / "plugin.yaml").is_file()
            assert (plugin / "__init__.py").read_bytes() == (
                REPO / "gauntlet_host" / "gauntlet_plugin.py"
            ).read_bytes()
            assert not (home / ".hermes").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    after = _task_state(task_id)
    task = json.loads((TASKS / f"{task_id}.json").read_text())
    assert after == before
    assert task["active"] is True
    assert task["released"] is False
    assert not any(RECEIPTS.glob("*.json"))
    print(
        json.dumps(
            {
                "phase": 5,
                "status": "verified",
                "task_id": task_id,
                "chat_requests_observed": len(server.chat_requests),
                "release_verdict": "UNKNOWN",
                "release_mutation": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
