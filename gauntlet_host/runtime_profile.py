"""Gauntlet-owned runtime home and alpha policy profile."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from gauntlet_host.constants import (
    GAUNTLET_PLUGIN_ID,
    GAUNTLET_PLUGIN_SOURCE,
    GAUNTLET_STATUS_TOOLS,
    GAUNTLET_TOOLSET,
)

GAUNTLET_PLUGIN_MANIFEST = """\
manifest_version: 2
name: gauntlet
version: 0.2.0
description: Lean read-only canonical task, obligation, and release status tools.
author: The Gauntlet
kind: standalone
provides_tools:
  - gauntlet_task_status_compact
  - gauntlet_obligation_get
  - gauntlet_release_status
"""


class RuntimeProfileError(RuntimeError):
    """Fail-closed runtime profile preparation error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    """Materialized Gauntlet-owned runtime profile."""

    runtime_home: str
    config_path: str
    profile_name: str
    config_sha256: str
    background_review_enabled: bool
    memory_write_approval: bool
    memory_enabled: bool
    user_profile_enabled: bool
    skills_write_approval: bool
    skills_project_discovery: bool
    execution_guidance_enabled: bool
    task_completion_guidance_enabled: bool
    parallel_tool_call_guidance_enabled: bool
    coding_context_enabled: bool
    gauntlet_plugin_enabled: bool
    plugin_path: str
    plugin_manifest_path: str
    plugin_sha256: str
    plugin_tools: tuple[str, ...]
    token_measurement_root: str
    token_measurement_key_path: str
    token_measurement_key_id: str
    session_binding_key_path: str
    session_binding_key_id: str
    session_lock_root: str
    created_directories: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def default_runtime_home() -> Path:
    """Return the dedicated runtime home, never the user's normal Hermes home."""

    return Path.home().expanduser() / ".gauntlet" / "runtime"


