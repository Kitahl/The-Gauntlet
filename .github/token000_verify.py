"""TOKEN-000 measurement-only qualification with a deterministic local provider."""

from __future__ import annotations

import argparse
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
FROZEN_COMMIT = "6a50046b23e4f4cef6667b80d2e700e7167d14ac"
FROZEN_TREE = "bb490654eba9eb5bef24102ba5f94321862cfdd0"
PINNED_HERMES = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"


def _load_phase5() -> Any:
    spec = importlib.util.spec_from_file_location("phase5_verify", PHASE5_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load FAST-P5 deterministic provider fixture")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    assert isinstance(value, dict)
    return value


def _create_task(phase5: Any) -> str:
    shutil.rmtree(REPO / ".egrt", ignore_errors=True)
    task = _json_run(
        [
            sys.executable,
            str(phase5.TOOLS / "soul_runtime.py"),
            "--root",
            str(REPO),
            "start",
            "--goal",
            "TOKEN-000 measurement qualification",
        ]
    )
    task_id = str(task["task_id"])
    _json_run(
        [
            sys.executable,
            str(phase5.TOOLS / "soul_runtime.py"),
            "--root",
            str(REPO),
            "add",
            task_id,
            "DISCOVERY",
            "--claim",
            "Measure without optimizing or clearing authority.",
        ]
    )
    return task_id


def _git_identity() -> tuple[str, str]:
    values = []
    for revision in ("HEAD^{commit}", "HEAD^{tree}"):
        values.append(
            subprocess.check_output(
                ["git", "rev-parse", "--verify", revision],
                cwd=REPO,
                text=True,
                encoding="utf-8",
            ).strip()
        )
    return values[0], values[1]


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


def _measurement_documents(runtime: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    root = runtime / "measurements" / "token-efficiency"
    for path in sorted(root.rglob("tok_*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(value, dict)
        documents.append(value)
    return documents


def _run(
    *,
    prompt: str,
    task_id: str,
    workload_id: str,
) -> dict[str, Any]:
    os.environ["GAUNTLET_TOKEN_WORKLOAD_ID"] = workload_id
    result = run_worker_turn(
        prompt,
        task_id=task_id,
        cwd=REPO,
        model="phase5-mock",
        provider="custom",
        timeout_seconds=90,
    )
    assert result.status is WorkerStatus.OK, result.error
    measurement = result.payload.get("token_measurement")
    assert isinstance(measurement, dict)
    assert measurement["measurement_complete"] is True, measurement
    assert measurement["measurement_drop_count"] == 0
    assert measurement["invalid_record_count"] == 0
    return {
        "request_id": measurement["host_request_id"],
        "session_ids": measurement["runtime_session_ids"],
        "conversation_session_ids": measurement["conversation_runtime_session_ids"],
        "auxiliary_session_ids": measurement["auxiliary_runtime_session_ids"],
        "dispatches": measurement["dispatches_recorded"],
        "conversation_dispatches": measurement["conversation_dispatches_recorded"],
        "auxiliary_dispatches": measurement["auxiliary_dispatches_recorded"],
        "measurement_ids": measurement["measurement_ids"],
        "provider_usage_aggregate": measurement["provider_usage_aggregate"],
    }


def _workload_entry(
    identifier: str,
    name: str,
    status: str,
    *,
    reason: str | None = None,
    runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "name": name,
        "status": status,
        "reason": reason,
        "runs": runs or [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    phase5 = _load_phase5()
    phase5._source_boundary()
    task_id = _create_task(phase5)
    server = phase5.Phase5Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_home = os.environ.get("HOME")
    original_profile = os.environ.get("USERPROFILE")
    original_runtime_home = os.environ.get("HERMES_HOME")
    workloads: list[dict[str, Any]] = []

    try:
        with tempfile.TemporaryDirectory(prefix="gauntlet-token000-") as temporary:
            home = Path(temporary)
            runtime = home / ".gauntlet" / "runtime"
            phase5._write_runtime_config(runtime, server.server_address[1])
            os.environ["HOME"] = str(home)
            os.environ["USERPROFILE"] = str(home)
            os.environ.pop("HERMES_HOME", None)

            one_shot_start = len(server.chat_requests)
            one_shot = _run(
                prompt="TOKEN-000 local no-tool one-shot measurement.",
                task_id=task_id,
                workload_id="W01_NO_TOOL_ONE_SHOT",
            )
            one_shot_request_count = len(server.chat_requests) - one_shot_start
            assert one_shot_request_count == one_shot["dispatches"], (
                one_shot_request_count,
                one_shot,
            )
            workloads.append(
                _workload_entry(
                    "W01",
                    "no-tool one-shot",
                    "MEASURED_SYNTHETIC_PROVIDER",
                    runs=[one_shot],
                )
            )

            status_start = len(server.chat_requests)
            status_run = _run(
                prompt=("Use gauntlet_task_status, then report that status was observed."),
                task_id=task_id,
                workload_id="W02_ONE_STATUS_CALL",
            )
            status_request_count = len(server.chat_requests) - status_start
            assert status_request_count == status_run["dispatches"], (
                status_request_count,
                status_run,
            )
            workloads.append(
                _workload_entry(
                    "W02",
                    "one status call",
                    "MEASURED_SYNTHETIC_PROVIDER",
                    runs=[status_run],
                )
            )

            chat_start = len(server.chat_requests)
            chat_runs: list[dict[str, Any]] = []
            canaries: list[str] = []
            for turn in range(1, 11):
                canary = f"TOKEN000_CANARY_{turn}_{uuid.uuid4().hex}"
                canaries.append(canary)
                chat_runs.append(
                    _run(
                        prompt=f"Ten-turn continuity probe {turn}: {canary}",
                        task_id=task_id,
                        workload_id="W08_TEN_TURN_CHAT",
                    )
                )
            chat_requests = server.chat_requests[chat_start:]
            expected_chat_dispatches = sum(run["dispatches"] for run in chat_runs)
            assert len(chat_requests) == expected_chat_dispatches
            conversation_requests = [
                request for request in chat_requests if _is_conversation_request(request)
            ]
            assert len(conversation_requests) == 10
            assert sum(run["conversation_dispatches"] for run in chat_runs) == 10
            prior_context_preserved = True
            for index, request in enumerate(conversation_requests):
                text = _request_text(request)
                if any(canary in text for canary in canaries[:index]):
                    continue
                if index > 0:
                    prior_context_preserved = False
                    break
            session_ids = [
                run["conversation_session_ids"][0]
                for run in chat_runs
                if len(run["conversation_session_ids"]) == 1
            ]
            same_runtime_session = len(set(session_ids)) == 1 and len(session_ids) == 10
            session_status = "PASS" if prior_context_preserved and same_runtime_session else "FAIL"
            workloads.append(
                _workload_entry(
                    "W08",
                    "ten-turn chat",
                    "MEASURED_CORRECTNESS_FAIL" if session_status == "FAIL" else "MEASURED",
                    reason=(
                        "launcher created fresh runtime sessions and the provider-bound "
                        "requests did not include prior-turn canaries"
                        if session_status == "FAIL"
                        else None
                    ),
                    runs=chat_runs,
                )
            )

            unavailable = {
                "W03": "web research",
                "W04": "coding/edit/verification",
                "W05": "browser interaction",
                "W06": "small MCP catalog",
                "W07": "large MCP catalog",
                "W09": "resumed long session",
                "W10": "mixed multi-obligation task",
            }
            for identifier, name in unavailable.items():
                reason = (
                    "blocked by the demonstrated session-continuity failure"
                    if identifier == "W09"
                    else "no frozen local tool/provider fixture exists at this checkpoint"
                )
                workloads.append(
                    _workload_entry(
                        identifier,
                        name,
                        "NOT_MEASURED",
                        reason=reason,
                    )
                )

            documents = _measurement_documents(runtime)
            serialized_documents = json.dumps(
                documents,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            assert not any(canary in serialized_documents for canary in canaries)
            assert "TOKEN-000 local no-tool one-shot measurement." not in serialized_documents
            assert all(
                document.get("privacy", {}).get("raw_prompt_persisted") is False
                for document in documents
            )
            assert all(
                document.get("privacy", {}).get("raw_tool_output_persisted") is False
                for document in documents
            )

            running_commit, running_tree = _git_identity()
            manifest = {
                "schema": "gauntlet.token-000-qualification.v1",
                "phase": "TOKEN-000",
                "mode": "MEASUREMENT_ONLY",
                "source": {
                    "running_commit": running_commit,
                    "running_tree": running_tree,
                    "frozen_fast_p8_handoff_commit": FROZEN_COMMIT,
                    "frozen_fast_p8_handoff_tree": FROZEN_TREE,
                    "pinned_hermes_commit": PINNED_HERMES,
                },
                "task_id": task_id,
                "provider_fixture": {
                    "provider": "custom",
                    "model": "phase5-mock",
                    "network": "localhost-only",
                    "usage": "synthetic fixed values; not a savings baseline",
                },
                "instrumentation": {
                    "boundaries": {
                        "conversation": "hermes.llm_execution",
                        "auxiliary_sync": "agent.auxiliary_client._relay_sync_completion",
                        "auxiliary_async": "agent.auxiliary_client._relay_async_completion",
                        "auxiliary_sync_stream": "agent.auxiliary_client._relay_sync_stream",
                    },
                    "coverage_unit": "logical provider dispatch",
                    "canonicalization": "gauntlet.logical-provider-payload.v1",
                    "local_token_estimator": "utf8-bytes-div-4-ceiling.v1",
                    "wire_bytes_available": False,
                    "raw_prompt_persisted": False,
                    "raw_tool_output_persisted": False,
                    "raw_response_persisted": False,
                    "dispatch_measurement_count": len(documents),
                    "conversation_dispatch_measurement_count": sum(
                        document.get("request_kind") == "conversation" for document in documents
                    ),
                    "auxiliary_dispatch_measurement_count": sum(
                        document.get("request_kind") == "auxiliary" for document in documents
                    ),
                },
                "session_correctness": {
                    "status": session_status,
                    "same_runtime_session_id": same_runtime_session,
                    "prior_turn_context_present": prior_context_preserved,
                    "cross_task_leak_tested": False,
                    "restart_resume_tested": False,
                    "prompt_cache_behavior_tested": False,
                },
                "workloads": sorted(workloads, key=lambda item: item["id"]),
                "dispatch_measurements": documents,
                "claims": {
                    "token_savings_calculated": False,
                    "cost_savings_calculated": False,
                    "noninferiority_established": False,
                    "valid_conclusion": (
                        "measurement seam works on local frozen fixtures; the current "
                        "chat path fails runtime-session continuity"
                    ),
                },
                "authority_ceiling": "OBSERVATION_ONLY",
                "canonical_receipt_created": False,
                "canonical_state_mutated": False,
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
                        "dispatch_measurements": len(documents),
                        "session_correctness": session_status,
                        "workloads_measured": sum(
                            item["status"].startswith("MEASURED") for item in workloads
                        ),
                    },
                    sort_keys=True,
                )
            )
    finally:
        if original_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = original_home
        if original_profile is None:
            os.environ.pop("USERPROFILE", None)
        else:
            os.environ["USERPROFILE"] = original_profile
        if original_runtime_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = original_runtime_home
        os.environ.pop("GAUNTLET_TOKEN_WORKLOAD_ID", None)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
