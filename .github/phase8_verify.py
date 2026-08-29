"""Bounded FAST-P8 user-facing CLI and eight-item boot verification."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

PHASE5_HELPER = REPO / ".github" / "phase5_verify.py"
PROMPT = "Use gauntlet_task_status, then report that status was observed."
CANONICAL_CLAIM = "Find a canonical source before release."
ROUTE_MARKER = "[GAUNTLET FOIL ADVISORY ROUTE]"


def _load_phase5() -> Any:
    spec = importlib.util.spec_from_file_location("phase5_verify", PHASE5_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the retained FAST-P5 verification helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(
    command: list[str],
    *,
    environment: dict[str, str],
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO,
        env=environment,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _normalized_whitespace(value: str) -> str:
    return " ".join(value.split())


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


def _observations(runtime: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for path in sorted((runtime / "observations").rglob("*.json")):
        values.append(json.loads(path.read_text(encoding="utf-8")))
    return values


def main() -> None:
    phase5 = _load_phase5()
    phase5._source_boundary()
    shutil.rmtree(REPO / ".egrt", ignore_errors=True)

    command = shutil.which("gauntlet")
    assert command is not None, "editable install did not expose the gauntlet command"

    base_environment = dict(os.environ)
    help_run = _run([command, "--help"], environment=base_environment)
    assert help_run.returncode == 0
    assert "Soul's canonical release gate" in _normalized_whitespace(help_run.stdout)

    chat_help = _run([command, "chat", "--help"], environment=base_environment)
    assert chat_help.returncode == 0
    assert "one explicitly bound canonical task" in _normalized_whitespace(
        chat_help.stdout
    )

    chat_exit = _run(
        [command, "chat", "--root", str(REPO)],
        environment=base_environment,
        input_text="/quit\n",
    )
    assert chat_exit.returncode == 0
    assert "Gauntlet FAST-P8 alpha chat" in chat_exit.stdout

    server = phase5.Phase5Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with tempfile.TemporaryDirectory(prefix="gauntlet-phase8-") as temporary:
            home = Path(temporary)
            runtime = home / ".gauntlet" / "runtime"
            phase5._write_runtime_config(runtime, server.server_address[1])
            environment = dict(base_environment)
            environment.update(
                {
                    "HOME": str(home),
                    "HERMES_YOLO_MODE": "1",
                    "HERMES_ACCEPT_HOOKS": "1",
                    "HERMES_INTERACTIVE": "1",
                }
            )
            completed = _run(
                [
                    command,
                    "--root",
                    str(REPO),
                    "--kind",
                    "DISCOVERY",
                    "--claim",
                    CANONICAL_CLAIM,
                    "--model",
                    "phase5-mock",
                    "--provider",
                    "custom",
                    "--timeout",
                    "90",
                    "--json",
                    PROMPT,
                ],
                environment=environment,
            )
            if completed.stderr:
                print(completed.stderr, file=sys.stderr, end="")
            assert completed.returncode == 2
            finalized = json.loads(completed.stdout)
            print(json.dumps(finalized, indent=2, sort_keys=True))

            task_id = finalized["task_id"]
            assert finalized["schema"] == "gauntlet.finalization.v1"
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

            task_path = phase5.TASKS / f"{task_id}.json"
            task = json.loads(task_path.read_text(encoding="utf-8"))
            assert task["task_id"] == task_id
            assert task["goal_hash"] == hashlib.sha256(PROMPT.encode()).hexdigest()
            assert task["active"] is True
            assert task["released"] is False
            obligations = task["obligations"]
            assert len(obligations) == 1
            assert obligations[0]["kind"] == "DISCOVERY"
            assert obligations[0]["claim"] == CANONICAL_CLAIM
            assert obligations[0]["load_bearing"] is True
            assert obligations[0]["required_module"] == "space"

            prompt_request = _first_prompt_request(server.chat_requests, phase5)
            prompt_text = _prompt_text(prompt_request, phase5)
            assert ROUTE_MARKER in prompt_text
            assert "This is proposal-only routing guidance." in prompt_text
            assert CANONICAL_CLAIM not in prompt_text

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
            assert status["schema"] == "gauntlet.adapter.v1"
            assert status["action"] == "task-status"
            assert status["status"] == "OK"
            assert status["task_id"] == task_id
            assert status["task"]["task_id"] == task_id
            assert status["release"]["verdict"] == "UNKNOWN"
            assert status["read_only"] is True
            assert status["mutation_performed"] is False
            assert all(value is False for value in status["authority"].values())

            observations = _observations(runtime)
            matching = [
                item
                for item in observations
                if item.get("tool") == "gauntlet_task_status"
            ]
            assert len(matching) == 1
            observation = matching[0]
            assert observation["task_id"] == task_id
            assert observation["status"] == "OK"
            assert observation["authority_ceiling"] == "OBSERVATION_ONLY"
            assert observation["canonical_receipt_created"] is False
            assert observation["canonical_state_mutated"] is False

            assert (runtime / "state.db").is_file()
            assert not (home / ".hermes").exists()
            assert not any(phase5.RECEIPTS.glob("*.json"))

            boot_checks = {
                "1_gauntlet_starts": help_run.returncode == 0,
                "2_worker_starts": finalized["worker_status"] == "OK",
                "3_model_responds": bool(finalized["final_response"]),
                "4_runtime_tool_executes": len(tool_messages) == 1,
                "5_gauntlet_task_status_works": status["status"] == "OK",
                "6_runtime_observation_recorded": len(matching) == 1,
                "7_soul_gate_runs": finalized["release_gate_invoked"] is True,
                "8_unresolved_not_cleared": (
                    finalized["accepted"] is False
                    and finalized["release_gate_verdict"] == "UNKNOWN"
                ),
            }
            assert len(boot_checks) == 8
            assert all(boot_checks.values())

            summary = {
                "schema": "gauntlet.fast-checkpoint-verification.v1",
                "fast_milestone": "FAST-P8",
                "task_id": task_id,
                "console_command": command,
                "chat_entry_point_started": True,
                "task_created_by_cli": True,
                "load_bearing_obligation_created": True,
                "foil_route_preserved": True,
                "model_round_trips": len(server.chat_requests),
                "boot_checks": boot_checks,
                "boot_checks_passed": sum(boot_checks.values()),
                "runtime_observations": len(observations),
                "canonical_receipts_created": 0,
                "release_gate_verdict": finalized["release_gate_verdict"],
                "unresolved_not_accepted": finalized["accepted"] is False,
                "ordinary_hermes_home_created": False,
            }
            print(json.dumps(summary, indent=2, sort_keys=True))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