def _secure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def _secure_file(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _load_yaml_module() -> Any | None:
    try:
        import yaml
    except ModuleNotFoundError:
        return None
    return yaml


def _read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeProfileError(
            "RUNTIME_CONFIG_UNREADABLE",
            f"cannot read Gauntlet runtime config: {exc}",
        ) from exc

    if not text.strip():
        return {}

    yaml = _load_yaml_module()
    try:
        if yaml is not None:
            value = yaml.safe_load(text)
        else:
            value = json.loads(text)
    except Exception as exc:
        dependency_hint = ""
        if yaml is None:
            dependency_hint = " Install the vendored runtime dependencies to read YAML."
        raise RuntimeProfileError(
            "RUNTIME_CONFIG_INVALID",
            f"cannot parse Gauntlet runtime config.{dependency_hint}",
        ) from exc

    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RuntimeProfileError(
            "RUNTIME_CONFIG_INVALID",
            "Gauntlet runtime config must contain a mapping at its root",
        )
    return dict(value)


def _mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if value is None:
        result: dict[str, Any] = {}
        parent[key] = result
        return result
    if not isinstance(value, dict):
        raise RuntimeProfileError(
            "RUNTIME_CONFIG_INVALID",
            f"Gauntlet runtime config field {key!r} must be a mapping",
        )
    return value


def _string_list(parent: dict[str, Any], key: str) -> list[str]:
    value = parent.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeProfileError(
            "RUNTIME_CONFIG_INVALID",
            f"Gauntlet runtime config field plugins.{key} must be a string array",
        )
    return list(dict.fromkeys(item.strip() for item in value if item.strip()))


def _apply_alpha_policy(config: dict[str, Any]) -> None:
    """Apply the isolated, explicit gauntlet-lean.v1 runtime profile."""

    config["toolsets"] = [GAUNTLET_TOOLSET]

    auxiliary = _mapping(config, "auxiliary")
    background_review = _mapping(auxiliary, "background_review")
    background_review["enabled"] = False

    agent = _mapping(config, "agent")
    agent["tool_use_enforcement"] = False
    agent["execution_guidance"] = False
    agent["intent_ack_continuation"] = False
    agent["stall_guards"] = False
    agent["task_completion_guidance"] = False
    agent["parallel_tool_call_guidance"] = True
    agent["environment_probe"] = False
    agent["coding_context"] = "off"
    agent["verify_on_stop"] = False

    memory = _mapping(config, "memory")
    memory["memory_enabled"] = False
    memory["user_profile_enabled"] = False
    memory["provider"] = ""
    memory["write_approval"] = True

    skills = _mapping(config, "skills")
    skills["external_dirs"] = []
    skills["project_discovery"] = False
    skills["trusted_project_dirs"] = []
    skills["write_approval"] = True

    plugins = _mapping(config, "plugins")
    enabled = _string_list(plugins, "enabled")
    if GAUNTLET_PLUGIN_ID not in enabled:
        enabled.append(GAUNTLET_PLUGIN_ID)
    plugins["enabled"] = enabled

    disabled = _string_list(plugins, "disabled")
    plugins["disabled"] = [plugin_id for plugin_id in disabled if plugin_id != GAUNTLET_PLUGIN_ID]


def _render_config(config: dict[str, Any]) -> str:
    yaml = _load_yaml_module()
    if yaml is None:
        return json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return yaml.safe_dump(
        config,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
    )


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        _secure_file(temporary)
        os.replace(temporary, path)
        _secure_file(path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeProfileError(
            "RUNTIME_CONFIG_WRITE_FAILED",
            f"cannot write Gauntlet runtime file {path}: {exc}",
        ) from exc


def _write_if_changed(path: Path, content: str) -> None:
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else None
    except OSError as exc:
        raise RuntimeProfileError(
            "RUNTIME_FILE_UNREADABLE",
            f"cannot read Gauntlet runtime file {path}: {exc}",
        ) from exc
    if existing != content:
        _atomic_write(path, content)
    else:
        _secure_file(path)


def _measurement_key(path: Path) -> tuple[Path, str]:
    """Create or reuse the private local HMAC key for measurement digests."""

    try:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            key = path.read_bytes()
        else:
            key = secrets.token_bytes(32)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(key)
                handle.flush()
                os.fsync(handle.fileno())
        _secure_file(path)
    except OSError as exc:
        raise RuntimeProfileError(
            "TOKEN_MEASUREMENT_KEY_FAILED",
            f"cannot prepare token measurement key: {exc}",
        ) from exc
    if len(key) < 32:
        raise RuntimeProfileError(
            "TOKEN_MEASUREMENT_KEY_INVALID",
            "token measurement key must contain at least 32 bytes",
        )
    return path, hashlib.sha256(key).hexdigest()[:16]


def _session_binding_key(path: Path) -> tuple[Path, str]:
    """Create or reuse the private key that binds tasks to Hermes sessions."""

    try:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            key = path.read_bytes()
        else:
            key = secrets.token_bytes(32)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(key)
                handle.flush()
                os.fsync(handle.fileno())
        _secure_file(path)
    except OSError as exc:
        raise RuntimeProfileError(
            "SESSION_BINDING_KEY_FAILED",
            f"cannot prepare session-binding key: {exc}",
        ) from exc
    if len(key) < 32:
        raise RuntimeProfileError(
            "SESSION_BINDING_KEY_INVALID",
            "session-binding key must contain at least 32 bytes",
        )
    return path, hashlib.sha256(key).hexdigest()[:16]


def _materialize_gauntlet_plugin(home: Path) -> tuple[Path, Path, str]:
    if not GAUNTLET_PLUGIN_SOURCE.is_file():
        raise RuntimeProfileError(
            "GAUNTLET_PLUGIN_SOURCE_MISSING",
            f"Gauntlet runtime plugin source is missing: {GAUNTLET_PLUGIN_SOURCE}",
        )
    try:
        source = GAUNTLET_PLUGIN_SOURCE.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeProfileError(
            "GAUNTLET_PLUGIN_SOURCE_UNREADABLE",
            f"cannot read Gauntlet runtime plugin source: {exc}",
        ) from exc

    plugin_dir = home / "plugins" / GAUNTLET_PLUGIN_ID
    _secure_directory(plugin_dir)
    plugin_path = plugin_dir / "__init__.py"
    manifest_path = plugin_dir / "plugin.yaml"
    _write_if_changed(plugin_path, source)
    _write_if_changed(manifest_path, GAUNTLET_PLUGIN_MANIFEST)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return plugin_path, manifest_path, digest


def prepare_runtime_profile(runtime_home: Path | None = None) -> RuntimeProfile:
    """Create isolated runtime state, plugin files, and alpha policy."""

    home = (runtime_home or default_runtime_home()).expanduser().resolve(strict=False)
    normal_hermes_home = (Path.home().expanduser() / ".hermes").resolve(strict=False)
    if home == normal_hermes_home:
        raise RuntimeProfileError(
            "RUNTIME_HOME_COLLISION",
            "Gauntlet runtime home must not be the user's normal Hermes home",
        )

    relative_directories = (
        "",
        "memories",
        "skills",
        "cache",
        "logs",
        "pending",
        "pending/memory",
        "pending/skills",
        "plugins",
        f"plugins/{GAUNTLET_PLUGIN_ID}",
        "measurements",
        "measurements/token-efficiency",
        "operational",
        "operational/foil-routes",
        "session-bindings",
        "session-bindings/locks",
    )
    created: list[str] = []
    for relative in relative_directories:
        directory = home / relative if relative else home
        _secure_directory(directory)
        created.append(str(directory))

    plugin_path, manifest_path, plugin_digest = _materialize_gauntlet_plugin(home)
    measurement_root = home / "measurements" / "token-efficiency"
    measurement_key_path, measurement_key_id = _measurement_key(measurement_root / ".hmac-key")
    session_binding_root = home / "session-bindings"
    session_binding_key_path, session_binding_key_id = _session_binding_key(
        session_binding_root / ".hmac-key"
    )

    config_path = home / "config.yaml"
    config = _read_config(config_path)
    _apply_alpha_policy(config)
    rendered = _render_config(config)
    _write_if_changed(config_path, rendered)

    os.environ["HERMES_HOME"] = str(home)
    config_digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()

    return RuntimeProfile(
        runtime_home=str(home),
        config_path=str(config_path),
        profile_name="gauntlet-lean.v1",
        config_sha256=config_digest,
        background_review_enabled=False,
        memory_write_approval=True,
        memory_enabled=False,
        user_profile_enabled=False,
        skills_write_approval=True,
        skills_project_discovery=False,
        execution_guidance_enabled=False,
        task_completion_guidance_enabled=False,
        parallel_tool_call_guidance_enabled=True,
        coding_context_enabled=False,
        gauntlet_plugin_enabled=True,
        plugin_path=str(plugin_path),
        plugin_manifest_path=str(manifest_path),
        plugin_sha256=plugin_digest,
        plugin_tools=GAUNTLET_STATUS_TOOLS,
        token_measurement_root=str(measurement_root),
        token_measurement_key_path=str(measurement_key_path),
        token_measurement_key_id=measurement_key_id,
        session_binding_key_path=str(session_binding_key_path),
        session_binding_key_id=session_binding_key_id,
        session_lock_root=str(session_binding_root / "locks"),
        created_directories=tuple(created),
    )
