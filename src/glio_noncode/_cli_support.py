"""Small JSON I/O helpers shared by lazy command groups."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

DEFAULT_MAX_JSON_BYTES = 16 * 1024 * 1024


def read_text(
    location: str,
    *,
    label: str = "input",
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
) -> str:
    if location == "-":
        text = sys.stdin.read(max_bytes + 1)
        if len(text.encode("utf-8")) > max_bytes:
            raise ValueError(f"{label} exceeds the {max_bytes}-byte limit")
        return text
    source = Path(location)
    if source.stat().st_size > max_bytes:
        raise ValueError(f"{label} exceeds the {max_bytes}-byte limit")
    payload = source.read_bytes()
    if len(payload) > max_bytes:
        raise ValueError(f"{label} exceeds the {max_bytes}-byte limit")
    return payload.decode("utf-8-sig")


def read_mapping(
    location: str,
    label: str,
    *,
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
) -> Mapping[str, Any]:
    value = read_json(location, label, max_bytes=max_bytes)
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return value


def read_json(
    location: str,
    label: str,
    *,
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
) -> Any:
    """Read one bounded JSON value without constraining its top-level shape."""

    return json.loads(read_text(location, label=label, max_bytes=max_bytes))


def write_json(value: object, output: str) -> None:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if output == "-":
        print(rendered)
        return
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered + "\n", encoding="utf-8")


__all__ = ["DEFAULT_MAX_JSON_BYTES", "read_json", "read_mapping", "read_text", "write_json"]
