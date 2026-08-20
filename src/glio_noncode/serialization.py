"""Canonical serialization and content addressing utilities."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Serialize a value deterministically for hashing and storage."""

    return json.dumps(
        value,
        default=_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_json(value: Any) -> str:
    """Serialize a value deterministically as UTF-8 JSON text."""

    return canonical_bytes(value).decode("utf-8")


def content_hash(value: Any, *, prefix: str = "sha256") -> str:
    """Return a stable content address for a JSON-compatible value."""

    digest = hashlib.sha256(canonical_bytes(value)).hexdigest()
    return f"{prefix}:{digest}"


def hash_bytes(value: bytes, *, prefix: str = "sha256") -> str:
    """Hash raw bytes using the same address format as JSON objects."""

    return f"{prefix}:{hashlib.sha256(value).hexdigest()}"


def jsonable(value: Any) -> Any:
    """Convert nested dataclasses/enums to plain JSON-compatible values."""

    if dataclasses.is_dataclass(value):
        return {field.name: jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(jsonable(item) for item in value)
    return value


def require_non_empty(value: str, field: str) -> str:
    """Normalize a required string and raise a readable contract error."""

    from .errors import ValidationError

    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized
