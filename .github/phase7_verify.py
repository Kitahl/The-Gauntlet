"""Bounded FAST-P7 live-capability and advisory FOIL route verification."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from typing import Any

REPO = Path(__file__).resolve().parent.parent
PHASE5_HELPER = REPO / ".github" / "phase5_verify.py"
RAW_CLAIM = "Find a canonical source before release."
ROUTE_MARKER = "[GAUNTLET FOIL ADVISORY ROUTE]"


def _load_phase5() -> Any:
    spec = importlib.util.spec_from_file_location("phase5_verify", PHASE5_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the retained FAST-P5 verification helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _route_adapter(
    task_id: str,
    capabilities: list[str],
    *,
    tool_hash: str = "a" * 64,
    tool_count: int = 2,
) -> tuple[int, dict[str, Any]]:
    environment = dict(os.environ)
    environment["GAUNTLET_TASK_ID"] = task_id
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO / "gauntlet_host" / "module_cli.py"),
            "--root",
            str(REPO),
            "foil-route",
        ],
        input=json.dumps(
            {
                "available_capabilities": capabilities,
                "tool_count": tool_count,
                "tool_manifest_hash": tool_hash,
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        cwd=REPO,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    records = [line for line in completed.stdout.splitlines() if line.strip()]
    assert len(records) == 1, completed.stderr
    return completed.returncode, json.loads(records[0])


def _assert_route(
    route: dict[str, Any],
    task_id: str,
    *,
    expect_incomplete: bool,
) -> None:
    assert route["schema"] == "gauntlet.foil-route.v1"
    assert route["action"] == "foil-route"
    assert route["status"] == "OK"
    assert route["task_id"] == task_id
    assert route["mode"] == "SHADOW"
    assert route["authority_ceiling"] == "ADAPTATION_ONLY"
    assert route["read_only"] is True
    assert route["mutation_performed"] is False
    assert route["execution_authorized"] is False
    assert route["toolset_narrowing_applied"] is False
    assert route["profile_used"] is False
    assert route["private_profile_data_transmitted"] is False
    assert route["stop_is_advisory"] is True
    assert all(value is False for value in route["authority"].values())
    assert route["policy_version"] == "FOIL_vNEXT_CANDIDATE_V2"
    assert route["trace"]["task_regime"] == "external_retrieval"
    assert route["primary_effort_mode"] == "discovery"
    assert "discover_candidates" in route["actions"]
    assert "source_evidence" in route["required_verifiers"]
    assert "source_evidence" in route["pending_verifiers"]
    assert route["should_stop"] is False
    assert route["targeted_complement"] is None
    assert route["capability_snapshot"]["verified_by_gauntlet"] is False
    assert route["capability_snapshot"]["source"] == (
        "RUNTIME_REPORTED_TOOL_DEFINITIONS"
    )
    assert "REASONING" in route["minimum_capability_bundle"]
    if expect_incomplete:
        assert route["capability_bundle_complete"] is False
        missing = {
            item["requirement"]
            for item in route["missing_capabilities"]
        }
        assert "verifier:source_evidence" in missing
    assert route["task_context"]["claim_text_transmitted"] is False
    assert RAW_CLAIM not in json.dumps(route)
    assert len(route["content_hash"]) == 64

    payload = dict(route)
    supplied = payload.pop("content_hash")
    import hashlib

    expected = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert supplied == expected


def _first_prompt_request(
    requests: list[dict[str, Any]],
    phase5: Any,
) -> dict[str, Any]:
    for request in requests:
        if phase5._has_target_prompt(request):
            return request
    raise AssertionError("no routed first model request was observed")


def _prompt_text(request: dict[str, Any], phase5: Any) -> str:
    return "\n".join(
        phase5._message_content(message)
        for message in request.get("messages", [])
        if isinstance(message, dict)
    )


def main() -> None:
    phase5 = _load_phase5()
    phase5._source_boundary()
    task_id = phase5._create_task()
    before = phase5._task_state(task_id)

    direct_exit, direct_route = _route_adapter(
        task_id,
        ["REASONING", "TEXT_GENERATION"],
    )
    assert direct_exit == 0
    _assert_route(direct_route, task_id, expect_incomplete=True)

    rejected_exit, rejected = _route_adapter(
        task_id,
        ["REASONING", "NOT_A_CAPABILITY"],
    )
    assert rejected_exit == 2
    assert rejected["status"] == "ERROR"
    assert rejected["error"]["code"] == "FOIL_ROUTE_CAPABILITY_UNKNOWN"
    assert rejected["authority_ceiling"] == "ADAPTATION_ONLY"
    assert all(value is False for value in rejected["authority"].values())

    server = phase5.Phase5Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    original_home = os.environ.get("HOME")
    try:
        with tempfile.TemporaryDirectory(prefix="gauntlet-phase7-") as temporary:
            home = Path(temporary)
            runtime = home / ".gauntlet" / "runtime"
            phase5._write_runtime_config(runtime, server.server_address[1])
            os.environ["HOME"] = str(home)

            from gauntlet_host.launcher import run_worker_turn
            from gauntlet_host.finalizer import finalize_worker_result

            worker = run_worker_turn(
                (
                    "Use gauntlet_task_status, then report that status was "
                    "observed."
                ),
                task_id=task_id,
                cwd=REPO,
                model="phase5-mock",
                provider="custom",
                timeout_seconds=90,
            )
            assert worker.status.value == "OK"
            assert worker.event == "worker.turn_completed"
            assert worker.payload["final_response"] == "phase5 status observed"
            assert worker.payload["usage"]["api_calls"] == 2
            route = worker.payload.get("foil_route")
            assert isinstance(route, dict)
            _assert_route(route, task_id, expect_incomplete=False)

            finalized = finalize_worker_result(REPO, task_id, worker)
            assert finalized.state == "UNRESOLVED"
            assert finalized.accepted is False
            assert finalized.final_response == "phase5 status observed"
            assert finalized.release_gate_invoked is True
            assert finalized.release_gate_verdict == "UNKNOWN"
            assert finalized.release_eligible is False
            assert finalized.task_release_performed is False
            assert finalized.canonical_receipt_created is False

            request = _first_prompt_request(server.chat_requests, phase5)
            prompt_text = _prompt_text(request, phase5)
            assert ROUTE_MARKER in prompt_text
            assert route["content_hash"] in prompt_text
            assert RAW_CLAIM not in prompt_text
            assert "This is proposal-only routing guidance." in prompt_text

            tool_request = phase5._tool_request(server.chat_requests)
            result_request = phase5._result_request(server.chat_requests)
            names = {
                item["function"]["name"]
                for item in tool_request.get("tools", [])
            }
            assert {"gauntlet_task_status", "gauntlet_release_status"} <= names
            tool_messages = [
                message
                for message in result_request.get("messages", [])
                if message.get("tool_call_id") == phase5.TARGET_CALL_ID
            ]
            assert len(tool_messages) == 1
            status = json.loads(tool_messages[0]["content"])
            assert status["task_id"] == task_id
            assert status["release"]["verdict"] == "UNKNOWN"
            assert status["read_only"] is True
            assert status["mutation_performed"] is False
            assert all(value is False for value in status["authority"].values())

            observations = []
            for path in sorted((runtime / "observations").rglob("*.json")):
                observations.append(json.loads(path.read_text(encoding="utf-8")))
            matching = [
                item
                for item in observations
                if item.get("tool") == "gauntlet_task_status"
            ]
            assert len(matching) == 1
            assert matching[0]["authority_ceiling"] == "OBSERVATION_ONLY"
            assert matching[0]["canonical_receipt_created"] is False
            assert matching[0]["canonical_state_mutated"] is False
            assert not (home / ".hermes").exists()

            after = phase5._task_state(task_id)
            task = json.loads((phase5.TASKS / f"{task_id}.json").read_text())
            assert after == before
            assert task["active"] is True
            assert task["released"] is False
            assert not any(phase5.RECEIPTS.glob("*.json"))

            summary = {
                "schema": "gauntlet.fast-checkpoint-verification.v1",
                "fast_milestone": "FAST-P7",
                "task_id": task_id,
                "model_round_trips": len(server.chat_requests),
                "route_injected_before_first_model_request": True,
                "route_mode": route["mode"],
                "route_authority_ceiling": route["authority_ceiling"],
                "profile_data_transmitted": False,
                "toolset_narrowing_applied": False,
                "capability_bundle_complete": (
                    route["capability_bundle_complete"]
                ),
                "missing_requirements": len(route["missing_capabilities"]),
                "release_gate_verdict": finalized.release_gate_verdict,
                "unresolved_not_accepted": finalized.accepted is False,
                "canonical_task_unchanged": after == before,
                "canonical_receipts_created": 0,
            }
            print(json.dumps(summary, indent=2, sort_keys=True))
    finally:
        if original_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = original_home
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
