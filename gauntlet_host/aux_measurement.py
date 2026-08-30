"""Measurement-only wrappers for pinned Hermes auxiliary provider calls."""

from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from gauntlet_host import gauntlet_plugin as measurement


def _base_url(client: Any) -> str:
    return str(getattr(client, "base_url", "") or "")


def _context(auxiliary_client: Any) -> dict[str, Any]:
    relay_context = getattr(auxiliary_client, "_RELAY_AUX_CALL_CONTEXT", None)
    getter = getattr(relay_context, "get", None)
    if not callable(getter):
        return {}
    value = getter()
    return value if isinstance(value, dict) else {}


def _document(
    auxiliary_client: Any,
    client: Any,
    request: dict[str, Any],
    *,
    provider: str | None,
    api_mode: str | None,
    stream: bool,
) -> dict[str, Any]:
    context = _context(auxiliary_client)
    attempt = context.get("attempt_count")
    values = {
        "api_request_id": f"aux-{uuid.uuid4().hex}",
        "session_id": os.environ.get("HERMES_SESSION_ID", "") or "unknown-session",
        "turn_id": str(context.get("request_id") or "auxiliary"),
        "api_call_count": attempt + 1 if isinstance(attempt, int) else None,
        "provider": provider or context.get("provider"),
        "model": request.get("model") or context.get("model"),
        "api_mode": api_mode or context.get("api_mode") or "chat_completions",
        "base_url": _base_url(client),
    }
    document = measurement._measurement_document(request, values)
    document["request_kind"] = "auxiliary"
    document["auxiliary_task"] = str(context.get("task") or "unspecified")
    document["retry_count"] = attempt if isinstance(attempt, int) else None
    document["auxiliary_stream"] = stream
    document["_started_clock"] = time.monotonic()
    return document


def _finish(document: dict[str, Any], response: Any) -> None:
    measurement._finish_measurement(
        document,
        status="OK",
        usage=getattr(response, "usage", None),
        tool_call_count=None,
    )


@contextmanager
def auxiliary_measurement_scope() -> Iterator[None]:
    """Wrap all pinned retry-aware auxiliary relay boundaries."""

    from agent import auxiliary_client

    original_sync = auxiliary_client._relay_sync_completion
    original_async = auxiliary_client._relay_async_completion
    original_stream = auxiliary_client._relay_sync_stream

    def measured_sync(
        client: Any,
        kwargs: dict[str, Any],
        *,
        provider: str | None = None,
        api_mode: str | None = None,
        create: Callable[[dict[str, Any]], Any] | None = None,
    ) -> Any:
        try:
            document = _document(
                auxiliary_client,
                client,
                kwargs,
                provider=provider,
                api_mode=api_mode,
                stream=False,
            )
        except Exception:
            return original_sync(
                client, kwargs, provider=provider, api_mode=api_mode, create=create
            )
        try:
            response = original_sync(
                client, kwargs, provider=provider, api_mode=api_mode, create=create
            )
        except BaseException as exc:
            measurement._finish_measurement(document, status="ERROR", error_type=type(exc).__name__)
            raise
        _finish(document, response)
        return response

    async def measured_async(
        client: Any,
        kwargs: dict[str, Any],
        *,
        provider: str | None = None,
        api_mode: str | None = None,
        create: Callable[[dict[str, Any]], Any] | None = None,
    ) -> Any:
        try:
            document = _document(
                auxiliary_client,
                client,
                kwargs,
                provider=provider,
                api_mode=api_mode,
                stream=False,
            )
        except Exception:
            return await original_async(
                client, kwargs, provider=provider, api_mode=api_mode, create=create
            )
        try:
            response = await original_async(
                client, kwargs, provider=provider, api_mode=api_mode, create=create
            )
        except BaseException as exc:
            measurement._finish_measurement(document, status="ERROR", error_type=type(exc).__name__)
            raise
        _finish(document, response)
        return response

    def measured_stream(
        client: Any,
        kwargs: dict[str, Any],
        *,
        provider: str | None = None,
        api_mode: str | None = None,
    ) -> Any:
        try:
            document = _document(
                auxiliary_client,
                client,
                kwargs,
                provider=provider,
                api_mode=api_mode,
                stream=True,
            )
        except Exception:
            return original_stream(client, kwargs, provider=provider, api_mode=api_mode)
        try:
            response = original_stream(client, kwargs, provider=provider, api_mode=api_mode)
        except BaseException as exc:
            measurement._finish_measurement(document, status="ERROR", error_type=type(exc).__name__)
            raise
        _finish(document, response)
        return response

    auxiliary_client._relay_sync_completion = measured_sync
    auxiliary_client._relay_async_completion = measured_async
    auxiliary_client._relay_sync_stream = measured_stream
    try:
        yield
    finally:
        if auxiliary_client._relay_sync_completion is measured_sync:
            auxiliary_client._relay_sync_completion = original_sync
        if auxiliary_client._relay_async_completion is measured_async:
            auxiliary_client._relay_async_completion = original_async
        if auxiliary_client._relay_sync_stream is measured_stream:
            auxiliary_client._relay_sync_stream = original_stream
