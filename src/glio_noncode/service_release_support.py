"""Shared deterministic helpers for service-release projections and exports."""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .serialization import canonical_json, content_hash, jsonable

SERVICE_RELEASE_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact_name",
        "email",
        "generated_by",
        "identity",
        "language",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "phone",
        "primary_agent",
        "primary_agent_id",
        "produced_by",
        "programming_language",
        "patient_id",
        "subject_id",
        "participant_id",
        "individual_id",
        "medical_record_number",
        "user_id",
        "username",
    }
)
SERVICE_RELEASE_PRIVATE_KEY_TOKENS = (
    "agent",
    "assistant",
    "author",
    "email",
    "identity",
    "language",
    "model",
    "patient",
    "subject",
    "participant",
    "individual",
    "phone",
    "user",
)
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def safe_component(value: str, field: str = "value") -> str:
    """Validate one path or release identifier component."""

    normalized = str(value).strip()
    if not _SAFE_COMPONENT.fullmatch(normalized) or normalized in {".", ".."}:
        raise ValidationError(f"{field} is not a safe service-release component")
    return normalized


def safe_relative_path(value: str) -> str:
    """Normalize an export path and reject traversal or drive prefixes."""

    normalized = str(value).replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or ":" in normalized:
        raise ValidationError("service-release paths must be safe relative paths")
    if any(not _SAFE_COMPONENT.fullmatch(part) for part in path.parts):
        raise ValidationError("service-release paths contain an unsafe component")
    return path.as_posix()


def forbidden_keys(value: Any, *, _path: str = "$") -> tuple[str, ...]:
    """Find forbidden metadata keys recursively in a public projection."""

    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key)
            lowered = name.casefold()
            if lowered in SERVICE_RELEASE_FORBIDDEN_KEYS or any(
                token in lowered for token in SERVICE_RELEASE_PRIVATE_KEY_TOKENS
            ):
                found.append(f"{_path}.{name}")
            found.extend(forbidden_keys(child, _path=f"{_path}.{name}"))
    elif isinstance(value, (list, tuple, set)):
        for index, child in enumerate(value):
            found.extend(forbidden_keys(child, _path=f"{_path}[{index}]"))
    return tuple(sorted(set(found)))


def public_value(value: Any) -> Any:
    """Convert a contract or projection into a JSON-safe public value."""

    projected = jsonable(value)
    violations = forbidden_keys(projected)
    if violations or contains_private_key(projected):
        details = ", ".join(violations) or "$private-key"
        raise ValidationError(f"service-release projection contains forbidden keys: {details}")
    return projected


def canonical_payload(value: Any) -> bytes:
    """Encode canonical JSON with one terminal newline for exact-byte exports."""

    return (canonical_json(public_value(value)) + "\n").encode("utf-8")


def csv_payload(rows: Iterable[Mapping[str, Any]]) -> bytes:
    """Encode deterministic CSV rows with sorted columns and JSON cells."""

    materialized = [dict(public_value(row)) for row in rows]
    fields = sorted({key for row in materialized for key in row}) or ["resource"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in materialized:
        writer.writerow(
            {
                key: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                if isinstance(value, (dict, list, tuple))
                else value
                for key, value in row.items()
            }
        )
    return output.getvalue().encode("utf-8")


def markdown_payload(title: str, rows: Iterable[Mapping[str, Any]]) -> bytes:
    """Encode a compact deterministic Markdown table for reviewers."""

    materialized = [dict(public_value(row)) for row in rows]
    fields = sorted({key for row in materialized for key in row}) or ["resource"]
    lines = [
        f"# {title}",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in materialized:
        values: list[str] = []
        for field in fields:
            value = row.get(field, "")
            if isinstance(value, (dict, list, tuple)):
                text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            else:
                text = str(value)
            values.append(text.replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return ("\n".join(lines) + "\n").encode("utf-8")


def artifact_address(payload: bytes) -> str:
    """Address exact artifact bytes without exposing their contents in the key."""

    return content_hash(
        {"bytes": payload.decode("utf-8")},
        prefix="service-release-artifact",
    )


def line_count(payload: bytes) -> int:
    """Count newline-delimited export lines, including a final non-newline line."""

    if not payload:
        return 0
    return payload.count(b"\n") + (0 if payload.endswith(b"\n") else 1)


def rows_from(value: Any) -> tuple[dict[str, Any], ...]:
    """Normalize a mapping/list projection into stable query rows."""

    projected = public_value(value)
    if isinstance(projected, list):
        return tuple(dict(item) for item in projected if isinstance(item, Mapping))
    if isinstance(projected, Mapping):
        return (dict(projected),)
    return ()


def text_matches(value: Mapping[str, Any], text: str | None) -> bool:
    """Apply case-insensitive bounded text matching to one row."""

    if not text:
        return True
    return str(text).casefold() in json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).casefold()


def address_map(values: Iterable[Any]) -> dict[str, Any]:
    """Return a collision-checked address map for contract objects."""

    result: dict[str, Any] = {}
    for value in values:
        address = str(getattr(value, "content_address", ""))
        if not address:
            raise ValidationError("address map values require content addresses")
        if address in result:
            raise ValidationError(f"duplicate content address: {address}")
        result[address] = value
    return result


__all__ = [
    "SERVICE_RELEASE_FORBIDDEN_KEYS",
    "SERVICE_RELEASE_PRIVATE_KEY_TOKENS",
    "address_map",
    "artifact_address",
    "canonical_payload",
    "csv_payload",
    "forbidden_keys",
    "line_count",
    "markdown_payload",
    "public_value",
    "rows_from",
    "safe_component",
    "safe_relative_path",
    "text_matches",
]
