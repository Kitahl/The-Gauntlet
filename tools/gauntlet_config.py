"""Shared configuration/runtime paths for the public Process Assurance tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from private_io import ensure_private_dir

CONFIG_NAME = ".gauntlet.json"
DEFAULT_CONFIG: dict[str, Any] = {
    "state_dir": ".egrt/state",
    "governing_files": [
        "README.md", "RESEARCH.md", "REPRODUCIBILITY.md", "ROADMAP.md",
        "docs/ARCHITECTURE.md", "docs/VNEXT_RUNTIME_PIPELINE.md",
        "docs/specs/COMMON_RUNTIME_CONTRACT.md",
        "skills/soul/SKILL.md", "skills/mathbot/SKILL.md",
        "skills/scoutbot/SKILL.md", "skills/novelbot/SKILL.md",
        "skills/codebot/SKILL.md", "skills/benchbot/SKILL.md",
        "skills/infinity-gauntlet/SKILL.md", "skills/meditate/SKILL.md",
        "skills/council-of-elders/SKILL.md", "skills/foil/SKILL.md",
    ],
    "runtime": {
        "enabled": True,
        "schema": "egrt.runtime.v1",
        "persist_raw_prompts": False,
        "persist_raw_tool_output": False,
        "release_gate": True,
        "active_task_required_for_gate": True,
    },
    "challenge": {
        "mode": "shadow",
        "max_total_per_obligation": 4,
        "max_load_bearing_per_obligation": 2,
        "max_selected_discriminators": 2,
        "allow_foil_proposals": True,
        "require_claim_native_receipt": True,
        "block_on_unavailable_load_bearing": True,
        "persist_raw_text": False,
    },
    "boundary": {
        "enabled": True,
        "near_duplicate_threshold": 0.72,
        "incident_refractory_turns": 3,
        "judge_model": None,
    },
    "ledger": {"enabled": False, "path": None, "accept_runtime_receipts": True},
}


def project_root(start: str | os.PathLike[str] | None = None) -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("EGR_PROJECT_DIR")
    if env:
        return Path(env).expanduser().resolve()
    p = Path(start or Path.cwd()).resolve()
    for candidate in (p, *p.parents):
        if (candidate / CONFIG_NAME).exists() or (candidate / ".git").exists():
            return candidate
    return p


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    path = root / CONFIG_NAME
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {CONFIG_NAME}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError(f"invalid {CONFIG_NAME}: top level must be an object")
    return _merge(DEFAULT_CONFIG, raw)


def challenge_config(root: Path | None = None) -> dict[str, Any]:
    config = load_config(root)
    challenge = dict(config.get("challenge") or {})
    override = os.environ.get("EGR_CHALLENGE_MODE")
    if override:
        override = override.strip().lower()
        if override not in {"off", "shadow", "enforced"}:
            raise RuntimeError("EGR_CHALLENGE_MODE must be off, shadow, or enforced")
        challenge["mode"] = override
    return challenge


def state_dir(root: Path | None = None, config: dict[str, Any] | None = None) -> Path:
    root = root or project_root()
    config = config or load_config(root)
    p = Path(str(config.get("state_dir") or ".egrt/state"))
    if not p.is_absolute():
        p = root / p
    return ensure_private_dir(p)
