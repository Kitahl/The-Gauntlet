#!/usr/bin/env python3
"""Non-destructive localhost qualification for TOKEN-400."""

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

REPO = Path(__file__).resolve().parents[1]
PINNED_HERMES = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
PROMPT = "Read the exact obligation, then explicitly retrieve one bounded artifact page."
DETAIL_CALL_ID = "token400-detail"
ARTIFACT_CALL_ID = "token400-artifact"
RAW_START = "TOKEN400-CURRENT-CALL-RAW-START"
RAW_TAIL = "TOKEN400-FULL-ARTIFACT-TAIL"
RAW_SECRET = "token=token400-super-secret-value"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from gauntlet_host.ipc import WorkerStatus  # noqa: E402
from gauntlet_host.launcher import run_worker_turn  # noqa: E402
from gauntlet_host.runtime_profile import prepare_runtime_profile  # noqa: E402
from gauntlet_host.session_binding import derive_session_id  # noqa: E402
from gauntlet_host.tool_results import (  # noqa: E402
    CURRENT_CALL_SCHEMA,
    PAGE_SCHEMA,
    REFERENCE_SCHEMA,
)


def _load_support() -> Any:
    path = REPO / ".github" / "token100_verify.py"
    spec = importlib.util.spec_from_file_location("token100_support_for_token400", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load TOKEN-100 localhost fixture support")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


support = _load_support()


def _tool_results(body: dict[str, Any]) -> dict[str, str]:
    results: dict[str, str] = {}
    messages = body.get("messages")
    if not isinstance(messages, list):
        return results
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        call_id = message.get("tool_call_id")
        if isinstance(call_id, str):
            results[call_id] = support._message_text(message)
    return results


class Token400Server(support.phase5.Phase5Server):
    def __init__(self) -> None:
        ThreadingHTTPServer.__init__(self, ("127.0.0.1", 0), Token400Handler)
        self.lock = threading.Lock()
        self.chat_requests: list[dict[str, Any]] = []
        self.artifact_id: str | None = None
        self.protocol_errors: list[str] = []


class Token400Handler(support.phase5.Phase5Handler):
    @property
    def token400_server(self) -> Token400Server:
        return self.server  # type: ignore[return-value]

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        if not path.endswith("/chat/completions"):
            self._send_json({"ok": True})
            return

        server = self.token400_server
        with server.lock:
            server.chat_requests.append(body)
        created = int(time.time())
        results = _tool_results(body)
        if ARTIFACT_CALL_ID in results:
            self._final_response(body, created, "TOKEN-400 bounded rehydration observed")
            return
        if DETAIL_CALL_ID in results:
            try:
                current = json.loads(results[DETAIL_CALL_ID])
                if current.get("schema") != CURRENT_CALL_SCHEMA:
                    raise ValueError("detail result was not current-call projection")
                artifact = current.get("artifact")
                if not isinstance(artifact, dict) or artifact.get("schema") != REFERENCE_SCHEMA:
                    raise ValueError("current-call projection omitted artifact reference")
                artifact_id = artifact.get("artifact_id")
                if not isinstance(artifact_id, str):
                    raise ValueError("artifact ID missing")
                server.artifact_id = artifact_id
            except Exception as exc:
                server.protocol_errors.append(str(exc))
                self._final_response(body, created, "TOKEN-400 protocol error")
                return
            self._tool_response(
                body,
                created,
                call_id=ARTIFACT_CALL_ID,
                name="gauntlet_artifact_get",
                arguments={"artifact_id": server.artifact_id, "offset": 0, "limit": 512},
            )
            return
        self._tool_response(
            body,
            created,
            call_id=DETAIL_CALL_ID,
            name="gauntlet_obligation_get",
            arguments={"obligation_id": os.environ.get("TOKEN400_OBLIGATION_ID", "")},
        )

    def _tool_response(
        self,
        body: dict[str, Any],
        created: int,
        *,
        call_id: str,
        name: str,
        arguments: dict[str, Any],
    ) -> None:
        call = {
            "id": call_id,
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(arguments, separators=(",", ":"), sort_keys=True),
            },
        }
        if body.get("stream"):
            self._send_stream(
                [
                    {
                        "id": f"chatcmpl-{call_id}",
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
                        "id": f"chatcmpl-{call_id}",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "phase5-mock",
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                    },
                    self._usage(created),
                ]
            )
            return
        self._send_json(
            {
                "id": f"chatcmpl-{call_id}",
                "object": "chat.completion",
                "created": created,
                "model": "phase5-mock",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": None, "tool_calls": [call]},
                        "finish_reason": "tool_calls",
                    }
                ],
            }
        )


