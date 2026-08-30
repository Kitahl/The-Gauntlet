"""Private task-to-Hermes session binding and cross-process turn locking."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:  # POSIX
    import fcntl

    _HAVE_FLOCK = True
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]
    _HAVE_FLOCK = False

try:  # Windows
    import msvcrt

    _HAVE_MSVCRT = True
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None  # type: ignore[assignment]
    _HAVE_MSVCRT = False


SESSION_BINDING_DOMAIN = b"gauntlet.hermes-session.v1\x00"
SESSION_ID_PREFIX = "gauntlet-"


class SessionBindingError(RuntimeError):
    """Raised when a private task-to-session binding cannot be established."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SessionTurnLockTimeout(TimeoutError):
    """Raised when another process retains the same task turn lock."""


def derive_session_id(task_id: str, key_path: Path | str) -> str:
    """Derive one stable, non-reversible Hermes session id per Gauntlet task."""

    if not isinstance(task_id, str) or not task_id.strip():
        raise SessionBindingError(
            "SESSION_TASK_ID_INVALID",
            "task_id must be a non-empty string before session binding",
        )
    try:
        key = Path(key_path).read_bytes()
    except OSError as exc:
        raise SessionBindingError(
            "SESSION_BINDING_KEY_UNREADABLE",
            f"cannot read the private session-binding key: {exc}",
        ) from exc
    if len(key) < 32:
        raise SessionBindingError(
            "SESSION_BINDING_KEY_INVALID",
            "session-binding key must contain at least 32 bytes",
        )
    digest = hmac.new(
        key,
        SESSION_BINDING_DOMAIN + task_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{SESSION_ID_PREFIX}{digest[:32]}"


def session_turn_lock_path(lock_root: Path | str, session_id: str) -> Path:
    """Return the persistent lock-file path for one derived session id."""

    if not session_id.startswith(SESSION_ID_PREFIX):
        raise SessionBindingError(
            "SESSION_ID_INVALID",
            "Gauntlet session ids must use the private derived-id namespace",
        )
    return Path(lock_root) / f"{session_id}.turn"


@contextmanager
def exclusive_session_turn_lock(
    lock_path: Path | str,
    *,
    timeout: float,
) -> Iterator[None]:
    """Serialize a complete worker turn with a crash-safe kernel file lock.

    This is the repository-qualified lock pattern already used by
    ``tools/foil_task_guard.py``: ``flock`` on POSIX and a byte-range lock on
    Windows. The persistent file is not the lock; the held kernel handle is,
    so process death releases it automatically.
    """

    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + max(0.0, float(timeout))
    try:
        while True:
            try:
                if _HAVE_FLOCK:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                elif _HAVE_MSVCRT:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover - supported platforms have one primitive
                    raise SessionTurnLockTimeout(f"no file-locking primitive is available: {path}")
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise SessionTurnLockTimeout(
                        f"session remained busy for {timeout:g} seconds"
                    ) from exc
                time.sleep(0.01)
        try:
            yield
        finally:
            if _HAVE_FLOCK:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            else:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(descriptor)
