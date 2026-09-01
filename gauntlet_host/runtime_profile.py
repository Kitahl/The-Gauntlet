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
    GAUNTLET_ACTIVE_TOOLS,
    GAUNTLET_PLUGIN_ID,
    GAUNTLET_PLUGIN_SOURCE,
    GAUNTLET_TOOLSET,
    GOVERNED_PROFILE_NAME,
    HERMES_CLI_TOOLSET,
    LEAN_PROFILE_NAME,
    REPO_ROOT,
    SUPPORTED_RUNTIME_PROFILES,
)

GAUNTLET_PLUGIN_MANIFEST = """\
manifest_version: 2
name: gauntlet
version: 0.4.0
description: BASTION-01 lean compiled tools, sparse context, and bounded operational rehydration.
author: Rookframe Research
kind: standalone
provides_tools:
  - gauntlet_task_status_compact
  - gauntlet_obligation_get
  - gauntlet_release_status
  - gauntlet_artifact_get
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
    context_engine_name: str
    config_sha256: str
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
    inherited_config_path: str | None
    inherited_config_sha256: str | None
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


def normal_hermes_home() -> Path:
    """Return the pinned Hermes platform-native default home."""

    if os.name == "nt":
        roaming_root = os.environ.get("APPDATA", "").strip()
        base = (
            Path(roaming_root).parent / "Local"
            if roaming_root
            else Path.home() / ("App" + "Data") / "Local"
        )
        return base.expanduser() / "hermes"
    return Path.home().expanduser() / ".hermes"


def default_runtime_home(profile_name: str = LEAN_PROFILE_NAME) -> Path:
    """Return a dedicated persistent home for one supported profile."""

    if profile_name == LEAN_PROFILE_NAME:
        return Path.home().expanduser() / ".gauntlet" / "runtime"
    if profile_name == GOVERNED_PROFILE_NAME:
        # A real Hermes named-profile layout preserves read-only fallback to the
        # normal auth store while isolating sessions, memory, skills, and writes.
        return normal_hermes_home() / "profiles" / "gauntlet-governed"
    raise RuntimeProfileError(
        "RUNTIME_PROFILE_UNSUPPORTED",
        "runtime profile must be one of: " + ", ".join(SUPPORTED_RUNTIME_PROFILES),
    )


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

    context = _mapping(config, "context")
    context["engine"] = "gauntlet-sparse"

    auxiliary = _mapping(config, "auxiliary")
    background_review = _mapping(auxiliary, "background_review")
    background_review["enabled"] = False
    title_generation = _mapping(auxiliary, "title_generation")
    title_generation["enabled"] = False

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


def _apply_governed_policy(config: dict[str, Any]) -> None:
    """Apply full native Hermes capability with Gauntlet-owned release control."""

    config["toolsets"] = [HERMES_CLI_TOOLSET, GAUNTLET_TOOLSET]

    context = _mapping(config, "context")
    context["engine"] = "compressor"

    auxiliary = _mapping(config, "auxiliary")
    auxiliary["free_only"] = True
    background_review = _mapping(auxiliary, "background_review")
    background_review["enabled"] = True
    background_review["max_input_tokens"] = 60_000
    # Preserve the proven no-title-call saving without reducing task capability.
    title_generation = _mapping(auxiliary, "title_generation")
    title_generation["enabled"] = False

    agent = _mapping(config, "agent")
    agent["tool_use_enforcement"] = "auto"
    agent["execution_guidance"] = "auto"
    agent["intent_ack_continuation"] = True
    agent["stall_guards"] = True
    agent["task_completion_guidance"] = True
    agent["parallel_tool_call_guidance"] = True
    agent["environment_probe"] = True
    agent["coding_context"] = "auto"
    agent["verify_on_stop"] = True

    memory = _mapping(config, "memory")
    memory["memory_enabled"] = True
    memory["user_profile_enabled"] = True
    memory["write_approval"] = True

    skills = _mapping(config, "skills")
    external = skills.get("external_dirs", [])
    if not isinstance(external, list) or not all(isinstance(item, str) for item in external):
        raise RuntimeProfileError(
            "RUNTIME_CONFIG_INVALID",
            "Gauntlet runtime config field skills.external_dirs must be a string array",
        )
    skill_root = str((REPO_ROOT / "skills").resolve(strict=False))
    skills["external_dirs"] = list(
        dict.fromkeys([*(item.strip() for item in external if item.strip()), skill_root])
    )
    skills["project_discovery"] = True
    trusted = skills.get("trusted_project_dirs", [])
    if not isinstance(trusted, list) or not all(isinstance(item, str) for item in trusted):
        raise RuntimeProfileError(
            "RUNTIME_CONFIG_INVALID",
            "Gauntlet runtime config field skills.trusted_project_dirs must be a string array",
        )
    skills["trusted_project_dirs"] = list(
        dict.fromkeys(
            [*(item.strip() for item in trusted if item.strip()), str(REPO_ROOT.resolve())]
        )
    )
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


def prepare_runtime_profile(
    runtime_home: Path | None = None,
    *,
    profile_name: str = LEAN_PROFILE_NAME,
    base_config_path: Path | None = None,
) -> RuntimeProfile:
    """Create isolated runtime state, plugin files, and the selected policy."""

    if profile_name not in SUPPORTED_RUNTIME_PROFILES:
        raise RuntimeProfileError(
            "RUNTIME_PROFILE_UNSUPPORTED",
            "runtime profile must be one of: " + ", ".join(SUPPORTED_RUNTIME_PROFILES),
        )
    home = (runtime_home or default_runtime_home(profile_name)).expanduser().resolve(strict=False)
    normal_home = normal_hermes_home().resolve(strict=False)
    if home == normal_home:
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
        "operational/tool-results",
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
    inherited_path: Path | None = None
    inherited_digest: str | None = None
    if profile_name == GOVERNED_PROFILE_NAME:
        inherited_path = (base_config_path or (normal_home / "config.yaml")).expanduser()
        config = _read_config(inherited_path)
        if inherited_path.is_file():
            try:
                inherited_digest = hashlib.sha256(inherited_path.read_bytes()).hexdigest()
            except OSError as exc:
                raise RuntimeProfileError(
                    "RUNTIME_CONFIG_UNREADABLE",
                    f"cannot hash inherited Hermes runtime config: {exc}",
                ) from exc
        _apply_governed_policy(config)
    else:
        config = _read_config(config_path)
        _apply_alpha_policy(config)
    rendered = _render_config(config)
    _write_if_changed(config_path, rendered)

    os.environ["HERMES_HOME"] = str(home)
    config_digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()

    return RuntimeProfile(
        runtime_home=str(home),
        config_path=str(config_path),
        profile_name=profile_name,
        context_engine_name=(
            "gauntlet-sparse" if profile_name == LEAN_PROFILE_NAME else "compressor"
        ),
        config_sha256=config_digest,
        background_review_enabled=profile_name == GOVERNED_PROFILE_NAME,
        automatic_title_generation_enabled=False,
        memory_write_approval=True,
        memory_enabled=profile_name == GOVERNED_PROFILE_NAME,
        user_profile_enabled=profile_name == GOVERNED_PROFILE_NAME,
        skills_write_approval=True,
        skills_project_discovery=profile_name == GOVERNED_PROFILE_NAME,
        execution_guidance_enabled=profile_name == GOVERNED_PROFILE_NAME,
        task_completion_guidance_enabled=profile_name == GOVERNED_PROFILE_NAME,
        parallel_tool_call_guidance_enabled=True,
        coding_context_enabled=profile_name == GOVERNED_PROFILE_NAME,
        context_files_enabled=profile_name == GOVERNED_PROFILE_NAME,
        environment_probe_enabled=profile_name == GOVERNED_PROFILE_NAME,
        verify_on_stop_enabled=profile_name == GOVERNED_PROFILE_NAME,
        mcp_discovery_enabled=profile_name == GOVERNED_PROFILE_NAME,
        delegation_enabled=profile_name == GOVERNED_PROFILE_NAME,
        auto_release_enabled=False,
        max_iterations=64 if profile_name == GOVERNED_PROFILE_NAME else 8,
        inherited_config_path=str(inherited_path) if inherited_path is not None else None,
        inherited_config_sha256=inherited_digest,
        gauntlet_plugin_enabled=True,
        plugin_path=str(plugin_path),
        plugin_manifest_path=str(manifest_path),
        plugin_sha256=plugin_digest,
        plugin_tools=GAUNTLET_ACTIVE_TOOLS,
        token_measurement_root=str(measurement_root),
        token_measurement_key_path=str(measurement_key_path),
        token_measurement_key_id=measurement_key_id,
        session_binding_key_path=str(session_binding_key_path),
        session_binding_key_id=session_binding_key_id,
        session_lock_root=str(session_binding_root / "locks"),
        created_directories=tuple(created),
    )
