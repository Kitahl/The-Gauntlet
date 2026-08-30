"""Private, bounded lifecycle for large Gauntlet runtime tool results."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ARTIFACT_TOOL_NAME = "gauntlet_artifact_get"
ARTIFACT_SCHEMA = "gauntlet.operational-tool-result.v1"
REFERENCE_SCHEMA = "gauntlet.tool-result-reference.v1"
CURRENT_CALL_SCHEMA = "gauntlet.tool-result-current-call.v1"
PAGE_SCHEMA = "gauntlet.operational-artifact-page.v1"
REJECTION_SCHEMA = "gauntlet.tool-result-rejection.v1"

INLINE_RESULT_CHARS = 8_000
MAX_ARTIFACT_CHARS = 2_000_000
MAX_PAGE_CHARS = 4_096
DEFAULT_PAGE_CHARS = 2_048
ARTIFACT_TTL_SECONDS = 86_400
MAX_SUMMARY_CHARS = 512

_ARTIFACT_ID = re.compile(r"^art_[0-9a-f]{64}$")
_SECRET_ASSIGNMENT = re.compile(
    r"(?im)(?P<prefix>^|[^A-Za-z0-9_]|\\[nr])"
    r"(?P<key>api[_-]?key|authorization|bearer|token|secret|password)"
    r"(?P<key_quote>[\"']?)(?P<separator>\s*[:=]\s*)"
    r"(?P<value>bearer\s+[^\s,;\\\"'}\]]+|\"(?:[^\"\\]|\\.)*\"|"
    r"'(?:[^'\\]|\\.)*'|[^\s,;\\\"'}\]]+)"
)
_SECRET_TOKENS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
)


class ToolResultLifecycleError(RuntimeError):
    """Typed operational-artifact failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _binding_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _iso_timestamp(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).isoformat().replace("+00:00", "Z")


def redact_tool_result(content: str) -> tuple[str, int]:
    """Return a deterministic redacted projection; never persist the supplied raw text."""

    redactions = 0

    def assignment_replacement(match: re.Match[str]) -> str:
        nonlocal redactions
        redactions += 1
        value = match.group("value")
        quoted = value[0] if value and value[0] in {'"', "'"} else ""
        replacement = f"{quoted}<redacted>{quoted}"
        return (
            match.group("prefix")
            + match.group("key")
            + match.group("key_quote")
            + match.group("separator")
            + replacement
        )

    sanitized = _SECRET_ASSIGNMENT.sub(assignment_replacement, content)
    for pattern in _SECRET_TOKENS:
        sanitized, count = pattern.subn("<redacted-secret>", sanitized)
        redactions += count
    return sanitized, redactions


def _deterministic_summary(content: str) -> str:
    """Extract a bounded structural summary without an auxiliary model call."""

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        keys = sorted(str(key) for key in parsed)[:16]
        details: list[str] = [f"JSON object with {len(parsed)} top-level keys"]
        if keys:
            details.append("keys=" + ",".join(keys))
        for key in ("schema", "status", "action", "error", "message"):
            value = parsed.get(key)
            if isinstance(value, (str, int, float, bool)):
                details.append(f"{key}={str(value)[:96]}")
        summary = "; ".join(details)
    elif isinstance(parsed, list):
        summary = f"JSON array with {len(parsed)} items"
    else:
        lines = [" ".join(line.split()) for line in content.splitlines() if line.strip()]
        preview = " | ".join(lines[:2])
        summary = f"Text result with {len(content)} characters and {len(lines)} non-empty lines"
        if preview:
            summary += ": " + preview
    return summary[:MAX_SUMMARY_CHARS]


@dataclass(frozen=True, slots=True)
class ExternalizedToolResult:
    artifact_id: str
    sha256: str
    content: str
    reference: str
    original_chars: int
    stored_chars: int
    reference_chars: int
    redactions: int
    expires_at: str


