"""Canonical serialization and content addressing utilities."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any, Never, Self, SupportsIndex, overload


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if dataclasses.is_dataclass(value):
        return jsonable(value)
    if isinstance(value, Mapping):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Serialize a value deterministically for hashing and storage."""

    return json.dumps(
        value,
        default=_default,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_json(value: Any) -> str:
    """Serialize a value deterministically as UTF-8 JSON text."""

    return canonical_bytes(value).decode("utf-8")


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build JSON objects without silently discarding duplicate fields."""

    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object field: {key}")
        value[key] = item
    return value


def _reject_non_finite_json_number(value: str) -> Never:
    raise ValueError(f"non-finite JSON number: {value}")


def _strict_json_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite JSON number")
    return result


def _strict_json_loads(value: str | bytes | bytearray, **kwargs: Any) -> Any:
    """Decode JSON while rejecting duplicate fields and non-finite numbers."""

    kwargs.setdefault("object_pairs_hook", _strict_json_object)
    kwargs.setdefault("parse_constant", _reject_non_finite_json_number)
    kwargs.setdefault("parse_float", _strict_json_float)
    return json.loads(value, **kwargs)


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
        return {
            field.name: jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(jsonable(item) for item in value)
    return value


class _FrozenJsonObject(dict[str, Any]):
    """A JSON-native object that rejects ordinary mutation paths."""

    @staticmethod
    def _immutable() -> Never:
        raise TypeError("canonical metadata is immutable")

    def __setitem__(self, _key: str, _value: Any) -> None:
        self._immutable()

    def __delitem__(self, _key: str) -> None:
        self._immutable()

    def clear(self) -> None:
        self._immutable()

    def pop(self, _key: str, _default: Any = None) -> Any:
        self._immutable()

    def popitem(self) -> tuple[str, Any]:
        self._immutable()

    def setdefault(self, _key: str, _default: Any = None) -> Any:
        self._immutable()

    def update(self, *args: Any, **kwargs: Any) -> None:
        self._immutable()

    def __ior__(self, _other: object) -> Self:  # type: ignore[override, misc]
        self._immutable()

    def __copy__(self) -> _FrozenJsonObject:
        return self

    def __deepcopy__(self, _memo: dict[int, Any]) -> _FrozenJsonObject:
        return self


class _FrozenJsonArray(list[Any]):
    """A JSON-native array that rejects ordinary mutation paths."""

    @staticmethod
    def _immutable() -> Never:
        raise TypeError("canonical metadata is immutable")

    @overload
    def __setitem__(self, _key: SupportsIndex, _value: Any, /) -> None: ...

    @overload
    def __setitem__(
        self,
        _key: slice[SupportsIndex | None],
        _value: Iterable[Any],
        /,
    ) -> None: ...

    def __setitem__(
        self,
        _key: SupportsIndex | slice[SupportsIndex | None],
        _value: Any,
        /,
    ) -> None:
        self._immutable()

    def __delitem__(
        self,
        _key: SupportsIndex | slice[SupportsIndex | None],
        /,
    ) -> None:
        self._immutable()

    def append(self, _value: Any) -> None:
        self._immutable()

    def clear(self) -> None:
        self._immutable()

    def extend(self, _values: Iterable[Any]) -> None:
        self._immutable()

    def insert(self, _index: SupportsIndex, _value: Any, /) -> None:
        self._immutable()

    def pop(self, _index: SupportsIndex = -1, /) -> Any:
        self._immutable()

    def remove(self, _value: Any) -> None:
        self._immutable()

    def reverse(self) -> None:
        self._immutable()

    def sort(self, *, key: Any = None, reverse: bool = False) -> None:
        self._immutable()

    def __iadd__(self, _values: Iterable[Any], /) -> Self:  # type: ignore[misc]
        self._immutable()

    def __imul__(self, _count: SupportsIndex, /) -> Self:
        self._immutable()

    def __copy__(self) -> _FrozenJsonArray:
        return self

    def __deepcopy__(self, _memo: dict[int, Any]) -> _FrozenJsonArray:
        return self


def freeze_json(value: Any, *, field: str = "value") -> Any:
    """Copy a canonical JSON value into recursively immutable containers.

    Identity-bearing metadata must not retain aliases to caller-owned dictionaries
    or lists: mutating either after construction would otherwise change an object's
    serialized value and content address.  This helper also rejects values JSON can
    spell only non-portably (non-finite numbers), recursive containers, non-string
    object keys, and Python-only scalar/container types.
    """

    try:
        return _freeze_json(value, field=field, active=set())
    except RecursionError as exc:
        from .errors import ValidationError

        raise ValidationError(f"{field} nesting is too deep") from exc


def _freeze_json(value: Any, *, field: str, active: set[int]) -> Any:
    from .errors import ValidationError

    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValidationError(f"{field} numbers must be finite")
        return value
    if isinstance(value, Mapping):
        marker = id(value)
        if marker in active:
            raise ValidationError(f"{field} must not contain recursive containers")
        if any(type(key) is not str for key in value):
            raise ValidationError(f"{field} object keys must be strings")
        active.add(marker)
        try:
            frozen = {
                key: _freeze_json(item, field=f"{field}.{key}", active=active)
                for key, item in value.items()
            }
        finally:
            active.remove(marker)
        return _FrozenJsonObject(frozen)
    if isinstance(value, (list, tuple)):
        marker = id(value)
        if marker in active:
            raise ValidationError(f"{field} must not contain recursive containers")
        active.add(marker)
        try:
            return _FrozenJsonArray(
                _freeze_json(item, field=f"{field}[{index}]", active=active)
                for index, item in enumerate(value)
            )
        finally:
            active.remove(marker)
    raise ValidationError(f"{field} must contain only canonical JSON values")


def require_non_empty(value: str, field: str) -> str:
    """Normalize a required string and raise a readable contract error."""

    from .errors import ValidationError

    if type(value) is not str:
        raise ValidationError(f"{field} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized
