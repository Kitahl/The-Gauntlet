"""Prospectively frozen TOKEN-700 matched local qualification.

This driver executes two exact Git commits from isolated temporary worktrees against one
deterministic localhost provider. It persists privacy-safe numeric projections, never raw
provider requests or responses. See the preregistration before changing this file.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO / "benchmarks" / "token700" / "workloads.v1.json"
MANIFEST_SHA256 = "70adbd24ab90d2ac9962da9e6f87b34cd9b2c089ea6db89d13b3d5174b77a4bf"
PREREGISTRATION_COMMIT = "503818e723f4b6625ef39459d8e2126afa9fe2cf"
PINNED_HERMES = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
MODEL = "phase5-mock"
PROVIDER = "custom"
TURN_TIMEOUT_SECONDS = 90
OUTER_TIMEOUT_SECONDS = 120
CASE_PATTERN = re.compile(r"TOKEN700\|(W\d{2}-S\d{2})\|(T\d{2})\|")
CASE_ID_PATTERN = re.compile(r"W\d{2}-S\d{2}")

ARMS = {
    "baseline": {
        "commit": "4e455e4dcddc329a6d2455676fdfc78a17338523",
        "tree": "17225910e1962b18b652e922c01e897f707f5eb1",
        "evidence_commit": "d00e8e5a69cad022bc9a5cb701d3addcaeabfb81",
    },
    "candidate": {
        "commit": "dcb63f1acf3b7aeab09e065fa116cbc32c5a18cb",
        "tree": "ec1fdf9385a16e878d4a8746aaec3cac6f8f85ed",
        "evidence_commit": "31c4080482a15624e422d30ce3c0a980b719ced9",
    },
}

RUNNER_SOURCE = r"""
import json
import sys
from pathlib import Path

from gauntlet_host.finalizer import finalize_worker_result
from gauntlet_host.ipc import encode_result
from gauntlet_host.launcher import run_worker_turn

