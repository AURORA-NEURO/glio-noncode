"""Small JSON I/O helpers shared by lazy command groups."""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_text, read_bytes
from .errors import ValidationError

DEFAULT_MAX_JSON_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_JSON_NESTING_DEPTH = 100


def _positive_limit(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"JSON input contains duplicate object key: {key!r}")
        value[key] = item
    return value


def _reject_non_finite_json_number(_value: str) -> Any:
    raise ValueError("JSON input contains a non-finite number")


def _strict_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("JSON input contains a non-finite number")
    return parsed


def _validate_json_nesting(value: str, *, max_depth: int) -> None:
    depth = 0
    in_string = False
    escaped = False
    for character in value:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > max_depth:
                raise ValueError(f"JSON input nesting exceeds the {max_depth}-level limit")
        elif character in "]}":
            depth -= 1


def read_text(
    location: str,
    *,
    label: str = "input",
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
) -> str:
    max_bytes = _positive_limit(max_bytes, "max_bytes")
    if location == "-":
        text = sys.stdin.read(max_bytes + 1)
        if len(text.encode("utf-8")) > max_bytes:
            raise ValueError(f"{label} exceeds the {max_bytes}-byte limit")
        return text
    source = Path(location)
    try:
        payload = read_bytes(source, field=label)
    except ValueError:
        raise
    except (OSError, ValidationError) as error:
        # Keep the CLI's stable ValueError contract while refusing missing,
        # non-regular, or symlinked inputs from crossing the boundary.
        raise ValueError(f"{label} could not be read") from error
    if len(payload) > max_bytes:
        raise ValueError(f"{label} exceeds the {max_bytes}-byte limit")
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} is not valid UTF-8") from error


def read_mapping(
    location: str,
    label: str,
    *,
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
    max_nesting_depth: int = DEFAULT_MAX_JSON_NESTING_DEPTH,
) -> Mapping[str, Any]:
    value = read_json(
        location,
        label,
        max_bytes=max_bytes,
        max_nesting_depth=max_nesting_depth,
    )
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return value


def read_json(
    location: str,
    label: str,
    *,
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
    max_nesting_depth: int = DEFAULT_MAX_JSON_NESTING_DEPTH,
) -> Any:
    """Read one bounded JSON value without constraining its top-level shape."""

    max_nesting_depth = _positive_limit(max_nesting_depth, "max_nesting_depth")
    text = read_text(location, label=label, max_bytes=max_bytes)
    _validate_json_nesting(text, max_depth=max_nesting_depth)
    value = json.loads(
        text,
        object_pairs_hook=_strict_json_object,
        parse_constant=_reject_non_finite_json_number,
        parse_float=_strict_json_float,
    )
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError(f"{label} must contain canonical Unicode JSON") from exc
    return value


def write_json(value: object, output: str) -> None:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if output == "-":
        print(rendered)
        return
    destination = Path(output)
    _validate_parent(destination.parent, "CLI output")
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(destination, rendered + "\n", field="CLI output")


__all__ = [
    "DEFAULT_MAX_JSON_BYTES",
    "DEFAULT_MAX_JSON_NESTING_DEPTH",
    "read_json",
    "read_mapping",
    "read_text",
    "write_json",
]
