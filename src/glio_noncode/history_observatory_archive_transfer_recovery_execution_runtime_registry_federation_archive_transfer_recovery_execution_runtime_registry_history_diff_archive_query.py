"""Bounded public queries over federation history-diff archives."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff as diff_model
from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = archive_model.VERSION + "-query-v1"
BOUNDARY = archive_model.BOUNDARY + "_query"
QUERY_PREFIX = archive_model.ARCHIVE_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = "comparison-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-history-diff-archive-query"
RESOURCES = ("summary", "manifest", "artifacts", "diff", "items", "changes", "addresses", "bounds")
CHANGES = diff_model.CHANGES
MAX_LIMIT = 256
MAX_OFFSET = 1_000_000
MAX_TEXT = 4096
MAX_ROWS = 2048
ROW_FIELDS = ("ordinal", "resource", "key", "value", "address", "change", "row_address")
QUERY_FIELDS = ("query_id", "archive_id", "archive_address", "resources", "key_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 1024, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192, required=required)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if value and (":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} must be a public content address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return archive_model._public(value)


def _json_value(value: Any, field: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{field} must be JSON-compatible") from error
    if len(canonical_bytes(normalized)) > 32768 or not _public(normalized):
        raise ValidationError(f"{field} crosses its bounded public contract")
    return normalized


class RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, key: str, value: Any, address: str, change: str, row_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff archive query row ordinal", MAX_ROWS, positive=True)
        self.resource = _label(resource, "history diff archive query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("history diff archive query row resource is unsupported")
        self.key = _text(key, "history diff archive query row key", 2048, required=True)
        self.value = _json_value(value, "history diff archive query row value")
        self.address = _address(address, "history diff archive query row address", required=False)
        self.change = _text(change, "history diff archive query row change", 32, required=False)
        if self.change and self.change not in CHANGES:
            raise ValidationError("history diff archive query row change is unsupported")
        self.row_address = _address(row_address, "history diff archive query row address", ROW_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("history diff archive query row crosses the public boundary")
        if not self.row_address.startswith("pending:") and not self.row_address.endswith(":pending") and address_row(self) != self.row_address:
            raise ValidationError("history diff archive query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow:
        value = _mapping(value, "history diff archive query row")
        _strict(value, set(cls.FIELDS), "history diff archive query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow):
        raise ValidationError("history diff archive query row address requires a typed row")
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


def _row(resource: str, key: str, value: Any, address: str, change: str, ordinal: int) -> RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow:
    provisional = RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow(ordinal, resource, key, value, address, change, ROW_PREFIX + ":pending")
    return RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow(provisional.ordinal, provisional.resource, provisional.key, provisional.value, provisional.address, provisional.change, address_row(provisional))


def _all_rows(value: archive_model.RecoveryExecutionRuntimeRegistryHistoryDiffArchive) -> tuple[RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow, ...]:
    value = archive_model.verify_archive(value)
    diff = value.diff
    if diff is None:
        raise ValidationError("history diff archive query requires a decoded nested diff")
    manifest = archive_model.manifest_document(value)
    rows: list[RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow] = []

    def add_mapping(resource: str, mapping: Mapping[str, Any], address: str, change: str = "") -> None:
        for key, item in mapping.items():
            rows.append(_row(resource, str(key), item, address, change, len(rows) + 1))

    summary = {"archive": value.summary(), "diff": diff.summary.to_dict()}
    add_mapping("summary", summary, value.content_address)
    add_mapping("manifest", manifest, manifest["manifest_address"])
    for artifact in value.artifacts:
        rows.append(_row("artifacts", f"{artifact.index}:{artifact.name}", artifact.to_dict(), artifact.hash, "", len(rows) + 1))
    add_mapping("diff", diff.compact(), diff.content_address)
    for item in diff.items:
        rows.append(_row("items", item.identity, item.to_dict(), item.content_address, item.change, len(rows) + 1))
    counts = {change: getattr(diff, change + "_count") for change in CHANGES}
    add_mapping("changes", counts, diff.content_address)
    addresses = {"archive": value.content_address, "manifest": manifest["manifest_address"], "diff": diff.content_address, "items": diff_model.address_items(diff.items), "summary": diff.summary.content_address}
    add_mapping("addresses", addresses, value.content_address)
    bounds = {"artifact_count": value.artifact_count, "archive_size": value.archive_size, "max_archive_bytes": archive_model.MAX_ARCHIVE_BYTES, "max_member_bytes": archive_model.MAX_MEMBER_BYTES, "item_count": diff.item_count, "max_query_rows": MAX_ROWS}
    add_mapping("bounds", bounds, value.content_address)
    if len(rows) > MAX_ROWS:
        raise ValidationError("history diff archive query row bound exceeded")
    return tuple(rows)


class RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, archive_id: str, archive_address: str, resources: Sequence[str], key_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "history diff archive query ID")
        self.archive_id = _label(archive_id, "history diff archive query archive ID")
        self.archive_address = _address(archive_address, "history diff archive query archive address", archive_model.ARCHIVE_PREFIX)
        self.resources = tuple(_label(item, "history diff archive query resource") for item in _sequence(resources, "history diff archive query resources", len(RESOURCES)))
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources):
            raise ValidationError("history diff archive query resources are unsupported or duplicated")
        self.key_filter = _text(key_filter, "history diff archive query key filter")
        self.text_filter = _text(text_filter, "history diff archive query text filter")
        self.offset = _count(offset, "history diff archive query offset", MAX_OFFSET)
        self.limit = _count(limit, "history diff archive query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "history diff archive query total count", MAX_ROWS)
        self.returned_count = _count(returned_count, "history diff archive query returned count", MAX_LIMIT)
        self.truncated = _bool(truncated, "history diff archive query truncation")
        self.rows = tuple(row if isinstance(row, RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow) else RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow.from_mapping(row) for row in _sequence(rows, "history diff archive query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "history diff archive query address", QUERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count or self.truncated != self.offset + self.returned_count < self.total_count:
            raise ValidationError("history diff archive query pagination does not replay")
        if tuple(row.ordinal for row in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("history diff archive query row ordinals do not replay")
        if any(row.resource not in self.resources for row in self.rows):
            raise ValidationError("history diff archive query row resource is outside the request")
        if not _public(self.to_dict()):
            raise ValidationError("history diff archive query crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("history diff archive query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "archive_id": self.archive_id, "archive_address": self.archive_address, "resources": self.resources, "key_filter": self.key_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": tuple(row.to_dict() for row in self.rows), "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery:
        value = _mapping(value, "history diff archive query")
        _strict(value, set(cls.FIELDS), "history diff archive query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery):
        raise ValidationError("history diff archive query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _matches(row: RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow, *, resources: tuple[str, ...], key_filter: str, text_filter: str) -> bool:
    if row.resource not in resources:
        return False
    if key_filter and row.key != key_filter:
        return False
    if text_filter and text_filter.casefold() not in canonical_json(row.to_dict()).casefold():
        return False
    return True


def query_archive(value: archive_model.RecoveryExecutionRuntimeRegistryHistoryDiffArchive, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, key: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery:
    value = archive_model.verify_archive(value)
    selected = tuple(resources)
    key = _text(key, "history diff archive query key filter")
    text = _text(text, "history diff archive query text filter")
    offset = _count(offset, "history diff archive query offset", MAX_OFFSET)
    limit = _count(limit, "history diff archive query limit", MAX_LIMIT, positive=True)
    all_rows = _all_rows(value)
    matching = tuple(row for row in all_rows if _matches(row, resources=selected, key_filter=key, text_filter=text))
    page = matching[offset:offset + limit]
    rows = tuple(_row(row.resource, row.key, row.value, row.address, row.change, offset + index + 1) for index, row in enumerate(page))
    body = {"query_id": query_id, "archive_id": value.archive_id, "archive_address": value.content_address, "resources": selected, "key_filter": key, "text_filter": text, "offset": offset, "limit": limit, "total_count": len(matching), "returned_count": len(rows), "truncated": offset + len(rows) < len(matching), "rows": rows, "content_address": QUERY_PREFIX + ":pending"}
    provisional = RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery(**body)
    return RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery:
    return RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery.from_mapping(value)


def query_json(value: RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery) -> str:
    value = query_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    for row in value.rows:
        writer.writerow((row.ordinal, row.resource, row.key, canonical_json(row.value), row.address, row.change, row.row_address))
    return output.getvalue()


def render_query_markdown(value: RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Federation History-Diff Archive Query", "", f"- Query: `{value.query_id}`", f"- Archive: `{value.archive_id}`", f"- Resources: `{', '.join(value.resources)}`", f"- Result: `{value.returned_count}/{value.total_count}`", f"- Truncated: `{value.truncated}`", f"- Address: `{value.content_address}`", "", "| ordinal | resource | key | change | address |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.key}` | `{row.change or '—'}` | `{row.address or '—'}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationRuntimeRegistryHistoryDiffArchiveQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "key": {"type": "string"}, "value": {}, "address": {"type": "string"}, "change": {"enum": ["", *CHANGES]}, "row_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationRuntimeRegistryHistoryDiffArchiveQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "archive_id": {"type": "string"}, "archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "key_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_LIMIT}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": list(RESOURCES), "changes": list(CHANGES), "max_limit": MAX_LIMIT, "max_offset": MAX_OFFSET, "max_rows": MAX_ROWS, "operations": ["query_archive", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "CHANGES", "MAX_LIMIT", "MAX_OFFSET", "MAX_ROWS", "ROW_FIELDS", "QUERY_FIELDS", "RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryRow", "RecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery", "address_row", "address_query", "query_archive", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
