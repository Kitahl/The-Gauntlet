"""Restricted local persistence helpers for Gauntlet and FOIL runtime state."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

DIR_MODE = 0o700
FILE_MODE = 0o600


def _restrict(path: Path, mode: int) -> None:
    """Apply POSIX owner-only permissions where the platform exposes them."""
    if os.name == "nt":
        return
    try:
        path.chmod(mode)
    except OSError:
        pass


def ensure_private_dir(path: str | os.PathLike[str]) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    _restrict(target, DIR_MODE)
    return target


def write_private_text(
    path: str | os.PathLike[str],
    text: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Atomically write local state and restrict the resulting file to its owner."""
    target = Path(path)
    parent = ensure_private_dir(target.parent)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=parent, text=True)
    tmp = Path(temporary)
    try:
        _restrict(tmp, FILE_MODE)
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
        os.replace(tmp, target)
        _restrict(target, FILE_MODE)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return target