prompt, task_id, root = sys.argv[1], sys.argv[2], Path(sys.argv[3])
worker = run_worker_turn(
    prompt,
    task_id=task_id,
    cwd=root,
    model="phase5-mock",
    provider="custom",
    timeout_seconds=90,
)
finalization = finalize_worker_result(root, task_id, worker)
print(json.dumps({
    "worker": json.loads(encode_result(worker)),
    "finalization": finalization.to_dict(),
}, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
"""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _git(*args: str, cwd: Path = REPO, timeout: int = 30) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def _json_command(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("JSON command returned a non-object")
    return value


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if _sha256_file(path) != MANIFEST_SHA256:
        raise ValueError("TOKEN-700 workload manifest hash mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("TOKEN-700 workload manifest must be an object")
    if value.get("schema") != "gauntlet.token700-workloads.v1":
        raise ValueError("TOKEN-700 workload manifest schema mismatch")
    workloads = value.get("workloads")
    variants = value.get("variants")
    if not isinstance(workloads, list) or len(workloads) != 10:
        raise ValueError("TOKEN-700 requires exactly ten workload classes")
    if variants != ["S01", "S02", "S03"]:
        raise ValueError("TOKEN-700 requires the three frozen variants")
    identifiers = [item.get("id") for item in workloads if isinstance(item, dict)]
    if identifiers != [f"W{number:02d}" for number in range(1, 11)]:
        raise ValueError("TOKEN-700 workload identifiers or order changed")
    if value.get("sample_size_pairs") != 30:
        raise ValueError("TOKEN-700 frozen sample size changed")
    return value


def expand_cases(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for workload in manifest["workloads"]:
        for variant in manifest["variants"]:
            cases.append(
                {
                    "case_id": f"{workload['id']}-{variant}",
                    "variant": variant,
                    "workload": workload,
                }
            )
    if len(cases) != manifest["sample_size_pairs"]:
        raise ValueError("expanded TOKEN-700 case count differs from frozen sample size")
    return cases


def expand_turns(case: Mapping[str, Any]) -> list[dict[str, str]]:
    workload = case["workload"]
    case_id = str(case["case_id"])
    explicit = workload.get("turns")
    if isinstance(explicit, list):
        return [
            {
                "turn_id": str(turn["turn_id"]),
                "provider_action": str(turn["provider_action"]),
                "prompt": str(turn["prompt_template"]).format(case_id=case_id),
            }
            for turn in explicit
        ]
    generator = workload["turn_generator"]
    turns = []
    for number in range(1, int(workload["turn_count"]) + 1):
        template = (
            generator.get("first_prompt_template") if number == 1 else generator["prompt_template"]
        )
        turns.append(
            {
                "turn_id": f"T{number:02d}",
                "provider_action": str(generator["provider_action"]),
                "prompt": str(template).format(
                    case_id=case_id,
                    turn_number=number,
                    turn_number_2d=f"{number:02d}",
                ),
            }
        )
    return turns


def paired_reduction(baseline: float, candidate: float) -> float:
    if baseline <= 0:
        raise ValueError("baseline cost must be positive")
    return (baseline - candidate) / baseline


def median(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def finite_suite_noninferiority(
    pairs: Sequence[tuple[bool, bool]],
) -> dict[str, Any]:
    regressions = sum(baseline and not candidate for baseline, candidate in pairs)
    improvements = sum(not baseline and candidate for baseline, candidate in pairs)
    baseline_correct = sum(baseline for baseline, _ in pairs)
    candidate_correct = sum(candidate for _, candidate in pairs)
    return {
        "n_pairs": len(pairs),
        "margin_percentage_points": 0,
        "baseline_correct": baseline_correct,
        "candidate_correct": candidate_correct,
        "regressions": regressions,
        "improvements": improvements,
        "passed": (bool(pairs) and regressions == 0 and candidate_correct >= baseline_correct),
        "scope": "finite_frozen_suite_only",
        "population_inference": False,
    }


def _message_content(message: Mapping[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
    return ""


def _messages(body: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = body.get("messages")
    if not isinstance(value, list):
        value = body.get("input")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _request_text(body: Mapping[str, Any]) -> str:
    return "\n".join(_message_content(message) for message in _messages(body))


def _latest_user_text(body: Mapping[str, Any]) -> str:
    for message in reversed(_messages(body)):
        if message.get("role") == "user":
            return _message_content(message)
    return ""


def _tool_names(body: Mapping[str, Any]) -> list[str]:
    names = []
    for tool in body.get("tools", []):
        if not isinstance(tool, dict):
            continue
        function = tool.get("function")
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            names.append(function["name"])
    return sorted(set(names))


def _tool_results(body: Mapping[str, Any]) -> list[dict[str, Any]]:
    results = []
    for message in _messages(body):
        if message.get("role") != "tool":
            continue
        content = _message_content(message)
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            results.append(value)
    return results


class Token700Server(ThreadingHTTPServer):
    def __init__(self, actions: Mapping[str, str]) -> None:
        super().__init__(("127.0.0.1", 0), Token700Handler)
        self.actions = dict(actions)
        self.lock = threading.Lock()
        self.chat_requests: list[dict[str, Any]] = []

    def append(self, body: dict[str, Any]) -> None:
        with self.lock:
            self.chat_requests.append(body)

    def snapshot(self) -> int:
        with self.lock:
            return len(self.chat_requests)

    def since(self, index: int) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.chat_requests[index:])


class Token700Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    @property
    def fixture(self) -> Token700Server:
        return self.server  # type: ignore[return-value]

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, value: Mapping[str, Any]) -> None:
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_stream(self, chunks: Sequence[Mapping[str, Any]]) -> None:
        body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
        data = (body + "data: [DONE]\n\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        model = {
            "id": MODEL,
            "object": "model",
            "owned_by": "gauntlet-token700",
            "context_length": 131072,
        }
        if path.endswith("/models"):
            self._send_json({"object": "list", "data": [model]})
        elif "/models/" in path:
            self._send_json(model)
        else:
            self._send_json({"ok": True})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(body, dict):
            self._send_json({"error": "request must be an object"})
            return
        if not urlparse(self.path).path.endswith("/chat/completions"):
            self._send_json({"ok": True})
            return
        self.fixture.append(body)
        match = CASE_PATTERN.search(_latest_user_text(body))
        if match is None:
            self._send_final(body, "TOKEN700_PROTOCOL_ERROR:no-case-marker")
            return
        case_id, turn_id = match.groups()
        action = self.fixture.actions.get(case_id)
        if action is None:
            self._send_final(body, f"TOKEN700_PROTOCOL_ERROR:{case_id}:{turn_id}")
            return
        if action == "STATUS_THEN_FINAL" and not _tool_results(body):
            self._send_status_call(body, case_id, turn_id)
            return
        prefix = "TOKEN700_UNAVAILABLE" if action == "UNAVAILABLE_FINAL" else "TOKEN700_OK"
        self._send_final(body, f"{prefix}:{case_id}:{turn_id}")

    def _usage(self, body: Mapping[str, Any], completion: str) -> dict[str, int]:
        prompt_tokens = max(1, math.ceil(len(_canonical(body)) / 4))
        completion_tokens = max(1, math.ceil(len(completion.encode("utf-8")) / 4))
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "prompt_tokens_details": {"cached_tokens": 0},
        }

    def _send_status_call(self, body: Mapping[str, Any], case_id: str, turn_id: str) -> None:
        names = _tool_names(body)
        if "gauntlet_task_status_compact" in names:
            name = "gauntlet_task_status_compact"
        elif "gauntlet_task_status" in names:
            name = "gauntlet_task_status"
        else:
            self._send_final(body, f"TOKEN700_PROTOCOL_ERROR:{case_id}:{turn_id}:no-status")
            return
        call_id = f"call-{case_id.lower()}-{turn_id.lower()}"
        call = {
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": "{}"},
        }
        created = int(time.time())
        if body.get("stream"):
            self._send_stream(
                [
                    {
                        "id": "chatcmpl-token700-tool",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": MODEL,
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
                        "id": "chatcmpl-token700-tool",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": MODEL,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                    },
                    {
                        "id": "chatcmpl-token700-tool",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": MODEL,
                        "choices": [],
                        "usage": self._usage(body, json.dumps(call, sort_keys=True)),
                    },
                ]
            )
            return
        self._send_json(
            {
                "id": "chatcmpl-token700-tool",
                "object": "chat.completion",
                "created": created,
                "model": MODEL,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": None, "tool_calls": [call]},
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": self._usage(body, json.dumps(call, sort_keys=True)),
            }
        )

    def _send_final(self, body: Mapping[str, Any], final: str) -> None:
        created = int(time.time())
        if body.get("stream"):
            self._send_stream(
                [
                    {
                        "id": "chatcmpl-token700-final",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": MODEL,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": final},
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        "id": "chatcmpl-token700-final",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": MODEL,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    },
                    {
                        "id": "chatcmpl-token700-final",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": MODEL,
                        "choices": [],
                        "usage": self._usage(body, final),
                    },
                ]
            )
            return
        self._send_json(
            {
                "id": "chatcmpl-token700-final",
                "object": "chat.completion",
                "created": created,
                "model": MODEL,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": final},
                        "finish_reason": "stop",
                    }
                ],
                "usage": self._usage(body, final),
            }
        )


def _assert_inside(path: Path, root: Path) -> None:
    if not path.resolve(strict=False).is_relative_to(root.resolve()):
        raise RuntimeError(f"temporary path escaped evaluation root: {path}")


def _extract_pinned_hermes(destination: Path) -> None:
    source = REPO / "vendor" / "hermes-agent"
    if _git("status", "--porcelain", cwd=source):
        raise RuntimeError("pinned Hermes checkout is dirty")
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar", PINNED_HERMES],
        cwd=source,
    )
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        for member in bundle.getmembers():
            target = (destination / member.name).resolve(strict=False)
            if not target.is_relative_to(destination.resolve()):
                raise RuntimeError("Hermes archive contains an unsafe path")
        bundle.extractall(destination, filter="data")


@contextmanager
def exact_worktrees(root: Path) -> Iterator[dict[str, Path]]:
    paths = {"baseline": root / "arm-a", "candidate": root / "arm-b"}
    added: list[Path] = []
    try:
        for arm, path in paths.items():
            _assert_inside(path, root)
            _git("worktree", "add", "--detach", str(path), ARMS[arm]["commit"], timeout=60)
            added.append(path)
            commit = _git("rev-parse", "HEAD^{commit}", cwd=path)
            tree = _git("rev-parse", "HEAD^{tree}", cwd=path)
            gitlink = _git("ls-tree", "HEAD", "vendor/hermes-agent", cwd=path).split()[2]
            if commit != ARMS[arm]["commit"] or tree != ARMS[arm]["tree"]:
                raise RuntimeError(f"{arm} worktree identity mismatch")
            if gitlink != PINNED_HERMES:
                raise RuntimeError(f"{arm} Hermes gitlink mismatch")
            _extract_pinned_hermes(path / "vendor" / "hermes-agent")
        yield paths
    finally:
        for path in reversed(added):
            _assert_inside(path, root)
            if path.exists():
                vendor = path / "vendor" / "hermes-agent"
                if vendor.exists():
                    shutil.rmtree(vendor)
            try:
                _git("worktree", "remove", "--force", str(path), timeout=60)
            except RuntimeError:
                pass
        try:
            _git("worktree", "prune")
        except RuntimeError:
            pass


def _prepare_tasks(root: Path, cases: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    task_ids: dict[str, str] = {}
    tool = REPO / "tools" / "soul_runtime.py"
    for case in cases:
        case_id = str(case["case_id"])
        started = _json_command(
            [
                sys.executable,
                str(tool),
                "--root",
                str(root),
                "start",
                "--goal",
                f"TOKEN-700 frozen workload {case_id}",
            ],
            cwd=REPO,
        )
        task_id = str(started["task_id"])
        for obligation in case["workload"]["obligations"]:
            _json_command(
                [
                    sys.executable,
                    str(tool),
                    "--root",
                    str(root),
                    "add",
                    task_id,
                    str(obligation["kind"]),
                    "--claim",
                    str(obligation["claim_template"]).format(case_id=case_id),
                ],
                cwd=REPO,
            )
        task_ids[case_id] = task_id
    return task_ids


def _state_digest(root: Path) -> str:
    base = root / ".egrt" / "state" / "runtime"
    rows = []
    for relative in ("tasks", "events", "receipts"):
        directory = base / relative
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            rows.append(
                {
                    "path": str(path.relative_to(base)).replace("\\", "/"),
                    "sha256": _sha256_file(path),
                }
            )
    return _sha256_bytes(_canonical(rows))


def _write_runtime_config(runtime: Path, port: int) -> None:
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "config.yaml").write_text(
        f"""model:
  default: {MODEL}
  provider: custom
  base_url: http://127.0.0.1:{port}/v1
  api_key: local-token700-key
  api_mode: chat_completions
  context_length: 131072
  max_tokens: 256
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
  disabled: []
auxiliary:
  background_review:
    enabled: false
memory:
  write_approval: false
skills:
  write_approval: false
""",
        encoding="utf-8",
        newline="\n",
    )


def _arm_environment(home: Path, case_id: str) -> dict[str, str]:
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    environment["USERPROFILE"] = str(home)
    environment["GAUNTLET_TOKEN_WORKLOAD_ID"] = case_id
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    for name in ("HERMES_HOME", "HERMES_YOLO_MODE", "HERMES_ACCEPT_HOOKS", "HERMES_INTERACTIVE"):
        environment.pop(name, None)
    return environment


def _measurement_index(runtime: Path) -> dict[str, dict[str, Any]]:
    index = {}
    root = runtime / "measurements" / "token-efficiency"
    for path in root.rglob("tok_*.json") if root.exists() else []:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and isinstance(value.get("measurement_id"), str):
            index[value["measurement_id"]] = value
    return index


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _public_measurement(document: Mapping[str, Any]) -> dict[str, Any]:
    composition = document.get("request_composition", {})
    components = composition.get("components", {}) if isinstance(composition, dict) else {}
    projected_components = {}
    if isinstance(components, dict):
        for name, value in components.items():
            if not isinstance(value, dict):
                continue
            projected_components[name] = {
                key: value.get(key)
                for key in (
                    "availability",
                    "items",
                    "chars",
                    "utf8_bytes",
                    "local_estimated_tokens",
                )
                if key in value
            }
    return {
        "document_sha256": _sha256_bytes(_canonical(document)),
        "measurement_id": document.get("measurement_id"),
        "request_kind": document.get("request_kind"),
        "dispatch_id": document.get("dispatch_id"),
        "runtime_session_id": document.get("runtime_session_id"),
        "request_composition": {
            "canonical_chars": composition.get("canonical_chars"),
            "canonical_utf8_bytes": composition.get("canonical_utf8_bytes"),
            "wire_utf8_bytes": composition.get("wire_utf8_bytes"),
            "local_estimated_tokens": composition.get("local_estimated_tokens"),
            "components": projected_components,
        },
        "provider_usage": document.get("provider_usage"),
        "attempt": document.get("attempt"),
        "retry_count": document.get("retry_count"),
        "fallback_index": document.get("fallback_index"),
        "fallback_detected": document.get("fallback_detected"),
        "tool_call_count": document.get("tool_call_count"),
        "auxiliary_stream": document.get("auxiliary_stream"),
        "outcome": document.get("outcome"),
        "timing": document.get("timing"),
        "endpoint_identity": document.get("endpoint_identity"),
        "source": document.get("source"),
        "runtime_estimates": document.get("runtime_estimates"),
        "cost": document.get("cost"),
    }


def _expected_final(action: str, case_id: str, turn_id: str) -> str:
    prefix = "TOKEN700_UNAVAILABLE" if action == "UNAVAILABLE_FINAL" else "TOKEN700_OK"
    return f"{prefix}:{case_id}:{turn_id}"


def _required_history_markers(case: Mapping[str, Any]) -> list[str]:
    workload = case["workload"]
    generator = workload.get("turn_generator")
    if not isinstance(generator, dict):
        return []
    key = f"turn_{workload['turn_count']}_requires_provider_context_markers"
    values = generator.get(key, [])
    return [str(value).format(case_id=case["case_id"]) for value in values]


def _run_turn(
    *,
    arm: str,
    arm_root: Path,
    home: Path,
    runtime: Path,
    case: Mapping[str, Any],
    task_id: str,
    turn: Mapping[str, str],
    all_case_ids: set[str],
    server: Token700Server,
) -> dict[str, Any]:
    start_index = server.snapshot()
    started = time.monotonic()
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            RUNNER_SOURCE,
            turn["prompt"],
            task_id,
            str(arm_root),
        ],
        cwd=arm_root,
        env=_arm_environment(home, str(case["case_id"])),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=OUTER_TIMEOUT_SECONDS,
        check=False,
    )
    elapsed_ms = round((time.monotonic() - started) * 1000, 3)
    if completed.returncode != 0:
        raise RuntimeError(
            f"{arm} {case['case_id']} {turn['turn_id']} runner failed: {completed.stderr[-2000:]}"
        )
    envelope = json.loads(completed.stdout)
    worker = envelope["worker"]
    finalization = envelope["finalization"]
    requests = server.since(start_index)
    expected_dispatches = 2 if turn["provider_action"] == "STATUS_THEN_FINAL" else 1
    expected_final = _expected_final(turn["provider_action"], str(case["case_id"]), turn["turn_id"])

    payload = worker.get("payload", {})
    summary = payload.get("token_measurement", {}) if isinstance(payload, dict) else {}
    measurement_ids = summary.get("measurement_ids", []) if isinstance(summary, dict) else []
    index = _measurement_index(runtime)
    documents = [index[item] for item in measurement_ids if item in index]
    conversation = [item for item in documents if item.get("request_kind") == "conversation"]
    auxiliary = [item for item in documents if item.get("request_kind") == "auxiliary"]

    current_marker = f"TOKEN700|{case['case_id']}|{turn['turn_id']}|"
    other_markers = sorted(
        marker
        for marker in all_case_ids
        if marker != case["case_id"]
        and any(marker in _request_text(request) for request in requests)
    )
    active_tools = sorted({name for request in requests for name in _tool_names(request)})
    checks = {
        "worker_status_ok": worker.get("status") == "OK",
        "expected_final_marker_exact": payload.get("final_response") == expected_final,
        "current_turn_marker_present_at_provider_boundary": (
            bool(requests) and all(current_marker in _request_text(request) for request in requests)
        ),
        "measurement_complete_with_zero_drops": (
            summary.get("measurement_complete") is True
            and summary.get("measurement_drop_count") == 0
            and summary.get("invalid_record_count") == 0
            and len(documents) == len(measurement_ids)
        ),
        "no_auxiliary_model_dispatch": not auxiliary,
        "release_verdict_unknown": finalization.get("release_gate_verdict") == "UNKNOWN",
        "release_eligible_false": finalization.get("release_eligible") is False,
        "task_release_not_performed": finalization.get("task_release_performed") is False,
        "canonical_receipt_not_created": finalization.get("canonical_receipt_created") is False,
        "no_cross_task_case_marker_leak": not other_markers,
        "provider_dispatch_count_expected": len(requests) == expected_dispatches,
        "measurement_dispatch_count_expected": len(conversation) == expected_dispatches,
        "active_tools_are_gauntlet_owned": all(
            name.startswith("gauntlet_") for name in active_tools
        ),
        "retry_and_fallback_absent": all(
            item.get("retry_count") in {0, None}
            and item.get("fallback_detected") is False
            and item.get("fallback_index") in {0, None}
            for item in documents
        ),
        "source_identity_matches_arm": all(
            item.get("source", {}).get("running_commit") == ARMS[arm]["commit"]
            and item.get("source", {}).get("running_tree") == ARMS[arm]["tree"]
            for item in documents
        ),
    }

    status_result = None
    if turn["provider_action"] == "STATUS_THEN_FINAL" and len(requests) == 2:
        results = _tool_results(requests[-1])
        status_result = results[-1] if results else None
        authority = status_result.get("authority", {}) if isinstance(status_result, dict) else {}
        checks.update(
            {
                "tool_calls_equal_1": sum(
                    int(_number(item.get("tool_call_count"))) for item in documents
                )
                == 1,
                "status_task_id_matches": (
                    isinstance(status_result, dict) and status_result.get("task_id") == task_id
                ),
                "status_is_read_only": (
                    isinstance(status_result, dict) and status_result.get("read_only") is True
                ),
                "status_mutation_false": (
                    isinstance(status_result, dict)
                    and status_result.get("mutation_performed") is False
                ),
                "status_authority_all_false": (
                    isinstance(authority, dict)
                    and bool(authority)
                    and all(value is False for value in authority.values())
                ),
            }
        )
    else:
        checks["tool_calls_equal_0"] = (
            sum(int(_number(item.get("tool_call_count"))) for item in documents) == 0
        )

    route_metrics = payload.get("capsule_metrics") if isinstance(payload, dict) else None
    local_input = sum(
        _number(item.get("request_composition", {}).get("local_estimated_tokens"))
        for item in conversation
    )
    provider_output = sum(
        _number(item.get("provider_usage", {}).get("output_tokens")) for item in conversation
    )
    reasoning = sum(
        _number(item.get("provider_usage", {}).get("reasoning_tokens")) for item in conversation
    )
    cache_write = sum(
        _number(item.get("provider_usage", {}).get("cache_write_tokens")) for item in conversation
    )
    cache_read = sum(
        _number(item.get("provider_usage", {}).get("cache_read_tokens")) for item in conversation
    )
    return {
        "turn_id": turn["turn_id"],
        "provider_action": turn["provider_action"],
        "checks": checks,
        "correct": all(checks.values()),
        "provider_dispatches": len(requests),
        "api_calls": len(conversation),
        "tool_calls": sum(int(_number(item.get("tool_call_count"))) for item in conversation),
        "elapsed_ms": elapsed_ms,
        "local_estimated_input_tokens": int(local_input),
        "provider_output_tokens": int(provider_output),
        "reasoning_tokens": int(reasoning),
        "cache_write_tokens": int(cache_write),
        "cache_read_tokens": int(cache_read),
        "complete_token_units": int(local_input + provider_output + reasoning + cache_write),
        "runtime_session_ids": summary.get("conversation_runtime_session_ids", []),
        "active_tool_names": active_tools,
        "route_metrics": route_metrics,
        "cross_task_leak_markers": other_markers,
        "measurements": [_public_measurement(item) for item in conversation],
    }


def _run_case(
    *,
    arm: str,
    arm_root: Path,
    home: Path,
    case: Mapping[str, Any],
    task_id: str,
    all_case_ids: set[str],
    server: Token700Server,
) -> dict[str, Any]:
    runtime = home / ".gauntlet" / "runtime"
    turns = []
    for turn in expand_turns(case):
        turns.append(
            _run_turn(
                arm=arm,
                arm_root=arm_root,
                home=home,
                runtime=runtime,
                case=case,
                task_id=task_id,
                turn=turn,
                all_case_ids=all_case_ids,
                server=server,
            )
        )

    task_path = arm_root / ".egrt" / "state" / "runtime" / "tasks" / f"{task_id}.json"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    receipts = list((arm_root / ".egrt" / "state" / "runtime" / "receipts").glob("*.json"))
    case_checks = {
        "canonical_task_not_marked_released": task.get("released") is False,
        "canonical_receipt_count_zero": not receipts,
        "canonical_obligation_count_matches": (
            len(task.get("obligations", [])) == len(case["workload"]["obligations"])
        ),
        "all_obligations_remain_open": (task.get("released") is False and not receipts),
        "one_runtime_session_id": len(
            {session_id for turn in turns for session_id in turn["runtime_session_ids"]}
        )
        == 1,
    }
    required = _required_history_markers(case)
    if required:
        final_measurements = turns[-1]["measurements"]
        final_requests = server.chat_requests[-turns[-1]["provider_dispatches"] :]
        text = "\n".join(_request_text(request) for request in final_requests)
        case_checks["final_turn_contains_required_context_markers"] = all(
            marker in text for marker in required
        ) and bool(final_measurements)

    route_metrics = [
        turn["route_metrics"] for turn in turns if isinstance(turn.get("route_metrics"), dict)
    ]
    return {
        "arm": arm,
        "case_id": case["case_id"],
        "workload_id": case["workload"]["id"],
        "workload_name": case["workload"]["name"],
        "scope": case["workload"]["scope"],
        "task_id": task_id,
        "task_sha256": _sha256_file(task_path),
        "checks": case_checks,
        "turns": turns,
        "correct": all(case_checks.values()) and all(turn["correct"] for turn in turns),
        "local_estimated_input_tokens": sum(turn["local_estimated_input_tokens"] for turn in turns),
        "complete_token_units": sum(turn["complete_token_units"] for turn in turns),
        "api_calls": sum(turn["api_calls"] for turn in turns),
        "tool_calls": sum(turn["tool_calls"] for turn in turns),
        "elapsed_ms": round(sum(turn["elapsed_ms"] for turn in turns), 3),
        "route_estimated_tokens_max": max(
            (int(item.get("route_estimated_tokens", 0)) for item in route_metrics),
            default=None,
        ),
        "status_estimated_tokens_max": max(
            (int(item.get("status_estimated_tokens", 0)) for item in route_metrics),
            default=None,
        ),
        "extra_llm_calls": sum(
            turn["provider_dispatches"]
            - (2 if turn["provider_action"] == "STATUS_THEN_FINAL" else 1)
            for turn in turns
        ),
        "false_clear_events": sum(not turn["checks"]["release_eligible_false"] for turn in turns),
        "cross_task_leaks": sum(bool(turn["cross_task_leak_markers"]) for turn in turns),
    }


def _validate_source_state() -> dict[str, str]:
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("tracked evaluation worktree must be clean")
    if _git("merge-base", "--is-ancestor", PREREGISTRATION_COMMIT, "HEAD"):
        pass
    head = _git("rev-parse", "HEAD^{commit}")
    tree = _git("rev-parse", "HEAD^{tree}")
    for arm, identity in ARMS.items():
        if _git("rev-parse", f"{identity['commit']}^{{tree}}") != identity["tree"]:
            raise RuntimeError(f"{arm} recorded tree does not match its commit")
        gitlink = _git("ls-tree", identity["commit"], "vendor/hermes-agent").split()[2]
        if gitlink != PINNED_HERMES:
            raise RuntimeError(f"{arm} pinned Hermes gitlink mismatch")
    current_gitlink = _git("ls-tree", "HEAD", "vendor/hermes-agent").split()[2]
    if current_gitlink != PINNED_HERMES:
        raise RuntimeError("current evaluator Hermes gitlink mismatch")
    if _git("status", "--porcelain", cwd=REPO / "vendor" / "hermes-agent"):
        raise RuntimeError("current pinned Hermes checkout is dirty")
    return {"evaluator_commit": head, "evaluator_tree": tree}


def _actions(cases: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    result = {}
    for case in cases:
        actions = {turn["provider_action"] for turn in expand_turns(case)}
        if len(actions) != 1:
            raise ValueError(f"case {case['case_id']} has mixed fixture actions")
        result[str(case["case_id"])] = actions.pop()
    return result


def _pair_results(
    cases: Sequence[Mapping[str, Any]],
    results: Mapping[str, Mapping[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    pairs = []
    for case in cases:
        case_id = str(case["case_id"])
        baseline = results[case_id]["baseline"]
        candidate = results[case_id]["candidate"]
        pairs.append(
            {
                "case_id": case_id,
                "workload_id": case["workload"]["id"],
                "workload_name": case["workload"]["name"],
                "scope": case["workload"]["scope"],
                "arm_order": results[case_id]["arm_order"],
                "baseline_correct": baseline["correct"],
                "candidate_correct": candidate["correct"],
                "input_reduction": paired_reduction(
                    baseline["local_estimated_input_tokens"],
                    candidate["local_estimated_input_tokens"],
                ),
                "complete_token_reduction": paired_reduction(
                    baseline["complete_token_units"],
                    candidate["complete_token_units"],
                ),
                "baseline": baseline,
                "candidate": candidate,
            }
        )
    return pairs


def _summarize(pairs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    quality = finite_suite_noninferiority(
        [(bool(pair["baseline_correct"]), bool(pair["candidate_correct"])) for pair in pairs]
    )
    baseline_valid = all(pair["baseline_correct"] for pair in pairs)
    input_reductions = [float(pair["input_reduction"]) for pair in pairs]
    complete_reductions = [float(pair["complete_token_reduction"]) for pair in pairs]
    continuity = [
        float(pair["input_reduction"])
        for pair in pairs
        if pair["workload_id"] in {"W08", "W09", "W10"}
    ]
    absence = [
        float(pair["input_reduction"])
        for pair in pairs
        if pair["workload_id"] in {"W03", "W04", "W05", "W06", "W07"}
    ]
    candidate_cases = [pair["candidate"] for pair in pairs]
    route_values = [
        value
        for case in candidate_cases
        if (value := case["route_estimated_tokens_max"]) is not None
    ]
    status_values = [
        value
        for case in candidate_cases
        if (value := case["status_estimated_tokens_max"]) is not None
    ]
    gates = {
        "baseline_valid": baseline_valid,
        "finite_suite_quality_noninferiority": quality["passed"],
        "route_capsule_max_le_512": bool(route_values) and max(route_values) <= 512,
        "compact_status_max_le_1024": bool(status_values) and max(status_values) <= 1024,
        "candidate_extra_llm_calls_zero": sum(case["extra_llm_calls"] for case in candidate_cases)
        == 0,
        "canonical_task_obligation_parity_100_percent": all(
            pair["baseline"]["task_sha256"] == pair["candidate"]["task_sha256"] for pair in pairs
        ),
        "candidate_false_clear_events_zero": sum(
            case["false_clear_events"] for case in candidate_cases
        )
        == 0,
        "candidate_cross_task_leaks_zero": sum(case["cross_task_leaks"] for case in candidate_cases)
        == 0,
        "overall_median_input_reduction_ge_40_percent": (
            median(input_reductions) is not None and median(input_reductions) >= 0.40
        ),
        "median_complete_token_reduction_ge_25_percent": (
            median(complete_reductions) is not None and median(complete_reductions) >= 0.25
        ),
    }
    if not baseline_valid:
        disposition = "INVALID_BASELINE"
    elif not quality["passed"]:
        disposition = "FAIL_QUALITY"
    elif not all(gates.values()):
        disposition = "FAIL_LOCAL_EFFICACY_OR_SAFETY_GATE"
    else:
        disposition = "LOCAL_NONMONETARY_NONINFERIOR"
    return {
        "disposition": disposition,
        "quality": quality,
        "gates": gates,
        "efficacy": {
            "overall_median_input_reduction": median(input_reductions),
            "continuity_median_input_reduction": median(continuity),
            "capability_absence_control_median_input_reduction": median(absence),
            "overall_median_complete_token_reduction": median(complete_reductions),
            "external_mcp_tool_heavy_reduction": "NOT_ESTABLISHED_GAUNTLET_ONLY",
            "monetary_complete_cost_reduction": "NOT_ESTABLISHED_UNPRICED_FIXTURE",
        },
        "maxima": {
            "route_estimated_tokens": max(route_values) if route_values else None,
            "status_estimated_tokens": max(status_values) if status_values else None,
        },
        "counts": {
            "pairs": len(pairs),
            "candidate_extra_llm_calls": sum(case["extra_llm_calls"] for case in candidate_cases),
            "candidate_false_clear_events": sum(
                case["false_clear_events"] for case in candidate_cases
            ),
            "candidate_cross_task_leaks": sum(case["cross_task_leaks"] for case in candidate_cases),
        },
        "claim_ceiling": (
            "Bounded localhost engineering result only; no real-model, external-tool, "
            "cache, monetary, or production-promotion claim."
        ),
    }


def run(output: Path, *, validate_only: bool = False) -> dict[str, Any]:
    source = _validate_source_state()
    manifest = load_manifest()
    cases = expand_cases(manifest)
    if validate_only:
        return {
            "status": "validated",
            "cases": len(cases),
            "manifest_sha256": MANIFEST_SHA256,
            **source,
        }
    actions = _actions(cases)
    server = Token700Server(actions)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="gauntlet-token700-") as temporary:
            temporary_root = Path(temporary).resolve()
            task_template = temporary_root / "task-template"
            task_template.mkdir()
            task_ids = _prepare_tasks(task_template, cases)
            template_digest = _state_digest(task_template)
            with exact_worktrees(temporary_root) as arm_roots:
                homes = {
                    "baseline": temporary_root / "home-a",
                    "candidate": temporary_root / "home-b",
                }
                for arm, arm_root in arm_roots.items():
                    shutil.copytree(task_template / ".egrt", arm_root / ".egrt")
                    if _state_digest(arm_root) != template_digest:
                        raise RuntimeError(f"{arm} task-state copy differs from template")
                    runtime = homes[arm] / ".gauntlet" / "runtime"
                    _write_runtime_config(runtime, server.server_address[1])

                all_case_ids = {str(case["case_id"]) for case in cases}
                results: dict[str, dict[str, Any]] = {}
                for index, case in enumerate(cases):
                    case_id = str(case["case_id"])
                    order = (
                        ["baseline", "candidate"] if index % 2 == 0 else ["candidate", "baseline"]
                    )
                    print(
                        f"TOKEN-700 {index + 1:02d}/{len(cases)} {case_id} {'>'.join(order)}",
                        file=sys.stderr,
                        flush=True,
                    )
                    results[case_id] = {"arm_order": order}
                    for arm in order:
                        results[case_id][arm] = _run_case(
                            arm=arm,
                            arm_root=arm_roots[arm],
                            home=homes[arm],
                            case=case,
                            task_id=task_ids[case_id],
                            all_case_ids=all_case_ids,
                            server=server,
                        )
                for arm, arm_root in arm_roots.items():
                    if _state_digest(arm_root) != template_digest:
                        raise RuntimeError(f"{arm} canonical task state mutated")
                pairs = _pair_results(cases, results)
                summary = _summarize(pairs)
                document = {
                    "schema": "gauntlet.token700-qualification.v1",
                    "phase": "TOKEN-700",
                    "mode": "MATCHED_LOCAL_GAUNTLET_ONLY",
                    "preregistration": {
                        "commit": PREREGISTRATION_COMMIT,
                        "manifest": "benchmarks/token700/workloads.v1.json",
                        "manifest_sha256": MANIFEST_SHA256,
                        "sample_size_pairs": len(pairs),
                        "noninferiority_margin_percentage_points": 0,
                    },
                    "source": {
                        **source,
                        "arms": ARMS,
                        "pinned_hermes_commit": PINNED_HERMES,
                    },
                    "fixture": {
                        "model": MODEL,
                        "provider": PROVIDER,
                        "endpoint": "localhost_ephemeral_openai_chat_completions",
                        "external_network": False,
                        "authorized_tools": "GAUNTLET_ONLY",
                        "provider_usage": "deterministic request-derived fixture values",
                        "money": "UNPRICED",
                    },
                    "summary": summary,
                    "pairs": pairs,
                    "privacy": {
                        "raw_provider_requests_persisted": False,
                        "raw_provider_responses_persisted": False,
                        "raw_tool_outputs_persisted": False,
                        "numeric_measurement_projections_persisted": True,
                    },
                    "authority_ceiling": "EVALUATION_ONLY",
                    "canonical_receipt_created": False,
                    "canonical_state_mutated": False,
                }
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                return document
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.validate_only and args.output is None:
        parser.error("--output is required unless --validate-only is used")
    result = run(args.output or Path("unused.json"), validate_only=args.validate_only)
    summary = result.get("summary") if isinstance(result, dict) else None
    print(
        json.dumps(
            {
                "status": result.get("status", "completed"),
                "disposition": summary.get("disposition") if isinstance(summary, dict) else None,
                "cases": (
                    result.get("cases")
                    if args.validate_only
                    else result.get("preregistration", {}).get("sample_size_pairs")
                ),
                "output": str(args.output) if args.output is not None else None,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
