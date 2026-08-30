"""Worker-side live capability snapshot and advisory FOIL route bridge."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from gauntlet_host.constants import (
    DEFAULT_ADAPTER_TIMEOUT_SECONDS,
    FOIL_ROUTE_PROTOCOL_VERSION,
    MAX_FOIL_ROUTE_OUTPUT_BYTES,
    MAX_FOIL_ROUTE_PROMPT_CHARS,
    REPO_ROOT,
)

_ROUTE_MARKER = "[GAUNTLET FOIL ADVISORY ROUTE]"
_ROUTE_END_MARKER = "[/GAUNTLET FOIL ADVISORY ROUTE]"
_FORBIDDEN_ROUTE_FIELDS = {
    "cleared",
    "evidence_class",
    "receipt",
    "receipts",
    "release",
    "released",
    "verdict",
}


class FoilRouteBridgeError(RuntimeError):
    """Typed operational failure while obtaining a proposal-only FOIL route."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tool_records(definitions: Any) -> list[dict[str, Any]]:
    if not isinstance(definitions, (list, tuple)):
        return []
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in definitions:
        if not isinstance(item, dict):
            continue
        function = item.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if not isinstance(name, str) or not name or name in seen:
            continue
        if len(name) > 256:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "schema_hash": _canonical_hash(
                    {
                        "parameters": function.get("parameters"),
                        "strict": function.get("strict"),
                    }
                ),
            }
        )
    return sorted(records, key=lambda item: item["name"])


def _matches(name: str, fragments: Iterable[str]) -> bool:
    return any(fragment in name for fragment in fragments)


def _tool_capabilities(name: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower())
    result: set[str] = set()

    if "deep_research" in normalized:
        result.add("DEEP_RESEARCH")
        result.add("WEB_SEARCH")

    if _matches(
        normalized,
        (
            "arxiv",
            "consensus",
            "crossref",
            "openalex",
            "pubmed",
            "scholar",
            "scispace",
            "zotero",
        ),
    ):
        result.add("SCHOLARLY_SEARCH")
    elif _matches(
        normalized,
        (
            "browser_",
            "web_extract",
            "web_search",
        ),
    ):
        result.add("WEB_SEARCH")

    if _matches(
        normalized,
        (
            "file_read",
            "file_search",
            "files_find",
            "files_read",
            "files_search",
            "read_file",
            "search_files",
        ),
    ):
        result.add("FILES_LIBRARY")

    if _matches(
        normalized,
        (
            "git_",
            "github",
            "repository",
            "sourcegraph",
        ),
    ):
        result.add("REPOSITORY")

    if _matches(
        normalized,
        (
            "coq",
            "formal_proof",
            "isabelle",
            "lean",
            "smt",
            "z3",
        ),
    ):
        result.add("FORMAL_PROOF")
    elif _matches(
        normalized,
        (
            "bash",
            "code_execution",
            "execute_code",
            "python",
            "shell",
            "terminal",
        ),
    ):
        result.add("CODE_EXECUTION")

    if _matches(
        normalized,
        (
            "calculator",
            "symbolic",
            "wolfram",
        ),
    ):
        result.add("SYMBOLIC_COMPUTATION")

    if _matches(
        normalized,
        (
            "database",
            "postgres",
            "sql",
            "supabase",
        ),
    ):
        result.add("DATABASE")

    if _matches(
        normalized,
        (
            "image_analyze",
            "screenshot",
            "vision",
        ),
    ):
        result.add("VISION")
    return result


def capability_snapshot(tool_definitions: Any) -> dict[str, Any]:
    """Map runtime tool schemas to the frozen semantic FOIL capability names."""

    records = _tool_records(tool_definitions)
    capabilities = {"TEXT_GENERATION", "REASONING"}
    for record in records:
        capabilities.update(_tool_capabilities(record["name"]))
    return {
        "available_capabilities": sorted(capabilities),
        "tool_count": len(records),
        "tool_manifest_hash": _canonical_hash(records),
    }


