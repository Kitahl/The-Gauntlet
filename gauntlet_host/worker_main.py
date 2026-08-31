"""Isolated bootstrap and one-turn execution for the vendored runtime."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
import sys
import traceback
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TextIO

if __package__ in {None, ""}:
    _repo_bootstrap = Path(__file__).resolve().parent.parent
    if str(_repo_bootstrap) not in sys.path:
        sys.path.insert(0, str(_repo_bootstrap))

from gauntlet_host.aux_measurement import auxiliary_measurement_scope
from gauntlet_host.constants import (
    DEFAULT_AGENT_RUN_BUDGET_SECONDS,
    EXPECTED_HERMES_COMMIT,
    EXPECTED_HERMES_REPOSITORY,
    EXPECTED_HERMES_TAG,
    GAUNTLET_TOOLS_ROOT,
    MAX_AGENT_RUN_BUDGET_SECONDS,
    MAX_OPERATIONAL_ERROR_CHARS,
    REPO_ROOT,
    VENDOR_ROOT,
    VENDOR_SNAPSHOT_MANIFEST,
    VENDOR_TOOLS_ROOT,
)
from gauntlet_host.ipc import (
    IPCContractError,
    RuntimeRequest,
    RuntimeResult,
    WorkerError,
    WorkerOperation,
    WorkerStatus,
    contract_error_result,
    decode_request,
    write_result,
)
from gauntlet_host.lean_context import drop_stale_lean_context_sidecars
from gauntlet_host.runtime_profile import (
    RuntimeProfile,
    RuntimeProfileError,
    prepare_runtime_profile,
)
from gauntlet_host.token_measurement import summarize_measurements


class WorkerBootstrapError(RuntimeError):
    """Fail-closed error raised before vendored runtime execution."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class RuntimeExecutionError(RuntimeError):
    """Typed operational failure raised while constructing or running AIAgent."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class NamespaceProof:
    """Evidence that this interpreter resolved Hermes's top-level tools package."""

    namespace_verified: bool
    tools_module: str
    tools_origin: str
    vendor_tools_root: str
    gauntlet_tools_root: str
    repo_root: str
    vendor_root: str
    cwd: str
    sys_path_head: str
    pythonpath: str
    upstream_repository: str
    upstream_tag: str
    upstream_commit: str
    runtime_home: str
    runtime_config: str
    runtime_config_sha256: str
    runtime_profile_name: str
    context_engine_name: str
    background_review_enabled: bool
    automatic_title_generation_enabled: bool
    memory_write_approval: bool
    memory_enabled: bool
    user_profile_enabled: bool
    skills_write_approval: bool
    skills_project_discovery: bool
    execution_guidance_enabled: bool
    task_completion_guidance_enabled: bool
    parallel_tool_call_guidance_enabled: bool
    coding_context_enabled: bool
    context_files_enabled: bool
    environment_probe_enabled: bool
    verify_on_stop_enabled: bool
    mcp_discovery_enabled: bool
    delegation_enabled: bool
    auto_release_enabled: bool
    max_iterations: int

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def _resolved(path: str | os.PathLike[str]) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _module_origin(module: Any) -> Path | None:
    origin = getattr(module, "__file__", None)
    if not origin:
        return None
    return _resolved(origin)


