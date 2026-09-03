"""Bounded FAST-P6 observation bridge and Soul finalizer verification."""

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


def _load_phase5() -> Any:
    spec = importlib.util.spec_from_file_location("phase5_verify", PHASE5_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the retained FAST-P5 verification helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_observations(runtime_home: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for path in sorted((runtime_home / "observations").rglob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        value["_path"] = str(path)
        values.append(value)
    return values


def _forbidden_authority_fields(value: Any) -> set[str]:
    forbidden = {
        "verdict",
        "receipt",
        "receipts",
        "evidence_class",
        "release",
        "released",
        "cleared",
        "obligation_clearance",
    }
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(forbidden.intersection(value))
        for item in value.values():
            found.update(_forbidden_authority_fields(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_forbidden_authority_fields(item))
    return found


def main() -> None:
    phase5 = _load_phase5()
    phase5._source_boundary()
    task_id = phase5._create_task()
    before = phase5._task_state(task_id)
    server = phase5.Phase5Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with tempfile.TemporaryDirectory(prefix="gauntlet-phase6-") as temporary:
            home = Path(temporary)
            runtime = home / ".gauntlet" / "runtime"
            phase5._write_runtime_config(runtime, server.server_address[1])
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
            assert completed.returncode == 2
            finalized = json.loads(completed.stdout)

            assert finalized["schema"] == "gauntlet.finalization.v1"
            assert finalized["task_id"] == task_id
            assert finalized["state"] == "UNRESOLVED"
            assert finalized["accepted"] is False
            assert finalized["final_response"] == "phase5 status observed"
            assert finalized["worker_status"] == "OK"
            assert finalized["worker_event"] == "worker.turn_completed"
            assert finalized["release_gate_invoked"] is True
            assert finalized["release_gate_verdict"] == "UNKNOWN"
            assert finalized["release_eligible"] is False
            assert finalized["task_release_performed"] is False
            assert finalized["canonical_receipt_created"] is False
            assert finalized["unresolved"]

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

            observations = _read_observations(runtime)
            matching = [
                item
                for item in observations
                if item.get("tool") == "gauntlet_task_status"
            ]
            assert len(matching) == 1
            observation = matching[0]
            assert observation["schema"] == "gauntlet.tool-observation.v1"
            assert observation["event"] == "runtime.tool.finished"
            assert observation["task_id"] == task_id
            assert observation["status"] == "OK"
            assert observation["runtime_session_id"]
            assert observation["tool_call_id"] == phase5.TARGET_CALL_ID
            assert len(observation["input_hash"]) == 64
            assert len(observation["output_hash"]) == 64
            assert observation["authority_ceiling"] == "OBSERVATION_ONLY"
            assert observation["canonical_receipt_created"] is False
            assert observation["canonical_state_mutated"] is False
            assert observation["provenance"]["raw_input_persisted"] is False
            assert observation["provenance"]["raw_output_persisted"] is False
            assert not _forbidden_authority_fields(observation)

            after = phase5._task_state(task_id)
            assert after == before
            task = json.loads((phase5.TASKS / f"{task_id}.json").read_text())
            assert task["released"] is False
            assert task["active"] is True
            assert not any(phase5.RECEIPTS.glob("*.json"))
            assert not (home / ".hermes").exists()

            summary = {
                "schema": "gauntlet.fast-checkpoint-verification.v1",
                "fast_milestone": "FAST-P6",
                "task_id": task_id,
                "model_round_trips": len(server.chat_requests),
                "observations_recorded": len(observations),
                "status_observations": len(matching),
                "release_gate_verdict": finalized["release_gate_verdict"],
                "unresolved_not_accepted": finalized["accepted"] is False,
                "canonical_task_unchanged": after == before,
                "canonical_receipts_created": 0,
                "ordinary_hermes_home_created": False,
            }
            print(json.dumps(summary, indent=2, sort_keys=True))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
