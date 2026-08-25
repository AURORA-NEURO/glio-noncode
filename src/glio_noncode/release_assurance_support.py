"""Deterministic public-boundary and export helpers for release assurance."""

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

RELEASE_ASSURANCE_FORBIDDEN_KEYS = frozenset(
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
RELEASE_ASSURANCE_PRIVATE_TOKENS = (
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


def safe_relative_path(value: str) -> str:
    """Return a safe POSIX path for a release-assurance export."""

    normalized = str(value).replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or ":" in normalized:
        raise ValidationError("release-assurance path is unsafe")
    if any(not _SAFE_COMPONENT.fullmatch(part) for part in path.parts):
        raise ValidationError("release-assurance path contains an unsafe component")
    return path.as_posix()


def forbidden_keys(value: Any, *, _path: str = "$") -> tuple[str, ...]:
    """Return recursive forbidden metadata paths."""

    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key)
            lowered = name.casefold()
            if lowered in RELEASE_ASSURANCE_FORBIDDEN_KEYS or any(
                token in lowered for token in RELEASE_ASSURANCE_PRIVATE_TOKENS
            ):
                found.append(f"{_path}.{name}")
            found.extend(forbidden_keys(child, _path=f"{_path}.{name}"))
    elif isinstance(value, (list, tuple, set)):
        for index, child in enumerate(value):
            found.extend(forbidden_keys(child, _path=f"{_path}[{index}]"))
    return tuple(sorted(set(found)))


def public_value(value: Any) -> Any:
    """Convert a value to JSON-safe data and fail closed on private metadata."""

    projected = jsonable(value)
    violations = forbidden_keys(projected)
    if violations or contains_private_key(projected):
        raise ValidationError(
            "release-assurance public boundary violation: "
            + ", ".join(violations or ("$private-key",))
        )
    return projected


def canonical_payload(value: Any) -> bytes:
    """Encode one canonical JSON artifact with a terminal newline."""

    return (canonical_json(public_value(value)) + "\n").encode("utf-8")


def csv_payload(rows: Iterable[Mapping[str, Any]]) -> bytes:
    """Encode sorted-column CSV with deterministic nested-cell JSON."""

    materialized = [dict(public_value(row)) for row in rows]
    fields = sorted({key for row in materialized for key in row}) or ["resource"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in materialized:
        writer.writerow({
            key: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if isinstance(value, (dict, list, tuple)) else value
            for key, value in row.items()
        })
    return output.getvalue().encode("utf-8")


def markdown_payload(title: str, rows: Iterable[Mapping[str, Any]]) -> bytes:
    """Encode a compact public Markdown table."""

    materialized = [dict(public_value(row)) for row in rows]
    fields = sorted({key for row in materialized for key in row}) or ["resource"]
    lines = [f"# {title}", "", "| " + " | ".join(fields) + " |",
             "| " + " | ".join("---" for _ in fields) + " |"]
    for row in materialized:
        values = []
        for field in fields:
            value = row.get(field, "")
            text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if isinstance(value, (dict, list, tuple)) else str(value)
            values.append(text.replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return ("\n".join(lines) + "\n").encode("utf-8")


def artifact_address(payload: bytes) -> str:
    """Address exact UTF-8 artifact bytes."""

    return content_hash({"bytes": payload.decode("utf-8")}, prefix="release-assurance-artifact")


def line_count(payload: bytes) -> int:
    """Count newline-delimited lines in an artifact."""

    if not payload:
        return 0
    return payload.count(b"\n") + (0 if payload.endswith(b"\n") else 1)


def text_matches(row: Mapping[str, Any], text: str | None) -> bool:
    """Apply deterministic case-insensitive matching to a public row."""

    if not text:
        return True
    return str(text).casefold() in json.dumps(
        dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).casefold()


__all__ = [
    "RELEASE_ASSURANCE_FORBIDDEN_KEYS",
    "RELEASE_ASSURANCE_PRIVATE_TOKENS",
    "artifact_address",
    "canonical_payload",
    "csv_payload",
    "forbidden_keys",
    "line_count",
    "markdown_payload",
    "public_value",
    "safe_relative_path",
    "text_matches",
]
