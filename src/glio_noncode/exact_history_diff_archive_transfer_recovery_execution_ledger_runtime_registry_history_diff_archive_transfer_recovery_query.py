"""Bounded public queries over exact archive transfer recovery plans."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery as recovery_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = recovery_model.VERSION + "-query-v1"
BOUNDARY = recovery_model.BOUNDARY + "_query"
QUERY_PREFIX = recovery_model.RECOVERY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
MAX_LIMIT = 256
MAX_QUERY_ITEMS = 2048
RESOURCES = ("summary", "actions", "addresses", "bounds", "received", "missing", "state", "decisions", "latest")
ROW_FIELDS = ("ordinal", "resource", "key", "value", "address", "row_address")
QUERY_FIELDS = ("version", "boundary", "query_id", "recovery_id", "transfer_id", "recovery_address", "transfer_address", "archive_address", "resources", "key", "text", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if not value:
        return value
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or value.startswith(("/", "\\")) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryRow:
    """One addressed public recovery-query row."""

    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, key: str, value: Any, address: str, row_address: str) -> None:
        self.ordinal = _count(ordinal, "recovery query row ordinal", MAX_QUERY_ITEMS)
        self.resource = _label(resource, "recovery query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("recovery query row resource is unsupported")
        self.key = _label(key, "recovery query row key", required=False)
        self.value = value
        self.address = _address(address, "recovery query row address")
        self.row_address = _address(row_address, "recovery query row content address", ROW_PREFIX, allow_pending=True)
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("recovery query row crosses the public boundary")
        if not self.row_address.startswith("pending:") and not self.row_address.endswith(":pending") and address_row(self) != self.row_address:
            raise ValidationError("recovery query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "recovery query row")
        _strict(value, set(cls.FIELDS), "recovery query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryRow):
        raise ValidationError("recovery query row address requires a typed row")
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQuery:
    """A deterministic, paginated recovery projection."""

    FIELDS = QUERY_FIELDS

    def __init__(self, version: str, boundary: str, query_id: str, recovery_id: str, transfer_id: str, recovery_address: str, transfer_address: str, archive_address: str, resources: Sequence[str], key: str, text: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryRow], content_address: str) -> None:
        self.version = _text(version, "recovery query version")
        self.boundary = _text(boundary, "recovery query boundary")
        self.query_id = _label(query_id, "recovery query ID")
        self.recovery_id = _label(recovery_id, "recovery query recovery ID")
        self.transfer_id = _label(transfer_id, "recovery query transfer ID")
        self.recovery_address = _address(recovery_address, "recovery query recovery address", recovery_model.RECOVERY_PREFIX)
        self.transfer_address = _address(transfer_address, "recovery query transfer address", recovery_model.transfer_model.TRANSFER_PREFIX)
        self.archive_address = _address(archive_address, "recovery query archive address", recovery_model.transfer_model.archive_model.ARCHIVE_PREFIX)
        selected = tuple(_label(item, "recovery query resource") for item in _sequence(resources, "recovery query resources", len(RESOURCES)))
        if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected) or selected != tuple(item for item in RESOURCES if item in selected):
            raise ValidationError("recovery query resources must preserve contract order")
        self.resources = selected
        self.key = _label(key, "recovery query key", required=False)
        self.text = _text(text, "recovery query text", 2048, required=False)
        self.offset = _count(offset, "recovery query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "recovery query limit", MAX_LIMIT)
        if self.limit < 1:
            raise ValidationError("recovery query limit must be positive")
        self.total_count = _count(total_count, "recovery query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "recovery query returned count", MAX_LIMIT)
        if not isinstance(truncated, bool):
            raise ValidationError("recovery query truncated must be boolean")
        self.truncated = truncated
        self.rows = tuple(row if isinstance(row, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryRow) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryRow.from_mapping(row) for row in _sequence(rows, "recovery query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "recovery query content address", QUERY_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.truncated != (self.offset + self.returned_count < self.total_count) or tuple(row.ordinal for row in self.rows) != tuple(range(self.offset, self.offset + self.returned_count)):
            raise ValidationError("recovery query does not replay its page")
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("recovery query crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("recovery query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "query_id": self.query_id, "recovery_id": self.recovery_id, "transfer_id": self.transfer_id, "recovery_address": self.recovery_address, "transfer_address": self.transfer_address, "archive_address": self.archive_address, "resources": self.resources, "key": self.key, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [row.to_dict() for row in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "recovery query")
        _strict(value, set(cls.FIELDS), "recovery query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQuery):
        raise ValidationError("recovery query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, key: str, value: Any, address: str):
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryRow(ordinal, resource, key, value, address, "pending:recovery-query-row")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryRow(ordinal, resource, key, value, address, address_row(provisional))


def _all_rows(value: recovery_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecovery):
    rows = []
    for key, item in value.summary().items():
        rows.append(_row("summary", len(rows), key, item, value.content_address))
    for action in value.actions:
        rows.append(_row("actions", len(rows), str(action.index), action.to_dict(), action.action_address))
    for key, item in (("recovery", value.content_address), ("transfer", value.transfer_address), ("archive", value.archive_address)):
        rows.append(_row("addresses", len(rows), key, item, item))
    for key, item in (("archive-size", value.archive_size), ("chunk-count", value.chunk_count), ("max-actions", recovery_model.MAX_ACTIONS), ("received-bytes", value.received_bytes), ("remaining-bytes", value.remaining_bytes)):
        rows.append(_row("bounds", len(rows), key, item, value.content_address))
    for index in value.received_indices:
        rows.append(_row("received", len(rows), str(index), index, value.content_address))
    for action in value.actions:
        rows.append(_row("missing", len(rows), str(action.index), action.to_dict(), action.action_address))
    for key, item in (("state", value.state), ("checkpointed", value.checkpointed), ("safe-to-resume", value.safe_to_resume), ("next-index", value.next_index)):
        rows.append(_row("state", len(rows), key, item, value.content_address))
    for key, item in (("decision", value.decision), ("action-count", value.action_count), ("complete", value.state == "complete")):
        rows.append(_row("decisions", len(rows), key, item, value.content_address))
    latest = value.actions[-1] if value.actions else None
    for key, item in (("index", latest.index if latest else value.next_index), ("action", latest.action_address if latest else ""), ("state", value.state)):
        rows.append(_row("latest", len(rows), key, item, latest.action_address if latest else value.content_address))
    return tuple(rows)


def query_recovery(value: recovery_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecovery, *, query_id: str | None = None, resources: Sequence[str] = RESOURCES, key: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT):
    if not isinstance(value, recovery_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecovery):
        raise ValidationError("recovery query requires a typed recovery")
    value = recovery_model.recovery_from_mapping(value.to_dict())
    selected = tuple(resources)
    rows = [row for row in _all_rows(value) if row.resource in selected and (not key or row.key == key) and (not text or text.lower() in canonical_json(row.to_dict()).lower())]
    page = tuple(_row(row.resource, index, row.key, row.value, row.address) for index, row in enumerate(rows[offset:offset + limit], start=offset))
    body = {"version": VERSION, "boundary": BOUNDARY, "query_id": DEFAULT_QUERY_ID if query_id is None else _label(query_id, "query ID"), "recovery_id": value.recovery_id, "transfer_id": value.transfer_id, "recovery_address": value.content_address, "transfer_address": value.transfer_address, "archive_address": value.archive_address, "resources": selected, "key": key, "text": text, "offset": offset, "limit": limit, "total_count": len(rows), "returned_count": len(page), "truncated": offset + len(page) < len(rows), "rows": page}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQuery(**body, content_address="pending:recovery-query")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQuery(**body, content_address=address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQuery.from_mapping(value)


def verify_query(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQuery):
        raise ValidationError("recovery query verification requires a typed query")
    return query_from_mapping(value.to_dict())


def query_json(value) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value) -> str:
    value = verify_query(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow(row.to_dict() | {"value": canonical_json(row.value)})
    return stream.getvalue()


def render_query_markdown(value) -> str:
    value = verify_query(value)
    lines = ["# Execution-ledger history-diff archive transfer recovery query", "", f"- Recovery: `{value.recovery_id}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}/{value.total_count}`", "", "| ordinal | resource | key | value |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | {row.resource} | {row.key} | `{canonical_json(row.value)}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer recovery query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 0}, "resource": {"enum": list(RESOURCES)}, "key": {"type": "string"}, "value": {}, "address": {"type": "string"}, "row_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer recovery query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "query_id": {"type": "string"}, "recovery_id": {"type": "string"}, "transfer_id": {"type": "string"}, "recovery_address": {"type": "string", "pattern": "^" + recovery_model.RECOVERY_PREFIX + ":"}, "transfer_address": {"type": "string", "pattern": "^" + recovery_model.transfer_model.TRANSFER_PREFIX + ":"}, "archive_address": {"type": "string", "pattern": "^" + recovery_model.transfer_model.archive_model.ARCHIVE_PREFIX + ":"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "key": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_LIMIT}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": RESOURCES, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS, "operations": ["query_recovery", "query_from_mapping", "verify_query", "query_json", "query_csv", "render_query_markdown"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "DEFAULT_QUERY_ID", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQuery", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_recovery", "query_schema", "render_query_markdown", "row_schema", "verify_query"]
