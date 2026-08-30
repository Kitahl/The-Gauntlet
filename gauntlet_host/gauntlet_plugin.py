"""Read-only Gauntlet status tools and observation-only runtime hooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ADAPTER_SCHEMA = "gauntlet.adapter.v1"
OBSERVATION_SCHEMA = "gauntlet.observation-store-result.v1"
TOOLSET = "gauntlet"
ADAPTER_TIMEOUT = 20.0
OBSERVATION_TIMEOUT = 10.0
MAX_ADAPTER_OUTPUT = 65_536

logger = logging.getLogger(__name__)
_pending: dict[tuple[str, str, str], tuple[str, float]] = {}
_pending_lock = threading.Lock()
_api_context: dict[str, dict[str, Any]] = {}
_llm_pending: dict[str, tuple[dict[str, Any], float]] = {}
_llm_lock = threading.Lock()


class BridgeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _safe(value: Any) -> str:
    text = " ".join(str(value).split())
    text = re.sub(
        r"(?i)(api[_-]?key|authorization|token|secret)\s*[:=]\s*\S+",
        r"\1=<redacted>",
        text,
    )
    return re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "<redacted-key>", text)[:1_000]


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise BridgeError("BRIDGE_ENVIRONMENT_MISSING", f"{name} is required")
    return value


def _error(action: str, exc: BridgeError) -> str:
    return json.dumps(
        {
            "schema": ADAPTER_SCHEMA,
            "action": action,
            "status": "ERROR",
            "error": {"code": exc.code, "message": _safe(exc.message)},
            "read_only": True,
            "mutation_performed": False,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _status_call(action: str, arguments: Any) -> str:
    try:
        command_arguments: list[str] = []
        if action == "obligation-get":
            if not isinstance(arguments, dict) or set(arguments) != {"obligation_id"}:
                raise BridgeError(
                    "TOOL_ARGUMENTS_REJECTED",
                    "gauntlet_obligation_get requires only obligation_id",
                )
            obligation_id = arguments.get("obligation_id")
            if (
                not isinstance(obligation_id, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}", obligation_id)
                or ".." in obligation_id
            ):
                raise BridgeError(
                    "OBLIGATION_ID_INVALID",
                    "obligation_id contains unsupported characters",
                )
            command_arguments = ["--obligation-id", obligation_id]
        elif arguments not in (None, {}):
            raise BridgeError(
                "TOOL_ARGUMENTS_REJECTED",
                "this Gauntlet status tool does not accept arguments",
            )

        task_id = _env("GAUNTLET_TASK_ID")
        root = Path(_env("GAUNTLET_REPO_ROOT")).resolve()
        adapter = Path(_env("GAUNTLET_MODULE_CLI")).resolve()
        expected = (root / "gauntlet_host" / "module_cli.py").resolve()
        if adapter != expected or not adapter.is_file():
            raise BridgeError("MODULE_ADAPTER_PATH_MISMATCH", "invalid module adapter")
        environment = dict(os.environ)
        environment.update(
            {
                "GAUNTLET_TASK_ID": task_id,
                "PYTHONPATH": str(root),
                "PYTHONUNBUFFERED": "1",
            }
        )
        for name in (
            "HERMES_YOLO_MODE",
            "HERMES_ACCEPT_HOOKS",
            "HERMES_INTERACTIVE",
        ):
            environment.pop(name, None)
        completed = subprocess.run(
            [
                sys.executable,
                str(adapter),
                "--root",
                str(root),
                action,
                *command_arguments,
            ],
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=ADAPTER_TIMEOUT,
            check=False,
        )
        if len(completed.stdout.encode("utf-8")) > MAX_ADAPTER_OUTPUT:
            raise BridgeError("MODULE_ADAPTER_OUTPUT_TOO_LARGE", "adapter output too large")
        records = [line for line in completed.stdout.splitlines() if line.strip()]
        if len(records) != 1:
            raise BridgeError("MODULE_ADAPTER_PROTOCOL_ERROR", "expected one JSON record")
        value = json.loads(records[0])
        if not isinstance(value, dict):
            raise BridgeError("MODULE_ADAPTER_PROTOCOL_ERROR", "result must be an object")
        if value.get("schema") != ADAPTER_SCHEMA:
            raise BridgeError("MODULE_ADAPTER_SCHEMA_MISMATCH", "invalid adapter schema")
        if value.get("action") != action or value.get("task_id") != task_id:
            raise BridgeError("MODULE_ADAPTER_CORRELATION_MISMATCH", "adapter mismatch")
        if value.get("read_only") is not True or value.get("mutation_performed") is not False:
            raise BridgeError("MODULE_ADAPTER_AUTHORITY_VIOLATION", "adapter was not read-only")
        expected_exit = 0 if value.get("status") == "OK" else 2
        if completed.returncode != expected_exit:
            raise BridgeError("MODULE_ADAPTER_EXIT_MISMATCH", "adapter exit mismatch")
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    except subprocess.TimeoutExpired:
        return _error(action, BridgeError("MODULE_ADAPTER_TIMEOUT", "adapter timed out"))
    except (OSError, json.JSONDecodeError) as exc:
        return _error(action, BridgeError("MODULE_ADAPTER_FAILURE", str(exc)))
    except BridgeError as exc:
        return _error(action, exc)
    except Exception as exc:
        return _error(action, BridgeError("MODULE_ADAPTER_UNEXPECTED_FAILURE", str(exc)))


def _task_status(arguments: dict[str, Any] | None = None, **_: Any) -> str:
    """Legacy internal alias; returns compact status and is not model-visible."""

    return _status_call("task-status-compact", arguments)


def _task_status_compact(arguments: dict[str, Any] | None = None, **_: Any) -> str:
    return _status_call("task-status-compact", arguments)


def _obligation_get(arguments: dict[str, Any] | None = None, **_: Any) -> str:
    return _status_call("obligation-get", arguments)


def _release_status(arguments: dict[str, Any] | None = None, **_: Any) -> str:
    return _status_call("release-status", arguments)


def _hash(value: Any) -> str:
    def fallback(item: Any) -> dict[str, str]:
        return {"type": type(item).__qualname__, "repr": _safe(repr(item))[:2_000]}

    try:
        data = json.dumps(
            value,
            default=fallback,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    except Exception:
        data = fallback(value)["repr"].encode(errors="replace")
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hook_inputs(
    positional: tuple[Any, ...], values: dict[str, Any]
) -> tuple[str, Any, Any, str, str]:
    name = values.get("tool_name") or values.get("function_name")
    arguments = values.get("args")
    if arguments is None:
        arguments = values.get("function_args", values.get("arguments"))
    result = values.get("result")
    if name is None and positional:
        name = positional[0]
    if arguments is None and len(positional) > 1:
        arguments = positional[1]
    if result is None and len(positional) > 2:
        result = positional[2]
    return (
        str(name or "unknown-tool"),
        arguments,
        result,
        str(values.get("session_id") or "unknown-session"),
        str(values.get("tool_call_id") or values.get("call_id") or "unknown-call"),
    )


def _key(name: str, session_id: str, call_id: str) -> tuple[str, str, str]:
    return session_id, call_id, name


def _pre(*positional: Any, **values: Any) -> None:
    name, _, _, session_id, call_id = _hook_inputs(positional, values)
    with _pending_lock:
        _pending[_key(name, session_id, call_id)] = (_now(), time.monotonic())


def _status(result: Any, values: dict[str, Any]) -> str:
    explicit = str(values.get("status") or "").upper()
    mapping = {
        "SUCCESS": "OK",
        "SUCCEEDED": "OK",
        "COMPLETED": "OK",
        "FAILED": "ERROR",
        "FAILURE": "ERROR",
        "TIMED_OUT": "TIMEOUT",
        "NOT_AVAILABLE": "UNAVAILABLE",
        "CANCELED": "CANCELLED",
    }
    explicit = mapping.get(explicit, explicit)
    if explicit in {"OK", "ERROR", "TIMEOUT", "UNAVAILABLE", "CANCELLED"}:
        return explicit
    if values.get("timed_out") is True:
        return "TIMEOUT"
    if values.get("cancelled") is True or values.get("canceled") is True:
        return "CANCELLED"
    if values.get("error") is not None or values.get("exception") is not None:
        return "ERROR"
    if isinstance(result, dict) and result.get("success") is False:
        return "ERROR"
    return "OK"


def _record(document: dict[str, Any]) -> None:
    try:
        root = Path(_env("GAUNTLET_REPO_ROOT")).resolve()
        bridge = Path(_env("GAUNTLET_OBSERVATION_BRIDGE")).resolve()
        expected = (root / "gauntlet_host" / "observation_bridge.py").resolve()
        if bridge != expected or not bridge.is_file():
            raise BridgeError("OBSERVATION_BRIDGE_PATH_MISMATCH", "invalid bridge")
        completed = subprocess.run(
            [sys.executable, str(bridge)],
            input=json.dumps(document, separators=(",", ":"), sort_keys=True),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            timeout=OBSERVATION_TIMEOUT,
            check=False,
        )
        records = [line for line in completed.stdout.splitlines() if line.strip()]
        if completed.returncode != 0 or len(records) != 1:
            raise BridgeError("OBSERVATION_BRIDGE_FAILURE", "bridge failed safely")
        if json.loads(records[0]).get("schema") != OBSERVATION_SCHEMA:
            raise BridgeError("OBSERVATION_SCHEMA_MISMATCH", "invalid bridge schema")
    except Exception as exc:
        logger.warning("Gauntlet observation hook failed safely: %s", _safe(exc))


def _post(*positional: Any, **values: Any) -> None:
    finished_at = _now()
    finished_clock = time.monotonic()
    name, arguments, result, session_id, call_id = _hook_inputs(positional, values)
    with _pending_lock:
        start = _pending.pop(_key(name, session_id, call_id), None)
    supplied = values.get("duration_ms")
    if isinstance(supplied, bool) or not isinstance(supplied, (int, float)):
        supplied = None
    if start is None:
        started_at = finished_at
        duration_ms = float(supplied or 0.0)
    else:
        started_at, started_clock = start
        duration_ms = (
            float(supplied)
            if supplied is not None
            else max(0.0, (finished_clock - started_clock) * 1_000)
        )
    try:
        task_id = _env("GAUNTLET_TASK_ID")
    except BridgeError:
        return
    _record(
        {
            "task_id": task_id,
            "runtime_session_id": session_id,
            "tool_call_id": call_id,
            "tool": name,
            "status": _status(result, values),
            "input_hash": _hash(arguments),
            "output_hash": _hash(result),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": max(0.0, duration_ms),
        }
    )


_SPARSE_CONTEXT_SCHEMA = "gauntlet.sparse-context-plan.v1"
_SPARSE_CONTEXT_ENGINE = "gauntlet-sparse"
_JIT_CONTEXT_MARKER = "[GAUNTLET JIT SELECTED CONTEXT]"
_JIT_CONTEXT_END_MARKER = "[/GAUNTLET JIT SELECTED CONTEXT]"
_WORD_PATTERN = re.compile(r"[A-Za-z0-9_:-]{2,}")
_ALLOWED_JIT_KINDS = {"skill", "memory", "profile"}


def _message_text(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""


def _lexical_tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in _WORD_PATTERN.finditer(text)}


def _assistant_tool_call_ids(message: Any) -> tuple[set[str], bool]:
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return set(), False
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or not calls:
        return set(), False
    ids = {
        str(call.get("id"))
        for call in calls
        if isinstance(call, dict) and isinstance(call.get("id"), str) and call.get("id")
    }
    return ids, True


def _tool_result_ids(messages: list[dict[str, Any]]) -> set[str]:
    return {
        str(message.get("tool_call_id"))
        for message in messages
        if isinstance(message, dict)
        and message.get("role") == "tool"
        and isinstance(message.get("tool_call_id"), str)
        and message.get("tool_call_id")
    }


def _closed_history_unit(messages: list[dict[str, Any]]) -> bool:
    call_ids: set[str] = set()
    has_calls = False
    for message in messages:
        ids, present = _assistant_tool_call_ids(message)
        call_ids.update(ids)
        has_calls = has_calls or present
    results = _tool_result_ids(messages)
    if not has_calls:
        return not results
    return bool(call_ids) and call_ids == results


def _history_units(messages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    units: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") == "user":
            if current:
                units.append(current)
            current = [message]
        elif current:
            current.append(message)
    if current:
        units.append(current)
    return [unit for unit in units if unit and unit[0].get("role") == "user"]


class _GauntletSparseEngineBase:
    """Request-only sparse selector with delegated pinned Hermes compaction."""

    threshold_percent = 0.75
    protect_first_n = 3
    protect_last_n = 20
    threshold_tokens = 0
    context_length = 0
    compression_count = 0
    last_prompt_tokens = 0
    last_completion_tokens = 0
    last_total_tokens = 0

    def __init__(self) -> None:
        self._delegate = None
        self._selection_plan: dict[str, Any] | None = None
        self.last_selection: dict[str, Any] = {
            "engine": _SPARSE_CONTEXT_ENGINE,
            "activated": False,
            "reason": "not_configured",
            "persisted_transcript_mutated": False,
        }

    def __setattr__(self, name: str, value: Any) -> None:
        delegate = self.__dict__.get("_delegate")
        if (
            delegate is not None
            and name not in {"_delegate", "_selection_plan", "last_selection"}
            and hasattr(delegate, name)
        ):
            setattr(delegate, name, value)
        object.__setattr__(self, name, value)

    @property
    def name(self) -> str:
        return _SPARSE_CONTEXT_ENGINE

    def __getattr__(self, name: str) -> Any:
        delegate = self.__dict__.get("_delegate")
        if delegate is not None:
            return getattr(delegate, name)
        raise AttributeError(name)

    def _sync_delegate_state(self) -> None:
        if self._delegate is None:
            return
        for name in (
            "threshold_percent",
            "protect_first_n",
            "protect_last_n",
            "threshold_tokens",
            "context_length",
            "compression_count",
            "last_prompt_tokens",
            "last_completion_tokens",
            "last_total_tokens",
        ):
            if hasattr(self._delegate, name):
                setattr(self, name, getattr(self._delegate, name))

    def update_model(
        self,
        model: str,
        context_length: int,
        base_url: str = "",
        api_key: str = "",
        provider: str = "",
        api_mode: str = "",
    ) -> None:
        if self._delegate is None:
            from agent.context_compressor import ContextCompressor

            self._delegate = ContextCompressor(
                model=model,
                threshold_percent=self.threshold_percent,
                protect_first_n=self.protect_first_n,
                protect_last_n=self.protect_last_n,
                summary_target_ratio=0.20,
                quiet_mode=True,
                base_url=base_url,
                api_key=api_key,
                config_context_length=context_length or None,
                provider=provider,
                api_mode=api_mode,
                model_thresholds=getattr(self, "model_thresholds", {}),
                tail_mode="lean",
            )
        else:
            self._delegate.update_model(
                model=model,
                context_length=context_length,
                base_url=base_url,
                api_key=api_key,
                provider=provider,
                api_mode=api_mode,
            )
        self._sync_delegate_state()

    def update_from_response(self, usage: dict[str, Any]) -> None:
        if self._delegate is not None:
            self._delegate.update_from_response(usage)
            self._sync_delegate_state()

    def should_compress(self, prompt_tokens: int | None = None) -> bool:
        return bool(self._delegate is not None and self._delegate.should_compress(prompt_tokens))

    def should_compress_info(self, prompt_tokens: int | None = None) -> tuple[bool, str | None]:
        if self._delegate is None:
            return False, None
        method = getattr(self._delegate, "should_compress_info", None)
        if callable(method):
            return method(prompt_tokens)
        return self._delegate.should_compress(prompt_tokens), None

    def compress(self, messages: list[dict[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
        if self._delegate is None:
            return messages
        result = self._delegate.compress(messages, **kwargs)
        self._sync_delegate_state()
        return result

    def prune_tool_results_only(
        self,
        messages: list[dict[str, Any]],
        current_tokens: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        if self._delegate is None:
            return messages, 0
        return self._delegate.prune_tool_results_only(messages, current_tokens)

    def should_compress_preflight(self, messages: list[dict[str, Any]]) -> bool:
        return bool(
            self._delegate is not None and self._delegate.should_compress_preflight(messages)
        )

    def should_defer_preflight_to_real_usage(self, rough_tokens: int) -> bool:
        return bool(
            self._delegate is not None
            and self._delegate.should_defer_preflight_to_real_usage(rough_tokens)
        )

    def has_content_to_compress(self, messages: list[dict[str, Any]]) -> bool:
        return bool(self._delegate is not None and self._delegate.has_content_to_compress(messages))

    def get_status(self) -> dict[str, Any]:
        if self._delegate is not None:
            return self._delegate.get_status()
        return {
            "last_prompt_tokens": 0,
            "threshold_tokens": self.threshold_tokens,
            "context_length": self.context_length,
            "usage_percent": 0,
            "compression_count": self.compression_count,
        }

    def bind_session_state(self, **kwargs: Any) -> None:
        if self._delegate is not None:
            method = getattr(self._delegate, "bind_session_state", None)
            if callable(method):
                method(**kwargs)

    def on_session_start(self, session_id: str, **kwargs: Any) -> None:
        if self._delegate is not None:
            self._delegate.on_session_start(session_id, **kwargs)

    def on_session_end(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        if self._delegate is not None:
            self._delegate.on_session_end(session_id, messages)

    def on_session_reset(self) -> None:
        if self._delegate is not None:
            self._delegate.on_session_reset()
            self._sync_delegate_state()
        self._selection_plan = None

    def on_turn_complete(
        self,
        messages: list[dict[str, Any]],
        usage: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if self._delegate is not None:
            method = getattr(self._delegate, "on_turn_complete", None)
            if callable(method):
                method(messages, usage=usage, **kwargs)

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return []

    def configure_gauntlet_context(self, plan: Any) -> None:
        if not isinstance(plan, dict) or plan.get("schema") != _SPARSE_CONTEXT_SCHEMA:
            raise ValueError("sparse context plan schema mismatch")
        supplied_hash = plan.get("content_hash")
        payload = dict(plan)
        payload.pop("content_hash", None)
        if (
            not isinstance(supplied_hash, str)
            or len(supplied_hash) != 64
            or hashlib.sha256(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            != supplied_hash
        ):
            raise ValueError("sparse context plan hash mismatch")
        if (
            plan.get("engine") != _SPARSE_CONTEXT_ENGINE
            or not isinstance(plan.get("task_binding_id"), str)
            or not plan["task_binding_id"]
            or plan.get("profile_name") != "gauntlet-lean.v1"
            or plan.get("persisted_transcript_mutation_allowed") is not False
            or plan.get("snippet_authority_allowed") is not False
        ):
            raise ValueError("sparse context plan isolation mismatch")
        for key in (
            "activation_history_chars",
            "recent_turns",
            "retrieval_top_k",
            "max_selected_messages",
        ):
            if isinstance(plan.get(key), bool) or not isinstance(plan.get(key), int):
                raise ValueError("sparse context plan integer policy invalid")
        snippets = plan.get("selected_snippets")
        if not isinstance(snippets, list) or len(snippets) > 8:
            raise ValueError("selected JIT context invalid")
        seen: set[str] = set()
        total_chars = 0
        for snippet in snippets:
            if not isinstance(snippet, dict):
                raise ValueError("selected JIT context invalid")
            snippet_id = snippet.get("snippet_id")
            content = snippet.get("content")
            if (
                not isinstance(snippet_id, str)
                or not snippet_id
                or snippet_id in seen
                or snippet.get("kind") not in _ALLOWED_JIT_KINDS
                or snippet.get("authority") != "CONTEXT_ONLY"
                or not isinstance(snippet.get("provenance"), str)
                or not snippet["provenance"]
                or not isinstance(content, str)
                or not content
                or len(content) > 4_000
                or hashlib.sha256(content.encode("utf-8")).hexdigest() != snippet.get("source_hash")
            ):
                raise ValueError("selected JIT context invalid")
            if _JIT_CONTEXT_MARKER in content or _JIT_CONTEXT_END_MARKER in content:
                raise ValueError("selected JIT context marker collision")
            seen.add(snippet_id)
            total_chars += len(content)
        if total_chars > 12_000:
            raise ValueError("selected JIT context too large")
        self._selection_plan = json.loads(json.dumps(plan))

    def _jit_message(self) -> dict[str, Any] | None:
        if self._selection_plan is None:
            return None
        snippets = self._selection_plan.get("selected_snippets", [])
        if not snippets:
            return None
        rendered = {
            "authority": "CONTEXT_ONLY",
            "profile": self._selection_plan["profile_name"],
            "snippets": [
                {
                    "snippet_id": item["snippet_id"],
                    "kind": item["kind"],
                    "provenance": item["provenance"],
                    "source_hash": item["source_hash"],
                    "content": item["content"],
                    "authority": "CONTEXT_ONLY",
                }
                for item in snippets
            ],
        }
        return {
            "role": "system",
            "content": (
                _JIT_CONTEXT_MARKER
                + "\nSelected snippets are non-authoritative context only.\n"
                + json.dumps(
                    rendered,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
                + _JIT_CONTEXT_END_MARKER
            ),
        }

    def select_context(
        self,
        request_messages: list[dict[str, Any]],
        *,
        conversation_messages: list[dict[str, Any]] | None = None,
        incoming_message: dict[str, Any] | None = None,
        budget_tokens: int = 0,
    ) -> list[dict[str, Any]] | None:
        if self._selection_plan is None or not request_messages:
            self.last_selection = {
                "engine": self.name,
                "activated": False,
                "reason": "not_configured",
                "persisted_transcript_mutated": False,
            }
            return None

        current_user_index = -1
        for index in range(len(request_messages) - 1, -1, -1):
            if request_messages[index].get("role") == "user":
                current_user_index = index
                break
        if current_user_index < 0:
            self.last_selection = {
                "engine": self.name,
                "activated": False,
                "reason": "no_current_user_boundary",
                "persisted_transcript_mutated": False,
            }
            return None

        prefix_end = 0
        while prefix_end < len(request_messages) and request_messages[prefix_end].get("role") in {
            "system",
            "developer",
        }:
            prefix_end += 1
        prefix = request_messages[:prefix_end]
        historical = request_messages[prefix_end:current_user_index]
        active_suffix = request_messages[current_user_index:]
        history_chars = sum(len(_message_text(message)) for message in historical)
        jit_message = self._jit_message()
        if history_chars < self._selection_plan["activation_history_chars"] and jit_message is None:
            self.last_selection = {
                "engine": self.name,
                "activated": False,
                "reason": "below_activation_threshold",
                "input_messages": len(request_messages),
                "selected_messages": len(request_messages),
                "history_chars": history_chars,
                "jit_snippets": 0,
                "persisted_transcript_mutated": False,
                "tool_closure_preserved": True,
            }
            return None

        units = _history_units(historical)
        closed = [(index, unit) for index, unit in enumerate(units) if _closed_history_unit(unit)]
        recent_count = self._selection_plan["recent_turns"]
        recent = closed[-recent_count:] if recent_count else []
        recent_indexes = {index for index, _ in recent}
        query_text = _message_text(active_suffix[0])
        query_tokens = _lexical_tokens(query_text)
        scored: list[tuple[int, int, list[dict[str, Any]]]] = []
        for index, unit in closed:
            if index in recent_indexes:
                continue
            overlap = len(
                query_tokens.intersection(
                    _lexical_tokens("\n".join(_message_text(message) for message in unit))
                )
            )
            if overlap:
                scored.append((overlap, index, unit))
        scored.sort(key=lambda item: (-item[0], -item[1]))
        retrieved = scored[: self._selection_plan["retrieval_top_k"]]
        selected_by_index = {index: unit for index, unit in recent}
        selected_by_index.update({index: unit for _, index, unit in retrieved})

        max_history_messages = self._selection_plan["max_selected_messages"]
        retrieval_indexes = {index for _, index, _ in retrieved}
        while (
            sum(len(unit) for unit in selected_by_index.values()) > max_history_messages
            and retrieval_indexes
        ):
            drop_index = min(retrieval_indexes)
            retrieval_indexes.remove(drop_index)
            selected_by_index.pop(drop_index, None)

        selected_history = [
            message for index in sorted(selected_by_index) for message in selected_by_index[index]
        ]
        selected = list(prefix)
        if jit_message is not None:
            selected.append(jit_message)
        selected.extend(selected_history)
        selected.extend(active_suffix)

        input_chars = sum(len(_message_text(message)) for message in request_messages)
        selected_chars = sum(len(_message_text(message)) for message in selected)
        if selected_chars >= input_chars and jit_message is None:
            self.last_selection = {
                "engine": self.name,
                "activated": False,
                "reason": "no_size_reduction",
                "input_messages": len(request_messages),
                "selected_messages": len(request_messages),
                "history_chars": history_chars,
                "jit_snippets": 0,
                "persisted_transcript_mutated": False,
                "tool_closure_preserved": True,
            }
            return None

        self.last_selection = {
            "engine": self.name,
            "activated": True,
            "reason": "long_history_or_jit_selection",
            "input_messages": len(request_messages),
            "selected_messages": len(selected),
            "input_chars": input_chars,
            "selected_chars": selected_chars,
            "history_chars": history_chars,
            "recent_units": len(recent),
            "retrieved_units": len(retrieval_indexes),
            "jit_snippets": len(self._selection_plan.get("selected_snippets", [])),
            "persisted_transcript_mutated": False,
            "tool_closure_preserved": True,
            "stable_system_prefix_messages": len(prefix),
            "active_suffix_messages": len(active_suffix),
            "top_k_session_retrieval": True,
        }
        return selected


def _build_sparse_context_engine() -> Any:
    from agent.context_engine import ContextEngine

    class GauntletSparseContextEngine(_GauntletSparseEngineBase, ContextEngine):
        pass

    return GauntletSparseContextEngine()


TOKEN_MEASUREMENT_SCHEMA = "gauntlet.token-measurement.v1"
TOKEN_STORE_RESULT_SCHEMA = "gauntlet.token-measurement-store-result.v1"
TOKEN_CANONICALIZATION = "gauntlet.logical-provider-payload.v1"
TOKEN_ESTIMATOR = "utf8-bytes-div-4-ceiling.v1"
_FOIL_MARKER = "[GAUNTLET FOIL ADVISORY ROUTE]"
_FOIL_END_MARKER = "[/GAUNTLET FOIL ADVISORY ROUTE]"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {"$type": "bytes", "byte_length": len(value)}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return {"$type": f"{type(value).__module__}.{type(value).__qualname__}"}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _measurement_key() -> tuple[bytes, str]:
    path = Path(_env("GAUNTLET_TOKEN_MEASUREMENT_KEY")).resolve()
    home = Path(_env("HERMES_HOME")).resolve()
    try:
        path.relative_to(home / "measurements" / "token-efficiency")
    except ValueError as exc:
        raise BridgeError(
            "TOKEN_MEASUREMENT_KEY_PATH_INVALID",
            "measurement key escaped runtime home",
        ) from exc
    try:
        key = path.read_bytes()
    except OSError as exc:
        raise BridgeError("TOKEN_MEASUREMENT_KEY_UNREADABLE", type(exc).__name__) from exc
    if len(key) < 32:
        raise BridgeError("TOKEN_MEASUREMENT_KEY_INVALID", "measurement key is too short")
    key_id = hashlib.sha256(key).hexdigest()[:16]
    expected = _env("GAUNTLET_TOKEN_MEASUREMENT_KEY_ID")
    if key_id != expected:
        raise BridgeError("TOKEN_MEASUREMENT_KEY_MISMATCH", "measurement key identity mismatch")
    return key, key_id


def _hmac_hex(key: bytes, data: bytes) -> str:
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def _component_bytes(value: Any) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    return _canonical_bytes(value)


def _component_record(key: bytes, values: list[Any]) -> dict[str, Any]:
    parts = [_component_bytes(value) for value in values]
    framed = b"".join(len(part).to_bytes(8, "big") + part for part in parts)
    byte_count = sum(len(part) for part in parts)
    char_count = sum(len(part.decode("utf-8", errors="replace")) for part in parts)
    return {
        "availability": "MEASURED",
        "items": len(parts),
        "chars": char_count,
        "utf8_bytes": byte_count,
        "local_estimated_tokens": math.ceil(byte_count / 4),
        "hmac_sha256": _hmac_hex(key, framed),
    }


def _unavailable_component(reason: str) -> dict[str, Any]:
    return {
        "availability": "UNAVAILABLE",
        "reason": reason,
        "items": None,
        "chars": None,
        "utf8_bytes": None,
        "local_estimated_tokens": None,
        "hmac_sha256": None,
    }


def _content_parts(content: Any) -> tuple[list[Any], list[Any]]:
    if isinstance(content, list):
        text_parts: list[Any] = []
        image_parts: list[Any] = []
        for item in content:
            if isinstance(item, dict) and str(item.get("type") or "").lower() in {
                "image",
                "image_url",
                "input_image",
            }:
                image_parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                text_parts.append(item.get("text"))
            else:
                text_parts.append(item)
        return text_parts, image_parts
    return [content] if content is not None else [], []


def _split_foil(text: str) -> tuple[str | None, str]:
    start = text.find(_FOIL_MARKER)
    if start < 0:
        return None, text
    end = text.find(_FOIL_END_MARKER, start)
    if end < 0:
        return None, text
    end += len(_FOIL_END_MARKER)
    foil = text[start:end]
    user = (text[:start] + text[end:]).strip()
    return foil, user


def _is_status_result(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and parsed.get("schema") == ADAPTER_SCHEMA


def _request_measurement(request: Any, key: bytes) -> dict[str, Any]:
    payload = request if isinstance(request, dict) else {}
    excluded_private_keys = sorted(
        str(name) for name in payload if isinstance(name, str) and name.startswith("_")
    )
    visible = {
        str(name): value
        for name, value in payload.items()
        if not (isinstance(name, str) and name.startswith("_"))
    }
    buckets: dict[str, list[Any]] = {
        "system_combined": [],
        "tool_schemas": [],
        "foil_route": [],
        "task_status": [],
        "conversation_user": [],
        "conversation_assistant": [],
        "conversation_tool": [],
        "images": [],
        "request_envelope": [],
    }

    for name in ("system", "instructions"):
        if name in visible:
            buckets["system_combined"].append(visible[name])
    if "tools" in visible:
        buckets["tool_schemas"].append(visible["tools"])

    messages = visible.get("messages")
    if not isinstance(messages, list):
        messages = visible.get("input")
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict):
                buckets["request_envelope"].append(message)
                continue
            role = str(message.get("role") or "").lower()
            text_parts, image_parts = _content_parts(message.get("content"))
            buckets["images"].extend(image_parts)
            for part in text_parts:
                if role in {"system", "developer"}:
                    buckets["system_combined"].append(part)
                elif role == "user":
                    if isinstance(part, str):
                        foil, user = _split_foil(part)
                        if foil is not None:
                            buckets["foil_route"].append(foil)
                            if user:
                                buckets["conversation_user"].append(user)
                        else:
                            buckets["conversation_user"].append(part)
                    else:
                        buckets["conversation_user"].append(part)
                elif role == "assistant":
                    buckets["conversation_assistant"].append(part)
                elif role == "tool" and _is_status_result(part):
                    buckets["task_status"].append(part)
                elif role == "tool":
                    buckets["conversation_tool"].append(part)
                else:
                    buckets["request_envelope"].append(part)

    envelope = {
        name: value
        for name, value in visible.items()
        if name not in {"messages", "input", "tools", "system", "instructions"}
    }
    if envelope:
        buckets["request_envelope"].append(envelope)

    components = {name: _component_record(key, values) for name, values in buckets.items()}
    unavailable_reason = "provenance is merged before the final provider boundary"
    for name in (
        "system_stable",
        "system_context",
        "system_volatile",
        "skills",
        "memory",
        "profile",
        "context_files",
    ):
        components[name] = _unavailable_component(unavailable_reason)

    canonical = _canonical_bytes(visible)
    attributed = sum(
        int(item["utf8_bytes"] or 0)
        for item in components.values()
        if item["availability"] == "MEASURED"
    )
    structural = len(canonical) - attributed
    return {
        "canonicalization": TOKEN_CANONICALIZATION,
        "hash_policy": "HMAC-SHA256 with a private runtime-local persistent key",
        "canonical_chars": len(canonical.decode("utf-8", errors="replace")),
        "canonical_utf8_bytes": len(canonical),
        "wire_utf8_bytes": None,
        "local_estimated_tokens": math.ceil(len(canonical) / 4),
        "local_token_estimator": TOKEN_ESTIMATOR,
        "payload_hmac_sha256": _hmac_hex(key, canonical),
        "components": components,
        "reconciliation": {
            "attributed_component_utf8_bytes": attributed,
            "structural_unattributed_utf8_bytes": structural,
            "non_overlapping": structural >= 0,
            "reconciles_to_canonical_payload": structural >= 0,
        },
        "excluded_private_runtime_keys": excluded_private_keys,
        "provider_wire_measurement_available": False,
    }


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    for method_name in ("model_dump", "dict"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                result = method()
            except Exception:
                continue
            if isinstance(result, dict):
                return result
    return {
        name: getattr(value, name)
        for name in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "input_tokens",
            "output_tokens",
            "input_tokens_details",
            "output_tokens_details",
            "prompt_tokens_details",
        )
        if hasattr(value, name)
    }


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _usage_record(value: Any) -> dict[str, Any]:
    usage = _mapping(value)
    prompt_details = _mapping(usage.get("prompt_tokens_details"))
    input_details = _mapping(usage.get("input_tokens_details"))
    output_details = _mapping(usage.get("output_tokens_details"))
    input_tokens = _number(usage.get("input_tokens"))
    if input_tokens is None:
        input_tokens = _number(usage.get("prompt_tokens"))
    output_tokens = _number(usage.get("output_tokens"))
    if output_tokens is None:
        output_tokens = _number(usage.get("completion_tokens"))
    cache_read = _number(usage.get("cache_read_tokens"))
    if cache_read is None:
        cache_read = _number(input_details.get("cached_tokens"))
    if cache_read is None:
        cache_read = _number(prompt_details.get("cached_tokens"))
    cache_write = _number(usage.get("cache_write_tokens"))
    if cache_write is None:
        cache_write = _number(input_details.get("cache_write_tokens"))
    reasoning = _number(usage.get("reasoning_tokens"))
    if reasoning is None:
        reasoning = _number(output_details.get("reasoning_tokens"))
    return {
        "source": "provider_reported",
        "input_tokens": input_tokens,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
        "billable_input_tokens": (
            input_tokens - cache_read
            if isinstance(input_tokens, (int, float))
            and isinstance(cache_read, (int, float))
            and input_tokens >= cache_read
            else None
        ),
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning,
        "total_tokens": _number(usage.get("total_tokens")),
    }


def _endpoint_identity(base_url: Any, key: bytes) -> dict[str, Any]:
    try:
        parsed = urlsplit(str(base_url or ""))
        host = (parsed.hostname or "").lower().encode("utf-8")
        return {
            "scheme": parsed.scheme.lower() or None,
            "host_hmac_sha256": _hmac_hex(key, host) if host else None,
            "port": parsed.port,
            "path": parsed.path.rstrip("/") or "/",
            "query_persisted": False,
            "userinfo_persisted": False,
        }
    except Exception:
        return {
            "scheme": None,
            "host_hmac_sha256": None,
            "port": None,
            "path": None,
            "query_persisted": False,
            "userinfo_persisted": False,
        }


def _pre_api_request(*_: Any, **values: Any) -> None:
    api_request_id = str(values.get("api_request_id") or "")
    if not api_request_id:
        return
    with _llm_lock:
        _api_context[api_request_id] = {
            "retry_count": _number(values.get("retry_count")),
            "runtime_approx_input_tokens": _number(values.get("approx_input_tokens")),
            "runtime_request_char_count": _number(values.get("request_char_count")),
            "runtime_message_count": _number(values.get("message_count")),
            "runtime_tool_count": _number(values.get("tool_count")),
        }


def _measurement_document(request: Any, values: dict[str, Any]) -> dict[str, Any]:
    key, key_id = _measurement_key()
    api_request_id = str(values.get("api_request_id") or f"dispatch-{time.time_ns()}")
    with _llm_lock:
        preflight = _api_context.pop(api_request_id, {})
    requested_provider = os.environ.get("GAUNTLET_REQUESTED_PROVIDER", "").strip() or None
    provider = str(values.get("provider") or "") or None
    return {
        "schema": TOKEN_MEASUREMENT_SCHEMA,
        "request_kind": "conversation",
        "auxiliary_task": None,
        "auxiliary_stream": False,
        "task_id": _env("GAUNTLET_TASK_ID"),
        "host_request_id": _env("GAUNTLET_HOST_REQUEST_ID"),
        "workload_id": (os.environ.get("GAUNTLET_TOKEN_WORKLOAD_ID", "").strip() or None),
        "runtime_session_id": str(values.get("session_id") or "unknown-session"),
        "turn_id": str(values.get("turn_id") or "unknown-turn"),
        "dispatch_id": api_request_id,
        "attempt": _number(values.get("api_call_count")),
        "retry_count": preflight.get("retry_count"),
        "fallback_index": None,
        "fallback_detected": bool(
            requested_provider and provider and requested_provider != provider
        ),
        "requested_provider": requested_provider,
        "provider": provider,
        "model": str(values.get("model") or "") or None,
        "api_mode": str(values.get("api_mode") or "") or None,
        "endpoint_identity": _endpoint_identity(values.get("base_url"), key),
        "source": {
            "running_commit": os.environ.get("GAUNTLET_SOURCE_COMMIT", "").strip() or None,
            "running_tree": os.environ.get("GAUNTLET_SOURCE_TREE", "").strip() or None,
            "frozen_fast_p8_handoff_commit": "6a50046b23e4f4cef6667b80d2e700e7167d14ac",
            "frozen_fast_p8_handoff_tree": "bb490654eba9eb5bef24102ba5f94321862cfdd0",
            "pinned_hermes_commit": "5fc308a70719a83cccdbba4c0e39c23f5a8239d5",
        },
        "request_composition": _request_measurement(request, key),
        "runtime_estimates": preflight,
        "digest_key_id": key_id,
        "provider_usage": _usage_record({}),
        "tool_call_count": None,
        "outcome": {
            "status": "PENDING",
            "error_type": None,
            "timeout": False,
            "cancelled": False,
        },
        "timing": {
            "started_at": _now(),
            "finished_at": None,
            "latency_ms": None,
            "time_to_first_token_ms": None,
        },
        "cost": {
            "amount": None,
            "currency": None,
            "pricing_source": None,
            "pricing_version": None,
            "pricing_timestamp": None,
            "status": "UNPRICED",
        },
        "privacy": {
            "raw_prompt_persisted": False,
            "raw_tool_output_persisted": False,
            "raw_response_persisted": False,
            "plain_content_hashes_persisted": False,
        },
    }


def _record_token_measurement(document: dict[str, Any]) -> bool:
    try:
        root = Path(_env("GAUNTLET_REPO_ROOT")).resolve()
        bridge = Path(_env("GAUNTLET_TOKEN_MEASUREMENT_BRIDGE")).resolve()
        expected = (root / "gauntlet_host" / "token_measurement_bridge.py").resolve()
        if bridge != expected or not bridge.is_file():
            raise BridgeError("TOKEN_MEASUREMENT_BRIDGE_PATH_MISMATCH", "invalid bridge")
        completed = subprocess.run(
            [sys.executable, str(bridge)],
            input=json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            timeout=OBSERVATION_TIMEOUT,
            check=False,
        )
        records = [line for line in completed.stdout.splitlines() if line.strip()]
        if completed.returncode != 0 or len(records) != 1:
            raise BridgeError("TOKEN_MEASUREMENT_BRIDGE_FAILURE", "bridge failed safely")
        value = json.loads(records[0])
        if value.get("schema") != TOKEN_STORE_RESULT_SCHEMA:
            raise BridgeError("TOKEN_MEASUREMENT_SCHEMA_MISMATCH", "invalid bridge schema")
        return value.get("status") in {"RECORDED", "EXISTS"}
    except Exception as exc:
        logger.warning("Gauntlet token measurement failed safely: %s", _safe(exc))
        return False


def _finish_measurement(
    document: dict[str, Any],
    *,
    status: str,
    usage: Any = None,
    tool_call_count: Any = None,
    error_type: str | None = None,
    latency_seconds: Any = None,
) -> None:
    document["provider_usage"] = _usage_record(usage)
    document["tool_call_count"] = _number(tool_call_count)
    document["outcome"] = {
        "status": status,
        "error_type": error_type,
        "timeout": error_type == "TimeoutError",
        "cancelled": error_type in {"CancelledError", "KeyboardInterrupt"},
    }
    finished = _now()
    started_clock = document.pop("_started_clock", None)
    supplied = _number(latency_seconds)
    if supplied is not None:
        latency_ms = max(0.0, float(supplied) * 1_000)
    elif isinstance(started_clock, (int, float)):
        latency_ms = max(0.0, (time.monotonic() - started_clock) * 1_000)
    else:
        latency_ms = None
    document["timing"]["finished_at"] = finished
    document["timing"]["latency_ms"] = round(latency_ms, 3) if latency_ms is not None else None
    _record_token_measurement(document)


def _llm_execution(request: Any, next_call: Any, **values: Any) -> Any:
    try:
        document = _measurement_document(request, values)
    except Exception as exc:
        logger.warning("Gauntlet token measurement setup failed safely: %s", _safe(exc))
        return next_call(request)
    document["_started_clock"] = time.monotonic()
    dispatch_id = document["dispatch_id"]
    try:
        response = next_call(request)
    except BaseException as exc:
        _finish_measurement(
            document,
            status="ERROR",
            error_type=type(exc).__name__,
        )
        raise
    with _llm_lock:
        _llm_pending[dispatch_id] = (document, time.monotonic())
    return response


def _post_api_request(*_: Any, **values: Any) -> None:
    dispatch_id = str(values.get("api_request_id") or "")
    with _llm_lock:
        pending = _llm_pending.pop(dispatch_id, None)
    if pending is None:
        return
    document, _ = pending
    _finish_measurement(
        document,
        status="OK",
        usage=values.get("usage"),
        tool_call_count=values.get("assistant_tool_call_count"),
        latency_seconds=values.get("api_duration"),
    )


_TASK_COMPACT_SCHEMA = {
    "description": (
        "Refresh compact canonical status for the exact host-bound task. Read-only; "
        "returns IDs, kinds, required modules, verdicts, reason codes, and hashes."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}
_OBLIGATION_SCHEMA = {
    "description": (
        "Read exact canonical detail for one obligation ID, including its claim and "
        "current release row. Read-only and bounded to one obligation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "obligation_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 256,
            }
        },
        "required": ["obligation_id"],
        "additionalProperties": False,
    },
}
_RELEASE_SCHEMA = {
    "description": (
        "Refresh Soul release-gate status for the exact host-bound task. This reports "
        "eligibility only and performs no mutation."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}


def register(ctx: Any) -> None:
    ctx.register_context_engine(_build_sparse_context_engine())
    ctx.register_tool(
        name="gauntlet_task_status_compact",
        toolset=TOOLSET,
        schema=_TASK_COMPACT_SCHEMA,
        handler=_task_status_compact,
        description=_TASK_COMPACT_SCHEMA["description"],
        emoji="",
    )
    ctx.register_tool(
        name="gauntlet_obligation_get",
        toolset=TOOLSET,
        schema=_OBLIGATION_SCHEMA,
        handler=_obligation_get,
        description=_OBLIGATION_SCHEMA["description"],
        emoji="",
    )
    ctx.register_tool(
        name="gauntlet_release_status",
        toolset=TOOLSET,
        schema=_RELEASE_SCHEMA,
        handler=_release_status,
        description=_RELEASE_SCHEMA["description"],
        emoji="",
    )
    ctx.register_hook("pre_tool_call", _pre)
    ctx.register_hook("post_tool_call", _post)
    ctx.register_hook("pre_api_request", _pre_api_request)
    ctx.register_hook("post_api_request", _post_api_request)
    ctx.register_middleware("llm_execution", _llm_execution)
