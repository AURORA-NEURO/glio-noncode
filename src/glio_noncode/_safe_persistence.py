"""Small, symlink-aware atomic persistence primitives for text artifacts."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from .errors import ValidationError

DEFAULT_MAX_READ_BYTES = 128 * 1024 * 1024


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

    if not isinstance(payload, (bytes, bytearray)):
        raise ValidationError("byte payload must be bytes")
    payload = bytes(payload)
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


def read_bytes(
    path: str | Path,
    *,
    field: str = "input path",
    max_bytes: int = DEFAULT_MAX_READ_BYTES,
) -> bytes:
    """Read a regular file without symlink traversal or unbounded allocation."""

    payload = read_bytes_bounded(path, max_bytes=max_bytes, field=field)
    if len(payload) > max_bytes:
        raise ValidationError(f"{field} exceeds the byte ceiling")
    return payload


def read_bytes_bounded(
    path: str | Path,
    *,
    max_bytes: int,
    field: str = "input path",
) -> bytes:
    """Read at most ``max_bytes + 1`` bytes without following symlinks.

    Callers can distinguish an exact payload from an oversized artifact while
    retaining the same descriptor-level protections as :func:`read_bytes`.
    The extra byte is intentional: it lets bounded callers reject an input
    before decoding or allocating an unbounded representation.
    """

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 0:
        raise ValidationError("byte ceiling must be a non-negative integer")
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
        # Reject oversized files from metadata before allocating any payload.
        # The extra-byte read below still covers a concurrent growth.
        if metadata.st_size > max_bytes:
            raise ValidationError(f"{field} exceeds the byte ceiling")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            payload = handle.read(max_bytes + 1)
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
    errors: str = "strict",
    max_bytes: int = DEFAULT_MAX_READ_BYTES,
) -> str:
    """Read and decode a regular text file without symlink traversal."""

    try:
        return read_bytes(path, field=field, max_bytes=max_bytes).decode(encoding, errors=errors)
    except LookupError as exc:
        raise ValidationError("text input encoding is invalid") from exc


__all__ = ["atomic_write_bytes", "atomic_write_text"]