class OperationalArtifactStore:
    """Task/session-bound private store for selected large operational results."""

    def __init__(
        self,
        runtime_home: str | Path,
        *,
        task_id: str,
        session_id: str,
        clock: Callable[[], float] = time.time,
        ttl_seconds: int = ARTIFACT_TTL_SECONDS,
        max_artifact_chars: int = MAX_ARTIFACT_CHARS,
    ) -> None:
        if not isinstance(task_id, str) or not task_id:
            raise ToolResultLifecycleError(
                "ARTIFACT_TASK_BINDING_MISSING", "task binding is required"
            )
        if not isinstance(session_id, str) or not session_id:
            raise ToolResultLifecycleError(
                "ARTIFACT_SESSION_BINDING_MISSING", "session binding is required"
            )
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise ToolResultLifecycleError("ARTIFACT_POLICY_INVALID", "artifact TTL is invalid")
        if (
            isinstance(max_artifact_chars, bool)
            or not isinstance(max_artifact_chars, int)
            or max_artifact_chars < INLINE_RESULT_CHARS
        ):
            raise ToolResultLifecycleError(
                "ARTIFACT_POLICY_INVALID", "artifact size bound is invalid"
            )

        self.runtime_home = Path(runtime_home).expanduser().resolve(strict=False)
        self.task_hash = _binding_hash(task_id)
        self.session_hash = _binding_hash(session_id)
        self.root = (
            self.runtime_home
            / "operational"
            / "tool-results"
            / self.task_hash[:24]
            / self.session_hash[:24]
        ).resolve(strict=False)
        try:
            self.root.relative_to(self.runtime_home / "operational" / "tool-results")
        except ValueError as exc:
            raise ToolResultLifecycleError(
                "ARTIFACT_ROOT_INVALID", "artifact root escaped the isolated runtime home"
            ) from exc
        self.clock = clock
        self.ttl_seconds = ttl_seconds
        self.max_artifact_chars = max_artifact_chars
        self.externalized: list[dict[str, Any]] = []
        self.rehydrated_pages: list[dict[str, Any]] = []
        self.rejected: list[dict[str, Any]] = []
        self._secure_directory(self.root)
        self._cleanup_expired()

    @classmethod
    def from_environment(cls) -> "OperationalArtifactStore":
        values = {
            name: os.environ.get(name, "").strip()
            for name in ("HERMES_HOME", "GAUNTLET_TASK_ID", "GAUNTLET_SESSION_ID")
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ToolResultLifecycleError(
                "ARTIFACT_ENVIRONMENT_MISSING",
                "required artifact environment is missing: " + ", ".join(missing),
            )
        return cls(
            values["HERMES_HOME"],
            task_id=values["GAUNTLET_TASK_ID"],
            session_id=values["GAUNTLET_SESSION_ID"],
        )

    @staticmethod
    def _secure_directory(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        try:
            path.chmod(0o700)
        except OSError:
            pass

    @staticmethod
    def _secure_file(path: Path) -> None:
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def _artifact_path(self, artifact_id: str) -> Path:
        if not isinstance(artifact_id, str) or not _ARTIFACT_ID.fullmatch(artifact_id):
            raise ToolResultLifecycleError(
                "ARTIFACT_ID_INVALID", "artifact ID did not match the content-addressed contract"
            )
        return self.root / f"{artifact_id}.json"

    def _cleanup_expired(self) -> None:
        now = self.clock()
        for path in self.root.glob("art_*.json"):
            try:
                if path.stat().st_mtime + self.ttl_seconds < now:
                    path.unlink()
            except OSError:
                continue

    def _atomic_write(self, path: Path, document: dict[str, Any]) -> None:
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            temporary.write_text(_canonical_json(document) + "\n", encoding="utf-8")
            self._secure_file(temporary)
            os.replace(temporary, path)
            self._secure_file(path)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise ToolResultLifecycleError(
                "ARTIFACT_WRITE_FAILED", f"operational artifact write failed: {type(exc).__name__}"
            ) from exc

    def externalize(
        self,
        content: Any,
        *,
        tool_name: str,
        tool_call_id: str,
    ) -> ExternalizedToolResult | None:
        if not isinstance(content, str) or len(content) <= INLINE_RESULT_CHARS:
            return None
        if tool_name == ARTIFACT_TOOL_NAME or parse_reference(content) is not None:
            return None

        sanitized, redactions = redact_tool_result(content)
        if len(sanitized) > self.max_artifact_chars:
            digest = _sha256(sanitized)
            self.rejected.append(
                {
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "sha256": digest,
                    "chars": len(sanitized),
                    "reason": "ARTIFACT_SIZE_BOUND_EXCEEDED",
                }
            )
            raise ToolResultLifecycleError(
                "ARTIFACT_SIZE_BOUND_EXCEEDED",
                f"tool result exceeded the {self.max_artifact_chars}-character artifact bound",
            )

        digest = _sha256(sanitized)
        artifact_id = f"art_{digest}"
        created_epoch = self.clock()
        expires_epoch = created_epoch + self.ttl_seconds
        document = {
            "schema": ARTIFACT_SCHEMA,
            "artifact_id": artifact_id,
            "sha256": digest,
            "task_binding_hash": self.task_hash,
            "session_binding_hash": self.session_hash,
            "tool_name": str(tool_name)[:256],
            "tool_call_id_hash": _binding_hash(str(tool_call_id)),
            "created_at": _iso_timestamp(created_epoch),
            "created_epoch": created_epoch,
            "expires_at": _iso_timestamp(expires_epoch),
            "expires_epoch": expires_epoch,
            "stored_chars": len(sanitized),
            "redactions": redactions,
            "authority": "OPERATIONAL_ONLY",
            "canonical_evidence": False,
            "content": sanitized,
        }
        path = self._artifact_path(artifact_id)
        if not path.exists():
            self._atomic_write(path, document)
        else:
            document = self._load_document(artifact_id)

        reference_payload = {
            "schema": REFERENCE_SCHEMA,
            "artifact_id": artifact_id,
            "sha256": digest,
            "summary": _deterministic_summary(sanitized),
            "stored_chars": len(sanitized),
            "redactions": redactions,
            "expires_at": document["expires_at"],
            "authority": "OPERATIONAL_ONLY",
            "canonical_evidence": False,
            "rehydrate": {
                "tool": ARTIFACT_TOOL_NAME,
                "offset": 0,
                "limit": DEFAULT_PAGE_CHARS,
                "maximum_limit": MAX_PAGE_CHARS,
            },
        }
        reference = _canonical_json(reference_payload)
        result = ExternalizedToolResult(
            artifact_id=artifact_id,
            sha256=digest,
            content=sanitized,
            reference=reference,
            original_chars=len(content),
            stored_chars=len(sanitized),
            reference_chars=len(reference),
            redactions=redactions,
            expires_at=document["expires_at"],
        )
        self.externalized.append(
            {
                key: value
                for key, value in asdict(result).items()
                if key not in {"content", "reference"}
            }
            | {"tool_name": tool_name, "tool_call_id": tool_call_id}
        )
        return result

    def rejection(self, content: Any, exc: ToolResultLifecycleError) -> str:
        text = content if isinstance(content, str) else _canonical_json(content)
        sanitized, redactions = redact_tool_result(text)
        return _canonical_json(
            {
                "schema": REJECTION_SCHEMA,
                "status": "REJECTED",
                "error": {"code": exc.code, "message": exc.message[:512]},
                "sha256": _sha256(sanitized),
                "chars": len(sanitized),
                "redactions": redactions,
                "raw_content_included": False,
                "authority": "OPERATIONAL_ONLY",
            }
        )

    def _load_document(self, artifact_id: str) -> dict[str, Any]:
        path = self._artifact_path(artifact_id)
        try:
            if path.stat().st_size > (self.max_artifact_chars * 4 + 16_384):
                raise ToolResultLifecycleError(
                    "ARTIFACT_FILE_TOO_LARGE", "artifact file exceeded its storage bound"
                )
            document = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ToolResultLifecycleError("ARTIFACT_NOT_FOUND", "artifact was not found") from exc
        except json.JSONDecodeError as exc:
            raise ToolResultLifecycleError("ARTIFACT_CORRUPT", "artifact JSON is invalid") from exc
        except OSError as exc:
            raise ToolResultLifecycleError(
                "ARTIFACT_READ_FAILED", f"artifact read failed: {type(exc).__name__}"
            ) from exc
        if not isinstance(document, dict) or document.get("schema") != ARTIFACT_SCHEMA:
            raise ToolResultLifecycleError("ARTIFACT_SCHEMA_MISMATCH", "artifact schema is invalid")
        if (
            document.get("artifact_id") != artifact_id
            or document.get("task_binding_hash") != self.task_hash
            or document.get("session_binding_hash") != self.session_hash
        ):
            raise ToolResultLifecycleError(
                "ARTIFACT_BINDING_MISMATCH", "artifact did not match the bound task and session"
            )
        expires_epoch = document.get("expires_epoch")
        if isinstance(expires_epoch, bool) or not isinstance(expires_epoch, (int, float)):
            raise ToolResultLifecycleError("ARTIFACT_CORRUPT", "artifact expiry is invalid")
        if expires_epoch < self.clock():
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ToolResultLifecycleError("ARTIFACT_EXPIRED", "artifact has expired")
        content = document.get("content")
        if (
            not isinstance(content, str)
            or len(content) > self.max_artifact_chars
            or document.get("stored_chars") != len(content)
            or document.get("sha256") != _sha256(content)
            or artifact_id != f"art_{_sha256(content)}"
        ):
            raise ToolResultLifecycleError("ARTIFACT_HASH_MISMATCH", "artifact content is invalid")
        return document

    def load_full(self, artifact_id: str) -> str:
        """Internal first-call loader; not exposed as an unbounded model tool."""

        return str(self._load_document(artifact_id)["content"])

    def retrieve(
        self, artifact_id: str, *, offset: int = 0, limit: int = DEFAULT_PAGE_CHARS
    ) -> str:
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ToolResultLifecycleError("ARTIFACT_OFFSET_INVALID", "offset must be non-negative")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > MAX_PAGE_CHARS
        ):
            raise ToolResultLifecycleError(
                "ARTIFACT_LIMIT_INVALID", f"limit must be between 1 and {MAX_PAGE_CHARS}"
            )
        document = self._load_document(artifact_id)
        content = str(document["content"])
        if offset > len(content):
            raise ToolResultLifecycleError(
                "ARTIFACT_OFFSET_INVALID", "offset exceeded artifact length"
            )
        page = content[offset : offset + limit]
        next_offset = offset + len(page)
        payload = {
            "schema": PAGE_SCHEMA,
            "artifact_id": artifact_id,
            "sha256": document["sha256"],
            "offset": offset,
            "returned_chars": len(page),
            "total_chars": len(content),
            "next_offset": next_offset if next_offset < len(content) else None,
            "has_more": next_offset < len(content),
            "content": page,
            "authority": "OPERATIONAL_ONLY",
            "canonical_evidence": False,
            "read_only": True,
            "mutation_performed": False,
        }
        self.rehydrated_pages.append(
            {
                "artifact_id": artifact_id,
                "offset": offset,
                "returned_chars": len(page),
                "has_more": payload["has_more"],
            }
        )
        return _canonical_json(payload)

    def metrics(self) -> dict[str, Any]:
        return {
            "schema": "gauntlet.tool-result-lifecycle-metrics.v1",
            "inline_threshold_chars": INLINE_RESULT_CHARS,
            "max_artifact_chars": self.max_artifact_chars,
            "max_rehydrate_page_chars": MAX_PAGE_CHARS,
            "ttl_seconds": self.ttl_seconds,
            "externalized_results": len(self.externalized),
            "externalized_chars": sum(item["stored_chars"] for item in self.externalized),
            "reference_chars": sum(item["reference_chars"] for item in self.externalized),
            "rehydrated_pages": len(self.rehydrated_pages),
            "rejected_results": len(self.rejected),
            "task_bound": True,
            "session_bound": True,
            "content_addressed": True,
            "private": True,
            "ttl_bounded": True,
            "canonical_evidence": False,
        }


def parse_reference(content: Any) -> dict[str, Any] | None:
    if not isinstance(content, str) or REFERENCE_SCHEMA not in content:
        return None
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        return None
    if (
        not isinstance(value, dict)
        or value.get("schema") != REFERENCE_SCHEMA
        or not isinstance(value.get("artifact_id"), str)
        or not _ARTIFACT_ID.fullmatch(value["artifact_id"])
        or value.get("sha256") != value["artifact_id"][4:]
    ):
        return None
    return value


def current_call_projection(reference: dict[str, Any], content: str) -> str:
    """Return full sanitized content plus its durable reference for one provider call."""

    return _canonical_json(
        {
            "schema": CURRENT_CALL_SCHEMA,
            "visibility": "CURRENT_PROVIDER_CALL_ONLY",
            "artifact": reference,
            "content": content,
            "authority": "OPERATIONAL_ONLY",
            "canonical_evidence": False,
        }
    )
