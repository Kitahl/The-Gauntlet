"""Restricted local persistence helpers for Gauntlet and FOIL runtime state."""
from __future__ import annotations

import contextlib
import os
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

DIR_MODE = 0o700
FILE_MODE = 0o600

REPLACE_ATTEMPTS = 20
REPLACE_DELAY = 0.01
LOCK_ATTEMPTS = 500
LOCK_DELAY = 0.01


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
        # os.fdopen takes ownership of fd; closing it again here would raise EBADF.
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
        _replace_with_retry(tmp, target)
        _restrict(target, FILE_MODE)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return target


def _replace_with_retry(source: Path, target: Path) -> None:
    """os.replace, retried briefly.

    On Windows a concurrent reader/writer holding the destination makes the rename
    fail with PermissionError even though the operation would succeed moments later.
    """
    last: OSError | None = None
    for _ in range(REPLACE_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except PermissionError as exc:  # pragma: no cover - platform dependent
            last = exc
            time.sleep(REPLACE_DELAY)
    if last is not None:  # pragma: no cover - platform dependent
        raise last


@contextlib.contextmanager
def file_lock(path: str | os.PathLike[str]) -> Iterator[None]:
    """Advisory cross-process lock keyed on a sidecar lock file.

    Used to serialise read-modify-write cycles over shared runtime state. The lock
    is advisory: only callers that take it are serialised.
    """
    target = Path(path)
    ensure_private_dir(target.parent)
    handle = open(target, "a+b")  # noqa: SIM115 - released in the finally block
    try:
        _acquire(handle)
        try:
            yield
        finally:
            _release(handle)
    finally:
        handle.close()


def _acquire(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        for attempt in range(LOCK_ATTEMPTS):
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if attempt == LOCK_ATTEMPTS - 1:
                    raise
                time.sleep(LOCK_DELAY)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _release(handle) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
