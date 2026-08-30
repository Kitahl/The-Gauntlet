#!/usr/bin/env python3
"""Non-destructive localhost qualification for TOKEN-200/300/500."""

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
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
PINNED_HERMES = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
CURRENT_PROMPT = "Retrieve NEEDLE-RETRIEVED-MARKER and use selected context."
OLD_DROP = "OLD-UNRELATED-DROP-MARKER"
RELEVANT = "NEEDLE-RETRIEVED-MARKER"
RECENT = "RECENT-PRESERVED-MARKER"
JIT_SELECTED = "JIT-SELECTED-PROCEDURE-MARKER"
JIT_UNSELECTED = "JIT-UNSELECTED-MUST-NOT-APPEAR"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from gauntlet_host.ipc import WorkerStatus  # noqa: E402
from gauntlet_host.launcher import run_worker_turn  # noqa: E402
from gauntlet_host.runtime_profile import prepare_runtime_profile  # noqa: E402
from gauntlet_host.session_binding import derive_session_id  # noqa: E402


def _load_support() -> Any:
    path = REPO / ".github" / "token100_verify.py"
    spec = importlib.util.spec_from_file_location("token100_support", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load TOKEN-100 localhost fixture support")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


support = _load_support()


def _snippet() -> dict[str, str]:
    content = JIT_SELECTED + ": use the bounded task procedure."
    return {
        "snippet_id": "skill-token230500-selected",
        "kind": "skill",
        "provenance": "fixture://token230500/selected-skill/v1",
        "source_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content": content,
        "authority": "CONTEXT_ONLY",
    }


def _seed_long_session(runtime: Path, task_id: str) -> tuple[str, int]:
    profile = prepare_runtime_profile(runtime)
    session_id = derive_session_id(task_id, profile.session_binding_key_path)
    vendor = str(REPO / "vendor" / "hermes-agent")
    inserted = vendor not in sys.path
    if inserted:
        sys.path.insert(0, vendor)
    try:
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            db.create_session(session_id, "gauntlet")
            rows = [
                OLD_DROP + " " + ("a" * 2_400),
                RELEVANT + " " + ("b" * 2_400),
                "recent-one " + ("c" * 2_400),
                "recent-two " + ("d" * 2_400),
                RECENT + " " + ("e" * 2_400),
            ]
            for index, content in enumerate(rows):
                db.append_message(session_id, "user", content)
                db.append_message(session_id, "assistant", f"seed-answer-{index}")
            return session_id, db.message_count(session_id)
        finally:
            db.close()
    finally:
        if inserted and sys.path and sys.path[0] == vendor:
            sys.path.pop(0)


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


def _message_texts(request: dict[str, Any]) -> str:
    messages = request.get("messages")
    if not isinstance(messages, list):
        messages = request.get("input")
    return json.dumps(messages, ensure_ascii=False, separators=(",", ":"))


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

    server = support.LeanServer()
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
    repository_state_before = support._canonical_state_digest(REPO)

    try:
        with tempfile.TemporaryDirectory(prefix="gauntlet-token230500-") as temporary:
            home = Path(temporary)
            runtime = home / ".gauntlet" / "runtime"
            support.phase5._write_runtime_config(runtime, server.server_address[1])
            os.environ["HOME"] = str(home)
            os.environ["USERPROFILE"] = str(home)
            os.environ.pop("HERMES_HOME", None)
            os.environ["GAUNTLET_TOKEN_WORKLOAD_ID"] = "TOKEN230500_LIVE"

            workspace = home / "workspace"
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
            shutil.copytree(REPO / "gauntlet_host", workspace / "gauntlet_host", ignore=ignore)
            shutil.copytree(REPO / "tools", workspace / "tools", ignore=ignore)
            (workspace / "vendor" / "hermes-agent").mkdir(parents=True)
            task_id, _ = support._create_task(workspace)
            workspace_state_before = support._canonical_state_digest(workspace)

            session_id, seeded_count = _seed_long_session(runtime, task_id)
            assert seeded_count == 10

            result = run_worker_turn(
                CURRENT_PROMPT,
                task_id=task_id,
                cwd=workspace,
                model="phase5-mock",
                provider="custom",
                jit_context=[_snippet()],
                timeout_seconds=180,
            )
            if result.status is not WorkerStatus.OK:
                raise AssertionError(
                    {
                        "worker_error": str(result.error or result),
                        "provider_requests": len(server.chat_requests),
                    }
                )

            requests = support._conversation_requests(server.chat_requests)
            assert len(requests) == 1, len(requests)
            request = requests[0]
            wire_text = _message_texts(request)
            assert OLD_DROP not in wire_text
            assert RELEVANT in wire_text
            assert RECENT in wire_text
            assert JIT_SELECTED in wire_text
            assert JIT_UNSELECTED not in wire_text
            assert CURRENT_PROMPT in wire_text
            assert "[GAUNTLET LEAN VOLATILE CONTEXT]" in wire_text
            assert "[GAUNTLET JIT SELECTED CONTEXT]" in wire_text
            assert support._tool_names(request) == {
                "gauntlet_task_status_compact",
                "gauntlet_obligation_get",
                "gauntlet_release_status",
            }

            tool_surface = result.payload["tool_surface"]
            assert tool_surface["toolset_name"] == "gauntlet-active-v1"
            assert tool_surface["active_manifest_hash"] == tool_surface["planned_manifest_hash"]
            assert tool_surface["missing_required_names"] == []
            assert tool_surface["silent_widening_performed"] is False
            assert set(tool_surface["tool_names"]) == support._tool_names(request)

            sparse = result.payload["sparse_context"]
            assert sparse["engine"] == "gauntlet-sparse"
            assert sparse["activated"] is True
            assert sparse["selected_messages"] < sparse["input_messages"]
            assert sparse["selected_chars"] < sparse["input_chars"]
            assert sparse["retrieved_units"] >= 1
            assert sparse["recent_units"] == 3
            assert sparse["tool_closure_preserved"] is True
            assert sparse["persisted_transcript_mutated"] is False
            assert sparse["stable_system_prefix_messages"] >= 1
            assert sparse["top_k_session_retrieval"] is True

            jit = result.payload["jit_context"]
            assert jit == {
                "selected_snippet_count": 1,
                "profile_isolated": True,
                "task_binding_isolated": True,
                "authority": "CONTEXT_ONLY",
                "persisted": False,
            }
            assert result.payload["session_id"] == session_id
            assert result.payload["session_resumed"] is True
            assert result.payload["final_response"] == "lean auxiliary response"
            assert result.payload["usage"]["api_calls"] == 1

            persisted = _persisted_conversation(runtime, session_id)
            persisted_text = json.dumps(persisted, ensure_ascii=False)
            assert OLD_DROP in persisted_text
            assert RELEVANT in persisted_text
            assert RECENT in persisted_text
            assert CURRENT_PROMPT in persisted_text
            assert JIT_SELECTED not in persisted_text
            assert "[GAUNTLET JIT SELECTED CONTEXT]" not in persisted_text
            assert len([row for row in persisted if row.get("role") == "user"]) == 6

            assert workspace_state_before == support._canonical_state_digest(workspace)
            assert repository_state_before == support._canonical_state_digest(REPO)
            assert not any((workspace / ".egrt" / "state" / "runtime" / "receipts").glob("*.json"))

            running_commit, running_tree = support._git_identity()
            manifest = {
                "schema": "gauntlet.token-200-300-500-qualification.v1",
                "phases": ["TOKEN-200", "TOKEN-300", "TOKEN-500"],
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
                    "fresh_availability_before_agent_construction": True,
                    "explicit_capability_specs": True,
                    "active_manifest_hash_bound": True,
                    "silent_tool_widening": False,
                    "model_visible_tools": 3,
                    "sparse_context_activated": True,
                    "stable_system_prefix_preserved": True,
                    "current_user_turn_preserved": True,
                    "active_tool_closure_preserved": True,
                    "recent_turns_preserved": 3,
                    "top_k_retrieval_observed": True,
                    "irrelevant_old_unit_dropped": True,
                    "persisted_transcript_unchanged_by_selection": True,
                    "jit_selected_snippets": 1,
                    "jit_unselected_snippet_absent": True,
                    "jit_task_profile_isolated": True,
                    "jit_authority": "CONTEXT_ONLY",
                    "canonical_state_unchanged": True,
                    "canonical_receipts_created": 0,
                },
                "counts": {
                    "provider_requests": len(requests),
                    "seeded_messages": seeded_count,
                    "persisted_messages_after_turn": len(persisted),
                    "input_messages": sparse["input_messages"],
                    "selected_messages": sparse["selected_messages"],
                    "input_chars": sparse["input_chars"],
                    "selected_chars": sparse["selected_chars"],
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
                        "input_messages": sparse["input_messages"],
                        "selected_messages": sparse["selected_messages"],
                        "input_chars": sparse["input_chars"],
                        "selected_chars": sparse["selected_chars"],
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