def _adapter_environment(task_id: str, repository_root: Path) -> dict[str, str]:
    environment = dict(os.environ)
    environment["GAUNTLET_TASK_ID"] = task_id
    environment["PYTHONPATH"] = str(repository_root)
    environment["PYTHONUNBUFFERED"] = "1"
    for bypass in (
        "HERMES_YOLO_MODE",
        "HERMES_ACCEPT_HOOKS",
        "HERMES_INTERACTIVE",
    ):
        environment.pop(bypass, None)
    return environment


def _forbidden_fields(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(_FORBIDDEN_ROUTE_FIELDS.intersection(value))
        for item in value.values():
            found.update(_forbidden_fields(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_forbidden_fields(item))
    return found


def _validate_content_hash(route: dict[str, Any]) -> None:
    supplied = route.get("content_hash")
    if not isinstance(supplied, str) or not re.fullmatch(r"[0-9a-f]{64}", supplied):
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_CONTENT_HASH_INVALID",
            "FOIL route omitted a valid content hash",
        )
    payload = dict(route)
    payload.pop("content_hash", None)
    if _canonical_hash(payload) != supplied:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_CONTENT_HASH_MISMATCH",
            "FOIL route content hash did not match the returned route",
        )


def _parse_route(
    task_id: str,
    stdout: str,
    returncode: int,
) -> dict[str, Any]:
    if len(stdout.encode("utf-8")) > MAX_FOIL_ROUTE_OUTPUT_BYTES:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_OUTPUT_TOO_LARGE",
            "FOIL route adapter exceeded the bounded output limit",
        )
    records = [line for line in stdout.splitlines() if line.strip()]
    if len(records) != 1:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_PROTOCOL_ERROR",
            "FOIL route adapter must return exactly one JSON record",
        )
    try:
        route = json.loads(records[0])
    except json.JSONDecodeError as exc:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_PROTOCOL_ERROR",
            "FOIL route adapter returned invalid JSON",
        ) from exc
    if not isinstance(route, dict):
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_PROTOCOL_ERROR",
            "FOIL route adapter result must be a JSON object",
        )
    if route.get("schema") != FOIL_ROUTE_PROTOCOL_VERSION:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_SCHEMA_MISMATCH",
            f"FOIL route schema must be {FOIL_ROUTE_PROTOCOL_VERSION}",
        )
    if route.get("action") != "foil-route" or route.get("task_id") != task_id:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_CORRELATION_MISMATCH",
            "FOIL route did not match the host-bound task",
        )
    if route.get("read_only") is not True:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_AUTHORITY_VIOLATION",
            "FOIL route did not attest to read-only operation",
        )
    if route.get("mutation_performed") is not False:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_AUTHORITY_VIOLATION",
            "FOIL route reported a canonical mutation",
        )
    if route.get("mode") != "SHADOW":
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_MODE_INVALID",
            "FAST-P7 accepts only SHADOW FOIL routes",
        )
    if route.get("authority_ceiling") != "ADAPTATION_ONLY":
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_AUTHORITY_VIOLATION",
            "FOIL route exceeded the ADAPTATION_ONLY ceiling",
        )
    for name in (
        "execution_authorized",
        "toolset_narrowing_applied",
        "profile_used",
        "private_profile_data_transmitted",
    ):
        if route.get(name) is not False:
            raise FoilRouteBridgeError(
                "FOIL_ROUTE_AUTHORITY_VIOLATION",
                f"FOIL route field {name} must be false",
            )
    authority = route.get("authority")
    if not isinstance(authority, dict) or not authority:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_AUTHORITY_INVALID",
            "FOIL route omitted its authority projection",
        )
    if any(value is not False for value in authority.values()):
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_AUTHORITY_VIOLATION",
            "FOIL route attempted to claim canonical authority",
        )
    forbidden = _forbidden_fields(route)
    if forbidden:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_FORBIDDEN_FIELDS",
            "FOIL route contains authority-bearing fields: " + ", ".join(sorted(forbidden)),
        )
    _validate_content_hash(route)

    expected_exit = 0 if route.get("status") == "OK" else 2
    if returncode != expected_exit:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_EXIT_MISMATCH",
            "FOIL route adapter status and exit code did not agree",
        )
    if route.get("status") != "OK":
        error = route.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or "FOIL_ROUTE_UNAVAILABLE")
            message = str(error.get("message") or "FOIL route unavailable")
        else:
            code = "FOIL_ROUTE_UNAVAILABLE"
            message = "FOIL route unavailable"
        raise FoilRouteBridgeError(code, message)
    return route