def _create_large_task(root: Path) -> tuple[str, str, str]:
    task = support._json_run(
        [
            sys.executable,
            str(REPO / "tools" / "soul_runtime.py"),
            "--root",
            str(root),
            "start",
            "--goal",
            "TOKEN-400 bounded tool-result lifecycle qualification",
        ]
    )
    task_id = str(task["task_id"])
    claim = (
        RAW_START + "\n" + RAW_SECRET + "\n" + ("bounded-operational-payload\n" * 420) + RAW_TAIL
    )
    obligation = support._json_run(
        [
            sys.executable,
            str(REPO / "tools" / "soul_runtime.py"),
            "--root",
            str(root),
            "add",
            task_id,
            "DISCOVERY",
            "--claim",
            claim,
        ]
    )
    return task_id, str(obligation["obligation_id"]), claim


def _persisted_conversation(runtime: Path, session_id: str) -> list[dict[str, Any]]:
    os.environ["HERMES_HOME"] = str(runtime)
    vendor = str(REPO / "vendor" / "hermes-agent")
    inserted = vendor not in sys.path
    if inserted:
        sys.path.insert(0, vendor)
    try:
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            return db.get_messages_as_conversation(
                session_id,
                repair_alternation=True,
                include_row_ids=True,
            )
        finally:
            db.close()
    finally:
        if inserted and sys.path and sys.path[0] == vendor:
            sys.path.pop(0)


def _tool_content(request: dict[str, Any], call_id: str) -> str:
    return _tool_results(request)[call_id]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    snapshot = json.loads((REPO / "vendor" / "HERMES_SNAPSHOT.json").read_text(encoding="utf-8"))
    assert snapshot["upstream_commit"] == PINNED_HERMES
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO / "vendor" / "hermes-agent",
            text=True,
            encoding="utf-8",
        ).strip()
        == PINNED_HERMES
    )

    server = Token400Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_environment = {
        name: os.environ.get(name)
        for name in (
            "HOME",
            "USERPROFILE",
            "HERMES_HOME",
            "GAUNTLET_TOKEN_WORKLOAD_ID",
            "TOKEN400_OBLIGATION_ID",
        )
    }
    repository_state_before = support._canonical_state_digest(REPO)

    try:
        with tempfile.TemporaryDirectory(prefix="gauntlet-token400-") as temporary:
            home = Path(temporary)
            runtime = home / ".gauntlet" / "runtime"
            support.phase5._write_runtime_config(runtime, server.server_address[1])
            os.environ["HOME"] = str(home)
            os.environ["USERPROFILE"] = str(home)
            os.environ.pop("HERMES_HOME", None)
            os.environ["GAUNTLET_TOKEN_WORKLOAD_ID"] = "TOKEN400_LIVE"

            workspace = home / "workspace"
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
            shutil.copytree(REPO / "gauntlet_host", workspace / "gauntlet_host", ignore=ignore)
            shutil.copytree(REPO / "tools", workspace / "tools", ignore=ignore)
            (workspace / "vendor" / "hermes-agent").mkdir(parents=True)
            task_id, obligation_id, raw_claim = _create_large_task(workspace)
            os.environ["TOKEN400_OBLIGATION_ID"] = obligation_id
            workspace_state_before = support._canonical_state_digest(workspace)

            profile = prepare_runtime_profile(runtime)
            session_id = derive_session_id(task_id, profile.session_binding_key_path)
            result = run_worker_turn(
                PROMPT,
                task_id=task_id,
                cwd=workspace,
                model="phase5-mock",
                provider="custom",
                timeout_seconds=180,
            )
            if result.status is not WorkerStatus.OK:
                raise AssertionError(
                    {
                        "worker_error": str(result.error or result),
                        "provider_requests": len(server.chat_requests),
                        "protocol_errors": server.protocol_errors,
                    }
                )
            assert not server.protocol_errors, server.protocol_errors

            requests = support._conversation_requests(server.chat_requests)
            assert len(requests) == 3, len(requests)
            first, current_call_request, rehydrated_request = requests
            expected_tools = {
                "gauntlet_task_status_compact",
                "gauntlet_obligation_get",
                "gauntlet_release_status",
                "gauntlet_artifact_get",
            }
            assert support._tool_names(first) == expected_tools
            assert all(support._tool_names(request) == expected_tools for request in requests)

            current = json.loads(_tool_content(current_call_request, DETAIL_CALL_ID))
            assert current["schema"] == CURRENT_CALL_SCHEMA
            assert current["visibility"] == "CURRENT_PROVIDER_CALL_ONLY"
            assert RAW_START in current["content"]
            assert RAW_TAIL in current["content"]
            assert "token400-super-secret-value" not in current["content"]
            assert "token=<redacted>" in current["content"]
            reference = current["artifact"]
            assert reference["schema"] == REFERENCE_SCHEMA
            assert reference["artifact_id"] == server.artifact_id
            assert reference["sha256"] == reference["artifact_id"][4:]
            assert reference["rehydrate"]["tool"] == "gauntlet_artifact_get"
            assert len(json.dumps(reference)) < len(current["content"])

            durable_reference = json.loads(_tool_content(rehydrated_request, DETAIL_CALL_ID))
            assert durable_reference["schema"] == REFERENCE_SCHEMA
            assert durable_reference["artifact_id"] == reference["artifact_id"]
            assert RAW_START not in _tool_content(rehydrated_request, DETAIL_CALL_ID)
            page = json.loads(_tool_content(rehydrated_request, ARTIFACT_CALL_ID))
            assert page["schema"] == PAGE_SCHEMA
            assert page["artifact_id"] == reference["artifact_id"]
            assert page["returned_chars"] == 512
            assert page["has_more"] is True
            assert RAW_START in page["content"]
            assert RAW_TAIL not in page["content"]
            assert page["authority"] == "OPERATIONAL_ONLY"
            assert page["mutation_performed"] is False

            artifacts = list((runtime / "operational" / "tool-results").rglob("art_*.json"))
            assert len(artifacts) == 1, artifacts
            artifact_path = artifacts[0]
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            assert artifact["artifact_id"] == reference["artifact_id"]
            assert (
                hashlib.sha256(artifact["content"].encode("utf-8")).hexdigest()
                == artifact["sha256"]
            )
            assert RAW_START in artifact["content"]
            assert RAW_TAIL in artifact["content"]
            assert "token400-super-secret-value" not in artifact["content"]
            assert artifact["authority"] == "OPERATIONAL_ONLY"
            assert artifact["canonical_evidence"] is False
            assert artifact["expires_epoch"] > artifact["created_epoch"]
            assert str(artifact_path) not in json.dumps(requests)

            persisted = _persisted_conversation(runtime, session_id)
            persisted_text = json.dumps(persisted, ensure_ascii=False)
            assert CURRENT_CALL_SCHEMA not in persisted_text
            assert RAW_TAIL not in persisted_text
            assert "token400-super-secret-value" not in persisted_text
            assert REFERENCE_SCHEMA in persisted_text
            assert PAGE_SCHEMA in persisted_text
            detail_rows = [
                row
                for row in persisted
                if row.get("role") == "tool" and row.get("tool_call_id") == DETAIL_CALL_ID
            ]
            assert len(detail_rows) == 1
            assert json.loads(support._message_text(detail_rows[0]))["schema"] == REFERENCE_SCHEMA

            lifecycle = result.payload["tool_result_lifecycle"]
            assert lifecycle["externalized_results"] == 1
            assert lifecycle["externalized_chars"] == len(artifact["content"])
            assert lifecycle["reference_chars"] < lifecycle["externalized_chars"]
            assert lifecycle["task_bound"] is True
            assert lifecycle["session_bound"] is True
            assert lifecycle["content_addressed"] is True
            assert lifecycle["ttl_bounded"] is True
            assert lifecycle["canonical_evidence"] is False
            assert lifecycle["rehydration_tool"] == "gauntlet_artifact_get"
            assert lifecycle["first_visibility"]["first_visibility_presentations"] == 1
            assert lifecycle["first_visibility"]["pending_first_visibility"] == 0
            assert lifecycle["first_visibility"]["persisted_transcript_mutated"] is False
            assert result.payload["usage"]["api_calls"] == 3
            assert result.payload["final_response"] == "TOKEN-400 bounded rehydration observed"
            assert result.payload["session_id"] == session_id

            assert workspace_state_before == support._canonical_state_digest(workspace)
            assert repository_state_before == support._canonical_state_digest(REPO)
            assert not any((workspace / ".egrt" / "state" / "runtime" / "receipts").glob("*.json"))
            assert len(raw_claim) > 8_000

            running_commit, running_tree = support._git_identity()
            manifest = {
                "schema": "gauntlet.token-400-qualification.v1",
                "phases": ["TOKEN-400"],
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
                    "raw_result_visible_in_current_provider_call": True,
                    "durable_transcript_contains_reference_only": True,
                    "deterministic_extraction": True,
                    "secret_redaction_observed": True,
                    "private_task_session_bound_store": True,
                    "content_addressed_hash_verified": True,
                    "ttl_bound_verified": True,
                    "bounded_explicit_rehydration": True,
                    "artifact_path_not_model_visible": True,
                    "canonical_state_unchanged": True,
                    "canonical_receipts_created": 0,
                },
                "counts": {
                    "provider_requests": len(requests),
                    "model_visible_tools": len(expected_tools),
                    "raw_claim_chars": len(raw_claim),
                    "stored_artifact_chars": lifecycle["externalized_chars"],
                    "durable_reference_chars": lifecycle["reference_chars"],
                    "rehydrated_page_chars": page["returned_chars"],
                    "operational_artifacts": len(artifacts),
                },
                "authority_ceiling": "TOKEN_EFFICIENCY_ONLY",
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {
                        "status": "verified",
                        "manifest": str(args.output),
                        "provider_requests": len(requests),
                        "raw_claim_chars": len(raw_claim),
                        "reference_chars": lifecycle["reference_chars"],
                        "rehydrated_page_chars": page["returned_chars"],
                    },
                    sort_keys=True,
                )
            )
    finally:
        support._restore_environment(original_environment)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
