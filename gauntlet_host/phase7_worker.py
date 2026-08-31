"""FAST-P7 wrapper that injects one advisory FOIL route before model work."""

from __future__ import annotations

import logging
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
from gauntlet_host.constants import (
    GAUNTLET_ACTIVE_TOOLS,
    GAUNTLET_TOOLSET,
    GOVERNED_PROFILE_NAME,
)
from gauntlet_host.ipc import RuntimeRequest, RuntimeResult
from gauntlet_host.lean_context import LeanContext, LeanContextError
from gauntlet_host.tool_results import (
    ARTIFACT_TOOL_NAME,
    OperationalArtifactStore,
    ToolResultLifecycleError,
)
from gauntlet_host.tool_surface import (
    ToolSurfaceError,
    compile_live_tool_surface,
    install_compiled_toolset,
)

_ORIGINAL_EXECUTE = core._execute_agent_turn


def _tool_definition_names(definitions: Any) -> tuple[str, ...]:
    names: list[str] = []
    for definition in definitions if isinstance(definitions, list) else []:
        function = definition.get("function") if isinstance(definition, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        if isinstance(name, str) and name and name not in names:
            names.append(name)
    return tuple(names)


def _execute_with_foil_route(
    request: RuntimeRequest,
    proof: Any,
) -> RuntimeResult:
    governed = proof.runtime_profile_name == GOVERNED_PROFILE_NAME
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
        artifact_store = OperationalArtifactStore(
            proof.runtime_home,
            task_id=request.task_id,
            session_id=request.session_id or "",
        )
    except ToolResultLifecycleError as exc:
        return core._error_result(
            request,
            status=core.WorkerStatus.UNAVAILABLE,
            event="worker.tool_result_lifecycle_unavailable",
            code=exc.code,
            message=exc.message,
            payload=proof.to_payload(),
        )

    try:
        with redirect_stdout(sys.stderr):
            from agent import tool_executor
            if governed:
                from hermes_cli.mcp_startup import ensure_mcp_discovery_before_agent_build

                ensure_mcp_discovery_before_agent_build(
                    logger=logging.getLogger("gauntlet.governed.mcp"),
                    timeout=10.0,
                    single_query=True,
                    thread_name="gauntlet-governed-mcp-discovery",
                )
            from model_tools import get_tool_definitions
            from run_agent import AIAgent

            live_definitions = get_tool_definitions(
                enabled_toolsets=(
                    list(request.toolsets) if governed else [GAUNTLET_TOOLSET]
                ),
                quiet_mode=True,
                skip_tool_search_assembly=not governed,
            )
            live_names = _tool_definition_names(live_definitions)
            if governed:
                missing = sorted(set(GAUNTLET_ACTIVE_TOOLS) - set(live_names))
                if missing:
                    raise ToolSurfaceError(
                        "GOVERNED_GAUNTLET_TOOLS_MISSING",
                        "governed Hermes surface omitted required Gauntlet tools: "
                        + ", ".join(missing),
                    )
                compiled_surface = None
                governed_surface = {
                    "profile": GOVERNED_PROFILE_NAME,
                    "mode": "native-dynamic",
                    "tool_count": len(live_names),
                    "required_gauntlet_tools": list(GAUNTLET_ACTIVE_TOOLS),
                    "gauntlet_tools_verified": True,
                    "dynamic_mcp_assembly_enabled": True,
                    "requested_toolsets": list(request.toolsets),
                }
            else:
                compiled_surface = compile_live_tool_surface(
                    lean_context.tool_surface_plan,
                    live_definitions,
                    requested_toolsets=request.toolsets,
                )
                install_compiled_toolset(compiled_surface)
                governed_surface = None
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

    if compiled_surface is not None:
        request = replace(request, toolsets=(compiled_surface.toolset_name,))
    original_run_conversation = AIAgent.run_conversation
    original_result_persistence = tool_executor.maybe_persist_tool_result

    def managed_result_persistence(*args: Any, **kwargs: Any) -> Any:
        content = kwargs.get("content", args[0] if args else None)
        tool_name = str(kwargs.get("tool_name", args[1] if len(args) > 1 else ""))
        tool_call_id = str(kwargs.get("tool_use_id", args[2] if len(args) > 2 else ""))
        if tool_name == ARTIFACT_TOOL_NAME:
            return content
        try:
            externalized = artifact_store.externalize(
                content,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
            )
        except ToolResultLifecycleError as exc:
            route_state["lifecycle_error"] = exc
            return artifact_store.rejection(content, exc)
        if externalized is None:
            return original_result_persistence(*args, **kwargs)
        engine = route_state.get("context_engine")
        register_result = getattr(engine, "register_externalized_result", None)
        if not callable(register_result):
            exc = ToolResultLifecycleError(
                "TOOL_RESULT_CONTEXT_ENGINE_UNAVAILABLE",
                "sparse context engine could not project first-call tool output",
            )
            route_state["lifecycle_error"] = exc
            return artifact_store.rejection(content, exc)
        try:
            register_result(externalized.artifact_id, externalized.content)
        except Exception as unexpected:
            exc = ToolResultLifecycleError(
                "TOOL_RESULT_FIRST_VISIBILITY_FAILED",
                core._safe_exception_message(unexpected),
            )
            route_state["lifecycle_error"] = exc
            return artifact_store.rejection(content, exc)
        return externalized.reference

    def routed_run_conversation(
        agent: Any,
        prompt: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if route_state.get("applied") is True:
            return original_run_conversation(agent, prompt, *args, **kwargs)

        try:
            routed_prompt = lean_context.inject(prompt, proof.runtime_profile_name)
            engine = getattr(agent, "context_compressor", None)
            if not governed:
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
    if not governed:
        tool_executor.maybe_persist_tool_result = managed_result_persistence
    try:
        result = _ORIGINAL_EXECUTE(request, proof)
    finally:
        if AIAgent.run_conversation is routed_run_conversation:
            AIAgent.run_conversation = original_run_conversation
        if tool_executor.maybe_persist_tool_result is managed_result_persistence:
            tool_executor.maybe_persist_tool_result = original_result_persistence

    lifecycle_error = route_state.get("lifecycle_error")
    if isinstance(lifecycle_error, ToolResultLifecycleError) and result.status.value == "OK":
        return core._error_result(
            request,
            status=core.WorkerStatus.UNAVAILABLE,
            event="worker.tool_result_lifecycle_unavailable",
            code=lifecycle_error.code,
            message=lifecycle_error.message,
            payload=proof.to_payload() | {"tool_result_lifecycle": artifact_store.metrics()},
        )

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
        payload["tool_surface"] = (
            governed_surface
            if governed_surface is not None
            else compiled_surface.to_payload()
        )
        engine = route_state.get("context_engine")
        selection = getattr(engine, "last_selection", None)
        payload["sparse_context"] = (
            {
                "engine": proof.context_engine_name,
                "activated": False,
                "reason": "governed_profile_uses_native_context_engine",
                "persisted_transcript_mutated": False,
            }
            if governed
            else (
                dict(selection)
                if isinstance(selection, dict)
                else {
                    "engine": proof.context_engine_name,
                    "activated": False,
                    "reason": "selection_metrics_unavailable",
                    "persisted_transcript_mutated": False,
                }
            )
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
        payload["tool_result_lifecycle"] = (
            {"mode": "native-hermes", "gauntlet_externalization_active": False}
            if governed
            else artifact_store.metrics()
            | {
                "rehydration_tool": ARTIFACT_TOOL_NAME,
                "first_visibility": (
                    engine.tool_result_lifecycle_metrics()
                    if callable(getattr(engine, "tool_result_lifecycle_metrics", None))
                    else {"available": False}
                ),
            }
        )
        result = replace(result, payload=payload)
    return result


def main() -> int:
    core._execute_agent_turn = _execute_with_foil_route
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
