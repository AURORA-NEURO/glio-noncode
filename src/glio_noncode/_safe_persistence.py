"""Small, symlink-aware atomic persistence primitives for text artifacts."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from .errors import ValidationError


def _validate_parent(parent: Path, field: str) -> None:
    """Reject symlinked or non-directory components on the output path."""

    current = parent
    while True:
        if current.is_symlink():
            raise ValidationError(f"{field} must not traverse symlinked directories")
        if current.exists() and not current.is_dir():
            raise ValidationError(f"{field} parent must be a directory")
        if current == current.parent:
            break
        current = current.parent


def _validate_target(target: Path, field: str) -> None:
    _validate_parent(target.parent, field)
    if target.is_symlink():
        raise ValidationError(f"{field} must not be a symlink")
    if target.exists() and not target.is_file():
        raise ValidationError(f"{field} must be a regular file")


def _sync_directory(path: Path) -> None:
    """Best-effort directory fsync after replacing a file."""

    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def atomic_write_bytes(path: str | Path, payload: bytes, *, field: str = "output path") -> Path:
    """Atomically replace a regular output file without following symlinks."""

    target = Path(path)
    _validate_target(target, field)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # Re-check immediately before replacement to avoid replacing a target
        # that was swapped for a symlink while the payload was being written.
        _validate_target(target, field)
        os.replace(temporary, target)
        _sync_directory(target.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def atomic_write_text(
    path: str | Path,
    text: str,
    *,
    field: str = "output path",
    encoding: str = "utf-8",
) -> Path:
    """Atomically replace a regular text output file without symlink traversal."""

    if not isinstance(text, str):
        raise ValidationError("text payload must be a string")
    try:
        payload = text.encode(encoding)
    except (LookupError, UnicodeError) as exc:
        raise ValidationError("text payload encoding is invalid") from exc
    return atomic_write_bytes(path, payload, field=field)


def read_bytes(path: str | Path, *, field: str = "input path") -> bytes:
    """Read a regular file without following symlinked fixture paths."""

    target = Path(path)
    _validate_target(target, field)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags)
    except OSError as exc:
        if target.is_symlink():
            raise ValidationError(f"{field} must not be a symlink") from exc
        raise
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValidationError(f"{field} must be a regular file")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            payload = handle.read()
        # Windows does not expose O_NOFOLLOW; catch a target swapped to a
        # symlink while opening before returning any untrusted bytes.
        if target.is_symlink():
            raise ValidationError(f"{field} must not be a symlink")
        return payload
    finally:
        if descriptor != -1:
            os.close(descriptor)


def read_text(
    path: str | Path,
    *,
    field: str = "input path",
    encoding: str = "utf-8",
) -> str:
    """Read and decode a regular text file without symlink traversal."""

    try:
        return read_bytes(path, field=field).decode(encoding)
    except LookupError as exc:
        raise ValidationError("text input encoding is invalid") from exc


__all__ = ["atomic_write_bytes", "atomic_write_text"]
