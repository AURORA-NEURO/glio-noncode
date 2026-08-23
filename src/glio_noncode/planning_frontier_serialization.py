"""Safe JSON projection used by planning consumer views."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_HIDDEN_KEYS = {"raw_text", "raw_record", "patient_id", "sample_id", "access_token", "api_key"}


def safe_jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): "[omitted]" if str(key).lower() in _HIDDEN_KEYS else safe_jsonable(item) for key, item in value.items() if str(key).lower() not in {"raw_text", "raw_record"}}
    if isinstance(value, (tuple, list)):
        return tuple(safe_jsonable(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(safe_jsonable(item) for item in value))
    return value


__all__ = ["safe_jsonable"]