def _validate_snapshot_manifest() -> dict[str, Any]:
    if not VENDOR_SNAPSHOT_MANIFEST.is_file():
        raise WorkerBootstrapError(
            "VENDOR_MANIFEST_MISSING",
            f"missing vendored snapshot manifest: {VENDOR_SNAPSHOT_MANIFEST}",
        )

    try:
        value = json.loads(VENDOR_SNAPSHOT_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerBootstrapError(
            "VENDOR_MANIFEST_INVALID",
            f"cannot read vendored snapshot manifest: {exc}",
        ) from exc

    if not isinstance(value, dict):
        raise WorkerBootstrapError(
            "VENDOR_MANIFEST_INVALID",
            "vendored snapshot manifest must be a JSON object",
        )

    expected = {
        "destination": "vendor/hermes-agent",
        "state": "materialized",
        "upstream_repository": EXPECTED_HERMES_REPOSITORY,
        "upstream_tag": EXPECTED_HERMES_TAG,
        "upstream_commit": EXPECTED_HERMES_COMMIT,
    }
    mismatches = [
        f"{key}={value.get(key)!r} (expected {expected_value!r})"
        for key, expected_value in expected.items()
        if value.get(key) != expected_value
    ]
    if value.get("local_modifications") != []:
        mismatches.append("local_modifications must be an empty array")
    if mismatches:
        raise WorkerBootstrapError(
            "VENDOR_MANIFEST_MISMATCH",
            "; ".join(mismatches),
        )
    return value


def _reject_preloaded_gauntlet_tools() -> None:
    collisions: list[str] = []
    for name, module in tuple(sys.modules.items()):
        if name != "tools" and not name.startswith("tools."):
            continue
        origin = _module_origin(module)
        if origin is None or not _is_within(origin, VENDOR_TOOLS_ROOT):
            rendered_origin = str(origin) if origin is not None else "<unknown>"
            collisions.append(f"{name}={rendered_origin}")

    if collisions:
        raise WorkerBootstrapError(
            "TOOLS_NAMESPACE_PRELOADED",
            "non-vendored tools modules were loaded before isolation: "
            + ", ".join(sorted(collisions)),
        )


def _isolate_sys_path() -> None:
    vendor_text = str(VENDOR_ROOT)
    retained: list[str] = [vendor_text]
    seen: set[str] = {vendor_text}

    for entry in sys.path:
        if not entry:
            continue
        resolved = _resolved(entry)
        if _is_within(resolved, REPO_ROOT) and not _is_within(resolved, VENDOR_ROOT):
            continue
        rendered = str(resolved)
        if rendered in seen:
            continue
        seen.add(rendered)
        retained.append(rendered)

    sys.path[:] = retained
    os.environ["PYTHONPATH"] = vendor_text
    os.chdir(VENDOR_ROOT)
    importlib.invalidate_caches()


def _verify_tools_spec() -> None:
    spec = importlib.util.find_spec("tools")
    if spec is None or spec.origin is None:
        raise WorkerBootstrapError(
            "TOOLS_NAMESPACE_UNRESOLVED",
            "Python could not resolve the vendored top-level tools package",
        )

    origin = _resolved(spec.origin)
    if not _is_within(origin, VENDOR_TOOLS_ROOT):
        raise WorkerBootstrapError(
            "TOOLS_NAMESPACE_COLLISION",
            f"tools resolved outside the vendor root: {origin}",
        )

    locations = spec.submodule_search_locations
    if locations is None:
        raise WorkerBootstrapError(
            "TOOLS_NAMESPACE_NOT_PACKAGE",
            f"tools did not resolve as a package: {origin}",
        )
    for location in locations:
        if not _is_within(_resolved(location), VENDOR_TOOLS_ROOT):
            raise WorkerBootstrapError(
                "TOOLS_NAMESPACE_COLLISION",
                f"tools package search path escaped the vendor root: {location}",
            )


def bootstrap_vendor_runtime(profile: RuntimeProfile) -> NamespaceProof:
    """Enter the isolated vendor import environment and prove tools resolution."""

    if not VENDOR_ROOT.is_dir():
        raise WorkerBootstrapError(
            "VENDOR_ROOT_MISSING",
            f"missing vendored runtime root: {VENDOR_ROOT}",
        )
    if not (VENDOR_TOOLS_ROOT / "__init__.py").is_file():
        raise WorkerBootstrapError(
            "VENDOR_TOOLS_MISSING",
            f"missing vendored tools package: {VENDOR_TOOLS_ROOT}",
        )
    if not (GAUNTLET_TOOLS_ROOT / "__init__.py").is_file():
        raise WorkerBootstrapError(
            "GAUNTLET_TOOLS_MISSING",
            f"missing Gauntlet tools package: {GAUNTLET_TOOLS_ROOT}",
        )

    manifest = _validate_snapshot_manifest()
    _reject_preloaded_gauntlet_tools()
    _isolate_sys_path()
    _verify_tools_spec()

    tools_module = importlib.import_module("tools")
    tools_origin = _module_origin(tools_module)
    if tools_origin is None or not _is_within(tools_origin, VENDOR_TOOLS_ROOT):
        raise WorkerBootstrapError(
            "TOOLS_NAMESPACE_COLLISION",
            f"imported tools module escaped the vendor root: {tools_origin}",
        )

    return NamespaceProof(
        namespace_verified=True,
        tools_module=tools_module.__name__,
        tools_origin=str(tools_origin),
        vendor_tools_root=str(VENDOR_TOOLS_ROOT),
        gauntlet_tools_root=str(GAUNTLET_TOOLS_ROOT),
        repo_root=str(REPO_ROOT),
        vendor_root=str(VENDOR_ROOT),
        cwd=os.getcwd(),
        sys_path_head=sys.path[0],
        pythonpath=os.environ["PYTHONPATH"],
        upstream_repository=str(manifest["upstream_repository"]),
        upstream_tag=str(manifest["upstream_tag"]),
        upstream_commit=str(manifest["upstream_commit"]),
        runtime_home=profile.runtime_home,
        runtime_config=profile.config_path,
        runtime_config_sha256=profile.config_sha256,
        runtime_profile_name=profile.profile_name,
        context_engine_name=profile.context_engine_name,
        background_review_enabled=profile.background_review_enabled,
        automatic_title_generation_enabled=profile.automatic_title_generation_enabled,
        memory_write_approval=profile.memory_write_approval,
        memory_enabled=profile.memory_enabled,
        user_profile_enabled=profile.user_profile_enabled,
        skills_write_approval=profile.skills_write_approval,
        skills_project_discovery=profile.skills_project_discovery,
        execution_guidance_enabled=profile.execution_guidance_enabled,
        task_completion_guidance_enabled=profile.task_completion_guidance_enabled,
        parallel_tool_call_guidance_enabled=(profile.parallel_tool_call_guidance_enabled),
        coding_context_enabled=profile.coding_context_enabled,
        context_files_enabled=profile.context_files_enabled,
        environment_probe_enabled=profile.environment_probe_enabled,
        verify_on_stop_enabled=profile.verify_on_stop_enabled,
        mcp_discovery_enabled=profile.mcp_discovery_enabled,
        delegation_enabled=profile.delegation_enabled,
        auto_release_enabled=profile.auto_release_enabled,
        max_iterations=profile.max_iterations,
    )


def _error_result(
    request: RuntimeRequest,
    *,
    status: WorkerStatus,
    event: str,
    code: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> RuntimeResult:
    return RuntimeResult(
        request_id=request.request_id,
        task_id=request.task_id,
        status=status,
        event=event,
        payload=payload or {},
        error=WorkerError(code=code, message=message),
    )


def _safe_exception_message(exc: BaseException) -> str:
    text = " ".join(str(exc).split())
    text = re.sub(
        r"(?i)(api[_-]?key|authorization|token|secret)\s*[:=]\s*\S+",
        r"\1=<redacted>",
        text,
    )
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "<redacted-key>", text)
    if not text:
        text = exc.__class__.__name__
    return text[:MAX_OPERATIONAL_ERROR_CHARS]


def _run_budget(request: RuntimeRequest) -> float:
    raw = request.metadata.get(
        "run_budget_seconds",
        DEFAULT_AGENT_RUN_BUDGET_SECONDS,
    )
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise RuntimeExecutionError(
            "INVALID_RUN_BUDGET",
            "run_budget_seconds must be numeric",
        )
    value = float(raw)
    if value <= 0 or value > MAX_AGENT_RUN_BUDGET_SECONDS:
        raise RuntimeExecutionError(
            "INVALID_RUN_BUDGET",
            (
                "run_budget_seconds must be greater than 0 and at most "
                f"{MAX_AGENT_RUN_BUDGET_SECONDS:g}"
            ),
        )
    return value


def _model_and_provider(
    config: dict[str, Any],
    request: RuntimeRequest,
) -> tuple[str, str | None]:
    model_config = config.get("model")
    configured_model = ""
    configured_provider = ""

    if isinstance(model_config, str):
        configured_model = model_config.strip()
    elif isinstance(model_config, dict):
        raw_model = model_config.get("default") or model_config.get("model") or ""
        if isinstance(raw_model, dict):
            try:
                from hermes_cli.config import split_model_config_default

                configured_model, nested_provider = split_model_config_default(raw_model)
                configured_provider = str(
                    nested_provider or model_config.get("provider") or ""
                ).strip()
            except Exception:
                configured_model = str(raw_model.get("model") or "").strip()
                configured_provider = str(
                    raw_model.get("provider") or model_config.get("provider") or ""
                ).strip()
        else:
            configured_model = str(raw_model or "").strip()
            configured_provider = str(model_config.get("provider") or "").strip()

    effective_model = (request.model or "").strip() or configured_model
    effective_provider = (request.provider or "").strip() or configured_provider or None

    if not effective_model:
        raise RuntimeExecutionError(
            "MODEL_NOT_CONFIGURED",
            "no model was supplied and the Gauntlet runtime profile has no default model",
        )

    if request.model and not request.provider:
        try:
            from hermes_cli.models import detect_provider_for_model

            detected = detect_provider_for_model(
                effective_model,
                effective_provider or "auto",
            )
        except Exception:
            detected = None
        if detected:
            effective_provider, effective_model = detected

    return effective_model, effective_provider


def _toolsets(request: RuntimeRequest) -> list[str]:
    return list(dict.fromkeys(request.toolsets))


def _usage_payload(result: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
        "total_tokens",
        "api_calls",
        "estimated_cost_usd",
        "cost_status",
        "cost_source",
        "service_tier",
    )
    return {field: result.get(field) for field in fields}


def _cleanup_agent(agent: Any, session_db: Any) -> None:
    if agent is not None:
        try:
            session_messages = getattr(agent, "_session_messages", None)
            if isinstance(session_messages, list):
                agent.shutdown_memory_provider(session_messages)
            else:
                agent.shutdown_memory_provider()
        except Exception:
            pass
        try:
            agent.close()
        except Exception:
            pass
    if session_db is not None:
        try:
            session_db.close()
        except Exception:
            pass


def _execute_agent_turn(
    request: RuntimeRequest,
    proof: NamespaceProof,
) -> RuntimeResult:
    if not request.session_id:
        return _error_result(
            request,
            status=WorkerStatus.ERROR,
            event="worker.request_rejected",
            code="SESSION_BINDING_MISSING",
            message="run requests require a parent-derived Hermes session binding",
            payload=proof.to_payload(),
        )

    os.environ["GAUNTLET_TASK_ID"] = request.task_id
    if proof.context_files_enabled:
        project_cwd = Path(request.cwd or "").expanduser().resolve(strict=False)
        if not project_cwd.is_dir():
            return _error_result(
                request,
                status=WorkerStatus.ERROR,
                event="worker.request_rejected",
                code="PROJECT_CWD_INVALID",
                message="governed runtime requires an existing project working directory",
                payload=proof.to_payload(),
            )
        os.chdir(project_cwd)
    for bypass in (
        "HERMES_YOLO_MODE",
        "HERMES_ACCEPT_HOOKS",
        "HERMES_INTERACTIVE",
    ):
        os.environ.pop(bypass, None)

    agent = None
    session_db = None
    auxiliary_scope = None
    try:
        run_budget = _run_budget(request)
        with redirect_stdout(sys.stderr):
            from hermes_cli.config import load_config
            from hermes_cli.fallback_config import get_fallback_chain
            from hermes_cli.runtime_provider import resolve_runtime_provider
            from hermes_state import SessionDB
            from run_agent import AIAgent

            config = load_config()
            effective_model, effective_provider = _model_and_provider(config, request)
            runtime = resolve_runtime_provider(
                requested=effective_provider,
                target_model=effective_model,
            )
            os.environ["GAUNTLET_REQUESTED_PROVIDER"] = str(
                runtime.get("requested_provider") or effective_provider or ""
            )
            auxiliary_scope = auxiliary_measurement_scope()
            auxiliary_scope.__enter__()
            session_db = SessionDB()
            runtime_session_id = request.session_id
            conversation_history = None
            stale_lean_context_rows_dropped = 0
            if session_db.get_session(runtime_session_id) is not None:
                runtime_session_id = (
                    session_db.resolve_resume_session_id(runtime_session_id) or runtime_session_id
                )
                conversation_history = session_db.get_messages_as_conversation(
                    runtime_session_id,
                    repair_alternation=True,
                    include_row_ids=True,
                )
                stale_lean_context_rows_dropped = drop_stale_lean_context_sidecars(
                    conversation_history
                )
            agent = AIAgent(
                api_key=runtime.get("api_key"),
                base_url=runtime.get("base_url"),
                provider=runtime.get("provider"),
                requested_provider=runtime.get("requested_provider"),
                api_mode=runtime.get("api_mode"),
                model=effective_model,
                max_iterations=proof.max_iterations,
                enabled_toolsets=_toolsets(request),
                quiet_mode=True,
                tool_progress_mode="off",
                platform="cli" if proof.coding_context_enabled else "gauntlet",
                session_id=runtime_session_id,
                session_db=session_db,
                credential_pool=runtime.get("credential_pool"),
                fallback_model=get_fallback_chain(config) or None,
                skip_context_files=not proof.context_files_enabled,
                skip_memory=not (proof.memory_enabled or proof.user_profile_enabled),
                skip_background_review=not proof.background_review_enabled,
                run_budget_seconds=run_budget,
            )
            agent.suppress_status_output = True
            agent.stream_delta_callback = None
            agent.tool_gen_callback = None
            result = agent.run_conversation(
                request.prompt,
                conversation_history=conversation_history,
                task_id=request.task_id,
            )

        if not isinstance(result, dict):
            raise RuntimeExecutionError(
                "INVALID_AGENT_RESULT",
                "upstream AIAgent returned a non-object result",
            )

        final_response = result.get("final_response")
        if not isinstance(final_response, str) or not final_response.strip():
            raise RuntimeExecutionError(
                "NO_FINAL_RESPONSE",
                "upstream AIAgent did not produce a final response",
            )

        usage_payload = _usage_payload(result)
        token_measurement = summarize_measurements(
            proof.runtime_home,
            task_id=request.task_id,
            request_id=request.request_id,
            expected_api_calls=result.get("api_calls"),
            provider_usage=usage_payload,
        )
        safe_payload = proof.to_payload()
        safe_payload.update(
            {
                "final_response": final_response,
                "model": str(result.get("model") or effective_model),
                "provider": str(
                    result.get("provider") or runtime.get("provider") or effective_provider or ""
                ),
                "session_id": str(
                    result.get("session_id") or getattr(agent, "session_id", "") or ""
                ),
                "session_binding_id": request.session_id,
                "session_resumed": conversation_history is not None,
                "stale_lean_context_rows_dropped": (stale_lean_context_rows_dropped),
                "completed": bool(result.get("completed", True)),
                "failed": bool(result.get("failed", False)),
                "partial": bool(result.get("partial", False)),
                "requested_cwd": request.cwd,
                "runtime_cwd": os.getcwd(),
                "usage": usage_payload,
                "token_measurement": token_measurement,
            }
        )

        if safe_payload["failed"] or safe_payload["partial"]:
            return _error_result(
                request,
                status=WorkerStatus.UNAVAILABLE,
                event="worker.turn_incomplete",
                code="AGENT_TURN_INCOMPLETE",
                message="upstream AIAgent returned a failed or partial turn",
                payload=safe_payload,
            )

        return RuntimeResult(
            request_id=request.request_id,
            task_id=request.task_id,
            status=WorkerStatus.OK,
            event="worker.turn_completed",
            payload=safe_payload,
        )
    except RuntimeExecutionError as exc:
        return _error_result(
            request,
            status=WorkerStatus.UNAVAILABLE,
            event="worker.turn_unavailable",
            code=exc.code,
            message=exc.message,
            payload=proof.to_payload(),
        )
    except ModuleNotFoundError as exc:
        missing = exc.name or "unknown"
        return _error_result(
            request,
            status=WorkerStatus.UNAVAILABLE,
            event="worker.turn_unavailable",
            code="RUNTIME_DEPENDENCY_MISSING",
            message=f"missing vendored runtime dependency: {missing}",
            payload=proof.to_payload(),
        )
    except KeyboardInterrupt:
        raise
    except BaseException as exc:
        return _error_result(
            request,
            status=WorkerStatus.UNAVAILABLE,
            event="worker.turn_unavailable",
            code="AGENT_RUNTIME_UNAVAILABLE",
            message=_safe_exception_message(exc),
            payload=proof.to_payload(),
        )
    finally:
        if auxiliary_scope is not None:
            auxiliary_scope.__exit__(None, None, None)
        _cleanup_agent(agent, session_db)


def handle_request(request: RuntimeRequest) -> RuntimeResult:
    """Handle one isolated import probe or one upstream AIAgent turn."""

    try:
        profile = prepare_runtime_profile(profile_name=request.runtime_profile)
        proof = bootstrap_vendor_runtime(profile)
    except RuntimeProfileError as exc:
        return _error_result(
            request,
            status=WorkerStatus.ERROR,
            event="worker.profile_failed",
            code=exc.code,
            message=exc.message,
        )
    except WorkerBootstrapError as exc:
        return _error_result(
            request,
            status=WorkerStatus.ERROR,
            event="worker.bootstrap_failed",
            code=exc.code,
            message=exc.message,
        )

    if request.operation is WorkerOperation.PROBE_IMPORTS:
        return RuntimeResult(
            request_id=request.request_id,
            task_id=request.task_id,
            status=WorkerStatus.OK,
            event="worker.imports_verified",
            payload=proof.to_payload(),
        )

    return _execute_agent_turn(request, proof)


def run_worker(stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
    """Process a JSONL request stream and emit one result per non-blank line."""

    exit_code = 0
    for line_number, line in enumerate(stdin, start=1):
        if not line.strip():
            continue
        try:
            request = decode_request(line)
            result = handle_request(request)
        except IPCContractError as exc:
            result = contract_error_result(exc)
        except Exception:
            traceback.print_exc(file=stderr)
            result = RuntimeResult(
                request_id="unknown",
                task_id="unknown",
                status=WorkerStatus.ERROR,
                event="worker.internal_error",
                error=WorkerError(
                    code="WORKER_INTERNAL_ERROR",
                    message=f"unexpected worker failure while processing line {line_number}",
                ),
            )

        write_result(stdout, result)
        if result.status is WorkerStatus.ERROR:
            exit_code = max(exit_code, 2)
        elif result.status is WorkerStatus.UNAVAILABLE:
            exit_code = max(exit_code, 3)
    return exit_code


def main() -> int:
    return run_worker(sys.stdin, sys.stdout, sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
