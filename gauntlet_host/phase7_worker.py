"""FAST-P7 wrapper that injects one advisory FOIL route before model work."""

from __future__ import annotations

import sys
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    _repo_bootstrap = Path(__file__).resolve().parent.parent
    if str(_repo_bootstrap) not in sys.path:
        sys.path.insert(0, str(_repo_bootstrap))

from gauntlet_host import worker_main as core
from gauntlet_host.constants import GAUNTLET_TOOLSET
from gauntlet_host.ipc import RuntimeRequest, RuntimeResult
from gauntlet_host.lean_context import LeanContext, LeanContextError
from gauntlet_host.tool_surface import (
    ToolSurfaceError,
    compile_live_tool_surface,
    install_compiled_toolset,
)

_ORIGINAL_EXECUTE = core._execute_agent_turn


def _execute_with_foil_route(
    request: RuntimeRequest,
    proof: Any,
) -> RuntimeResult:
    try:
        lean_context = LeanContext.from_metadata(
            request.task_id,
            request.metadata.get("lean_context"),
            session_binding_id=request.session_id or "",
            profile_name=proof.runtime_profile_name,
        )
    except LeanContextError as exc:
        return core._error_result(
            request,
            status=core.WorkerStatus.UNAVAILABLE,
            event="worker.lean_context_unavailable",
            code=exc.code,
            message=exc.message,
            payload=proof.to_payload(),
        )

    route_state: dict[str, Any] = {}

    try:
        with redirect_stdout(sys.stderr):
            from model_tools import get_tool_definitions
            from run_agent import AIAgent

            live_definitions = get_tool_definitions(
                enabled_toolsets=[GAUNTLET_TOOLSET],
                quiet_mode=True,
                skip_tool_search_assembly=True,
            )
            compiled_surface = compile_live_tool_surface(
                lean_context.tool_surface_plan,
                live_definitions,
                requested_toolsets=request.toolsets,
            )
            install_compiled_toolset(compiled_surface)
    except ToolSurfaceError as exc:
        return core._error_result(
            request,
            status=core.WorkerStatus.UNAVAILABLE,
            event="worker.tool_surface_unavailable",
            code=exc.code,
            message=exc.message,
            payload=proof.to_payload(),
        )
    except Exception as exc:
        return core._error_result(
            request,
            status=core.WorkerStatus.UNAVAILABLE,
            event="worker.tool_surface_unavailable",
            code="TOOL_SURFACE_PROBE_FAILED",
            message=core._safe_exception_message(exc),
            payload=proof.to_payload(),
        )

    request = replace(request, toolsets=(compiled_surface.toolset_name,))
    original_run_conversation = AIAgent.run_conversation

    def routed_run_conversation(
        agent: Any,
        prompt: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if route_state.get("applied") is True:
            return original_run_conversation(agent, prompt, *args, **kwargs)

        try:
            routed_prompt = lean_context.inject(prompt)
            engine = getattr(agent, "context_compressor", None)
            if getattr(engine, "name", None) != proof.context_engine_name or not callable(
                getattr(engine, "configure_gauntlet_context", None)
            ):
                raise core.RuntimeExecutionError(
                    "SPARSE_CONTEXT_ENGINE_UNAVAILABLE",
                    "AIAgent did not activate the isolated Gauntlet sparse context engine",
                )
            engine.configure_gauntlet_context(lean_context.sparse_context_plan)
        except LeanContextError as exc:
            raise core.RuntimeExecutionError(exc.code, exc.message) from exc
        except ValueError as exc:
            raise core.RuntimeExecutionError(
                "SPARSE_CONTEXT_CONFIGURATION_INVALID",
                str(exc),
            ) from exc

        route_state["applied"] = True
        route_state["context_engine"] = engine
        if kwargs.get("persist_user_message") is None:
            kwargs["persist_user_message"] = prompt
        return original_run_conversation(
            agent,
            routed_prompt,
            *args,
            **kwargs,
        )

    AIAgent.run_conversation = routed_run_conversation
    try:
        result = _ORIGINAL_EXECUTE(request, proof)
    finally:
        if AIAgent.run_conversation is routed_run_conversation:
            AIAgent.run_conversation = original_run_conversation

    if route_state.get("applied") is not True and result.status.value == "OK":
        return core._error_result(
            request,
            status=core.WorkerStatus.UNAVAILABLE,
            event="worker.lean_context_unavailable",
            code="LEAN_CONTEXT_NOT_APPLIED",
            message="runtime completed without the required lean context",
            payload=proof.to_payload(),
        )

    if route_state.get("applied") is True:
        payload = dict(result.payload)
        payload["foil_route"] = lean_context.foil_route
        payload["lean_context"] = {
            "prefetched_by_parent": True,
            "active_manifest_revision": lean_context.active_manifest_revision,
            "active_manifest_hash": lean_context.active_manifest_hash,
            "route_capsule": lean_context.route_capsule(),
            "compact_status_hash": lean_context.compact_status["content_hash"],
            "route_record_path": lean_context.route_record_path,
            "capsule_metrics": lean_context.capsule_metrics(),
            "stable_prompt_prefix_preserved": True,
            "clean_user_message_persisted": True,
            "extra_model_calls": 0,
        }
        payload["tool_surface"] = compiled_surface.to_payload()
        engine = route_state.get("context_engine")
        selection = getattr(engine, "last_selection", None)
        payload["sparse_context"] = (
            dict(selection)
            if isinstance(selection, dict)
            else {
                "engine": proof.context_engine_name,
                "activated": False,
                "reason": "selection_metrics_unavailable",
                "persisted_transcript_mutated": False,
            }
        )
        payload["jit_context"] = {
            "selected_snippet_count": len(
                (lean_context.sparse_context_plan or {}).get("selected_snippets", [])
            ),
            "profile_isolated": True,
            "task_binding_isolated": True,
            "authority": "CONTEXT_ONLY",
            "persisted": False,
        }
        result = replace(result, payload=payload)
    return result


def main() -> int:
    core._execute_agent_turn = _execute_with_foil_route
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