def validate_advisory_route(
    task_id: str,
    route: dict[str, Any],
) -> dict[str, Any]:
    """Validate an already-decoded successful route from a parent prefetch."""

    return _parse_route(
        task_id,
        json.dumps(route, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        0,
    )


def build_advisory_route(
    *,
    task_id: str,
    tool_definitions: Any,
) -> dict[str, Any]:
    """Request one task-bound, profile-free, proposal-only FOIL route."""

    repository_root = Path(os.environ.get("GAUNTLET_REPO_ROOT", str(REPO_ROOT))).resolve()
    expected_module_cli = (repository_root / "gauntlet_host" / "module_cli.py").resolve()
    module_cli = Path(os.environ.get("GAUNTLET_MODULE_CLI", str(expected_module_cli))).resolve()
    if module_cli != expected_module_cli or not module_cli.is_file():
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_ADAPTER_MISSING",
            "FOIL route adapter path does not match the active repository",
        )
    snapshot = capability_snapshot(tool_definitions)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(module_cli),
                "--root",
                str(repository_root),
                "foil-route",
            ],
            input=json.dumps(
                snapshot,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            cwd=repository_root,
            env=_adapter_environment(task_id, repository_root),
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=DEFAULT_ADAPTER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_TIMEOUT",
            "FOIL route adapter exceeded its bounded timeout",
        ) from exc
    except OSError as exc:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_START_FAILED",
            "FOIL route adapter could not start: " + type(exc).__name__,
        ) from exc
    return _parse_route(task_id, completed.stdout, completed.returncode)


def route_instruction(route: dict[str, Any]) -> str:
    """Render the bounded public route trace for the first model request."""

    projection = {
        "schema": route["schema"],
        "route_content_hash": route["content_hash"],
        "task_id": route["task_id"],
        "mode": route["mode"],
        "authority_ceiling": route["authority_ceiling"],
        "policy_version": route["policy_version"],
        "trace": route["trace"],
        "primary_effort_mode": route["primary_effort_mode"],
        "task_complements": route["task_complements"],
        "targeted_complement": route["targeted_complement"],
        "actions": route["actions"],
        "required_verifiers": route["required_verifiers"],
        "pending_verifiers": route["pending_verifiers"],
        "minimum_capability_bundle": route["minimum_capability_bundle"],
        "capability_bundle_complete": route["capability_bundle_complete"],
        "missing_capabilities": route["missing_capabilities"],
        "should_stop": route["should_stop"],
        "stop_reason": route["stop_reason"],
        "execution_authorized": False,
        "canonical_authority": "NONE",
    }
    rendered = (
        _ROUTE_MARKER
        + "\n"
        + "This is proposal-only routing guidance. It is not evidence, a receipt, "
        + "a verdict, or release authority. Re-read canonical status when needed.\n"
        + json.dumps(
            projection,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
        + _ROUTE_END_MARKER
    )
    if len(rendered) > MAX_FOIL_ROUTE_PROMPT_CHARS:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_PROMPT_TOO_LARGE",
            "FOIL route instruction exceeded the bounded prompt allowance",
        )
    return rendered


def inject_advisory_route(prompt: str, route: dict[str, Any]) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_PROMPT_INVALID",
            "FOIL route requires a non-empty runtime prompt",
        )
    if _ROUTE_MARKER in prompt or _ROUTE_END_MARKER in prompt:
        raise FoilRouteBridgeError(
            "FOIL_ROUTE_PROMPT_COLLISION",
            "runtime prompt already contains a reserved FOIL route marker",
        )
    return route_instruction(route) + "\n\n" + prompt
