"""Shared pure helpers for the D01-D16 aggregate release closure.

The closure is intentionally a projection layer.  It reads the already accepted
offline handoff, copies only public aggregate fields, and addresses every new
projection independently.  These helpers keep that policy in one small,
auditable place so the API, command line surface, tests, and exporters cannot
silently drift apart.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath
from typing import Any

from .errors import ValidationError
from .serialization import canonical_json, content_hash, jsonable

PROGRAM_RELEASE_CLOSURE_FORBIDDEN_KEYS = frozenset(
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
PROGRAM_RELEASE_CLOSURE_PRIVATE_KEY_TOKENS = (
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
    """Normalize a path or identifier component without permitting traversal."""

    normalized = str(value).strip()
    if not _SAFE_COMPONENT.fullmatch(normalized) or normalized in {".", ".."}:
        raise ValidationError(f"{field} is not a safe closure component")
    return normalized


def safe_relative_path(value: str) -> str:
    """Return a normalized POSIX relative path suitable for export."""

    normalized = str(value).replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or ":" in normalized:
        raise ValidationError("closure export paths must be safe relative paths")
    if any(not _SAFE_COMPONENT.fullmatch(part) for part in path.parts):
        raise ValidationError("closure export paths contain an unsafe component")
    return path.as_posix()


def forbidden_keys(value: Any, *, _path: str = "$") -> tuple[str, ...]:
    """Find prohibited metadata keys recursively, returning stable locations."""

    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key)
            lowered = name.casefold()
            if lowered in PROGRAM_RELEASE_CLOSURE_FORBIDDEN_KEYS or any(
                token in lowered for token in PROGRAM_RELEASE_CLOSURE_PRIVATE_KEY_TOKENS
            ):
                found.append(f"{_path}.{name}")
            found.extend(forbidden_keys(child, _path=f"{_path}.{name}"))
    elif isinstance(value, (list, tuple, set)):
        for index, child in enumerate(value):
            found.extend(forbidden_keys(child, _path=f"{_path}[{index}]"))
    return tuple(sorted(set(found)))


def canonical_payload(value: Any) -> bytes:
    """Encode a JSON projection with a terminal newline for portable files."""

    return (canonical_json(jsonable(value)) + "\n").encode("utf-8")


def csv_payload(rows: Iterable[Mapping[str, Any]]) -> bytes:
    """Encode rows with deterministic columns and JSON values for nested cells."""

    materialized = [dict(jsonable(row)) for row in rows]
    fields = sorted({key for row in materialized for key in row}) or ["resource"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in materialized:
        writer.writerow(
            {
                key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                if isinstance(value, (dict, list, tuple))
                else value
                for key, value in row.items()
            }
        )
    return output.getvalue().encode("utf-8")


def markdown_payload(title: str, rows: Iterable[Mapping[str, Any]]) -> bytes:
    """Encode a compact, public aggregate Markdown table."""

    materialized = [dict(jsonable(row)) for row in rows]
    fields = sorted({key for row in materialized for key in row}) or ["resource"]
    lines = [
        f"# {title}",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in materialized:
        values = []
        for field in fields:
            value = row.get(field, "")
            text = (
                json.dumps(value, ensure_ascii=False, sort_keys=True)
                if isinstance(value, (dict, list, tuple))
                else str(value)
            )
            values.append(text.replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return ("\n".join(lines) + "\n").encode("utf-8")


def artifact_address(payload: bytes) -> str:
    return content_hash(
        {"bytes": payload.decode("utf-8")}, prefix="program-release-closure-artifact"
    )


def source_rows(bundle: Any, artifact_id: str) -> Any:
    """Decode one JSON/CSV payload from the existing offline bundle."""

    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        raise ValidationError(f"source artifact {artifact_id!r} is missing its payload")
    if artifact.media_type == "application/json":
        try:
            return json.loads(artifact.payload)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"source artifact {artifact_id!r} is invalid JSON") from exc
    return list(csv.DictReader(io.StringIO(artifact.payload)))


def source_artifact(bundle: Any, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None:
        raise ValidationError(f"source artifact {artifact_id!r} is not present")
    return artifact


def source_bundle_manifest(bundle: Any) -> dict[str, Any]:
    return dict(bundle.manifest_dict(include_payloads=False))


def source_report(bundle: Any) -> Mapping[str, Any]:
    value = source_rows(bundle, "report")
    if not isinstance(value, Mapping):
        raise ValidationError("source report must be an object")
    return value


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).casefold() in {"true", "1", "yes", "accepted", "published", "pass", "ready"}


def rows_by_key(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key, "")): dict(row) for row in rows if row.get(key) is not None}


def content_addressed(body: Any, prefix: str) -> str:
    return content_hash(jsonable(body), prefix=prefix)


def public_manifest(bundle: Any) -> dict[str, Any]:
    """Create a public-only source manifest for diagnostics and export."""

    value = source_bundle_manifest(bundle)
    value.pop("payload", None)
    return jsonable(value)


__all__ = [
    name
    for name in globals()
    if name.startswith("PROGRAM_RELEASE")
    or name
    in {
        "safe_component",
        "safe_relative_path",
        "forbidden_keys",
        "canonical_payload",
        "csv_payload",
        "markdown_payload",
        "artifact_address",
        "source_rows",
        "source_artifact",
        "source_bundle_manifest",
        "source_report",
        "as_int",
        "as_bool",
        "rows_by_key",
        "content_addressed",
        "public_manifest",
    }
]
