"""Bounded path-free queries over exact execution-ledger runtime registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = registry_model.VERSION + "-query-v1"
BOUNDARY = registry_model.BOUNDARY + "_query"
QUERY_PREFIX = registry_model.REGISTRY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
MAX_LIMIT = 256
MAX_QUERY_ITEMS = registry_model.MAX_ENTRIES * 6 + 64
RESOURCES = ("summary", "entries", "states", "acceptance", "runtimes", "addresses", "bounds", "latest")
ROW_FIELDS = ("resource", "ordinal", "key", "runtime_id", "runtime_address", "ledger_id", "state", "accepted", "value", "address", "row_address")
QUERY_FIELDS = ("query_id", "version", "boundary", "registry_address", "registry_id", "resources", "state_filter", "key_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong public address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
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


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow:
    """One stable row in a bounded registry query."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, key: str, runtime_id: str, runtime_address: str, ledger_id: str, state: str, accepted: bool, value: Any, address: str, row_address: str) -> None:
        if resource not in RESOURCES:
            raise ValidationError("ledger runtime registry query row resource is unsupported")
        self.resource = resource
        self.ordinal = _count(ordinal, "ledger runtime registry query row ordinal", MAX_QUERY_ITEMS)
        self.key = _text(key, "ledger runtime registry query row key", 512, required=True)
        self.runtime_id = _text(runtime_id, "ledger runtime registry query row runtime ID", 512)
        self.runtime_address = _text(runtime_address, "ledger runtime registry query row runtime address", 4096)
        self.ledger_id = _text(ledger_id, "ledger runtime registry query row ledger ID", 512)
        self.state = _text(state, "ledger runtime registry query row state", 128, required=True)
        self.accepted = _bool(accepted, "ledger runtime registry query row acceptance")
        self.value = value
        self.address = _address(address, "ledger runtime registry query row address")
        self.row_address = _address(row_address, "ledger runtime registry query row content address", ROW_PREFIX, allow_pending=True)
        if not self.row_address.startswith("pending:") and not self.row_address.endswith(":pending") and address_row(self) != self.row_address:
            raise ValidationError("ledger runtime registry query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow":
        value = _mapping(value, "ledger runtime registry query row")
        _strict(value, set(cls.FIELDS), "ledger runtime registry query row")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery:
    """A deterministic, bounded, value-free registry query result."""

    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, version: str, boundary: str, registry_address: str, registry_id: str, resources: Sequence[str], state_filter: str, key_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "ledger runtime registry query ID")
        self.version = _text(version, "ledger runtime registry query version", 2048)
        self.boundary = _text(boundary, "ledger runtime registry query boundary", 1024)
        self.registry_address = _address(registry_address, "ledger runtime registry query registry address", registry_model.REGISTRY_PREFIX)
        self.registry_id = _label(registry_id, "ledger runtime registry query registry ID")
        self.resources = tuple(resources)
        if not self.resources or tuple(item for item in RESOURCES if item in self.resources) != self.resources or any(item not in RESOURCES for item in self.resources):
            raise ValidationError("ledger runtime registry query resources are not canonical")
        self.state_filter = _text(state_filter, "ledger runtime registry query state filter", 128)
        self.key_filter = _text(key_filter, "ledger runtime registry query key filter", 512)
        self.text_filter = _text(text_filter, "ledger runtime registry query text filter", 4096)
        self.offset = _count(offset, "ledger runtime registry query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "ledger runtime registry query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "ledger runtime registry query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "ledger runtime registry query returned count", MAX_LIMIT)
        self.truncated = _bool(truncated, "ledger runtime registry query truncation")
        self.rows = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow.from_mapping(item) for item in _sequence(rows, "ledger runtime registry query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "ledger runtime registry query address", QUERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger runtime registry query version or boundary is not current")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or tuple(item.ordinal for item in self.rows) != tuple(range(self.returned_count)):
            raise ValidationError("ledger runtime registry query page does not replay")
        if self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("ledger runtime registry query truncation does not replay")
        if not self.content_address.startswith("pending:") and address_query(self) != self.content_address:
            raise ValidationError("ledger runtime registry query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "version": self.version, "boundary": self.boundary, "registry_address": self.registry_address, "registry_id": self.registry_id, "resources": self.resources, "state_filter": self.state_filter, "key_filter": self.key_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery":
        value = _mapping(value, "ledger runtime registry query")
        _strict(value, set(cls.FIELDS), "ledger runtime registry query")
        return cls(value["query_id"], value["version"], value["boundary"], value["registry_address"], value["registry_id"], tuple(_sequence(value["resources"], "ledger runtime registry query resources", len(RESOURCES))), value["state_filter"], value["key_filter"], value["text_filter"], value["offset"], value["limit"], value["total_count"], value["returned_count"], value["truncated"], tuple(value["rows"]), value["content_address"])


def address_row(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow):
        raise ValidationError("ledger runtime registry query row address requires a typed row")
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


def address_query(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery):
        raise ValidationError("ledger runtime registry query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, key: str, value: Any, *, runtime_id: str = "", runtime_address: str = "", ledger_id: str = "", state: str, accepted: bool, address: str) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow:
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow(resource, ordinal, key, runtime_id, runtime_address, ledger_id, state, accepted, value, address, "pending:ledger-runtime-registry-query-row")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow(resource, ordinal, key, runtime_id, runtime_address, ledger_id, state, accepted, value, address, address_row(provisional))


def _all_rows(value: registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry) -> tuple[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow, ...]:
    rows: list[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow] = []
    mapping = value.to_dict()
    for field in ("registry_id", "version", "boundary", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted", "content_address"):
        rows.append(_row("summary", len(rows), field, mapping[field], state=value.state, accepted=value.accepted, address=value.content_address))
    for item in value.entries:
        rows.append(_row("entries", len(rows), item.runtime_id, item.to_dict(), runtime_id=item.runtime_id, runtime_address=item.runtime_address, ledger_id=item.ledger_id, state=item.state, accepted=item.accepted, address=item.content_address))
    for key, item in (("empty", value.entry_count == 0), ("ready", value.ready_count), ("blocked", value.blocked_count)):
        rows.append(_row("states", len(rows), key, item, state=value.state, accepted=value.accepted, address=value.summary.content_address))
    for key, item in (("accepted", value.accepted), ("accepted-count", value.accepted_count), ("entry-count", value.entry_count)):
        rows.append(_row("acceptance", len(rows), key, item, state=value.state, accepted=value.accepted, address=value.summary.content_address))
    for item in value.entries:
        rows.append(_row("runtimes", len(rows), item.runtime_id, {"runtime_address": item.runtime_address, "ledger_id": item.ledger_id}, runtime_id=item.runtime_id, runtime_address=item.runtime_address, ledger_id=item.ledger_id, state=item.state, accepted=item.accepted, address=item.runtime_address))
    for key, item in (("runtime", value.content_address), ("entries", value.entries[0].content_address if value.entries else value.content_address), ("summary", value.summary.content_address), ("manifest", value.manifest.manifest_address)):
        rows.append(_row("addresses", len(rows), key, item, state=value.state, accepted=value.accepted, address=value.content_address))
    for key, item in (("entry-count", value.entry_count), ("max-entries", registry_model.MAX_ENTRIES), ("artifact-count", len(registry_model.ARTIFACT_FILES))):
        rows.append(_row("bounds", len(rows), key, item, state=value.state, accepted=value.accepted, address=value.summary.content_address))
    latest = value.entries[-1] if value.entries else None
    for key, item in (("runtime-id", latest.runtime_id if latest else ""), ("state", latest.state if latest else value.state), ("accepted", latest.accepted if latest else value.accepted), ("address", latest.runtime_address if latest else value.content_address)):
        rows.append(_row("latest", len(rows), key, item, runtime_id=latest.runtime_id if latest else "", runtime_address=latest.runtime_address if latest else "", ledger_id=latest.ledger_id if latest else "", state=value.state, accepted=value.accepted, address=latest.content_address if latest else value.content_address))
    return tuple(rows)


def _matches(row: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow, *, state: str, key: str, text: str) -> bool:
    if state and row.state != state:
        return False
    if key and row.key != key:
        return False
    if text and text.casefold() not in canonical_json(row.to_dict()).casefold():
        return False
    return True


def query_registry(value: registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry, *, query_id: str = "runtime-registry-history-diff-archive-transfer-recovery-execution-ledger-runtime-registry-query", resources: Sequence[str] | None = None, state: str = "", key: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery:
    if not isinstance(value, registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry):
        raise ValidationError("ledger runtime registry query requires a typed registry")
    value = registry_model.verify_registry(value)
    selected = tuple(resource for resource in RESOURCES if resources is None or resource in tuple(resources))
    if not selected:
        raise ValidationError("ledger runtime registry query requires at least one resource")
    offset = _count(offset, "ledger runtime registry query offset", MAX_QUERY_ITEMS)
    limit = _count(limit, "ledger runtime registry query limit", MAX_LIMIT, lower=1)
    rows = tuple(item for item in _all_rows(value) if item.resource in selected and _matches(item, state=state, key=key, text=text))
    page = rows[offset:offset + limit]
    page_rows = tuple(_row(item.resource, ordinal, item.key, item.value, runtime_id=item.runtime_id, runtime_address=item.runtime_address, ledger_id=item.ledger_id, state=item.state, accepted=item.accepted, address=item.address) for ordinal, item in enumerate(page))
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery(query_id, VERSION, BOUNDARY, value.content_address, value.registry_id, selected, state, key, text, offset, limit, len(rows), len(page_rows), offset + len(page_rows) < len(rows), page_rows, "pending:ledger-runtime-registry-query")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery(query_id, VERSION, BOUNDARY, value.content_address, value.registry_id, selected, state, key, text, offset, limit, len(rows), len(page_rows), offset + len(page_rows) < len(rows), page_rows, address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery.from_mapping(value)


def query_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_query_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Exact execution ledger runtime registry query", "", f"- Registry: `{value.registry_id}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}/{value.total_count}`", f"- Address: `{value.content_address}`", "", "| resource | ordinal | key | runtime | state | accepted | address |", "| --- | ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.resource} | {item.ordinal} | `{item.key}` | `{item.runtime_id}` | `{item.state}` | `{item.accepted}` | `{item.address}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 0}, "key": {"type": "string"}, "runtime_id": {"type": "string"}, "runtime_address": {"type": "string"}, "ledger_id": {"type": "string"}, "state": {"type": "string"}, "accepted": {"type": "boolean"}, "value": {}, "address": {"type": "string"}, "row_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "registry_address": {"type": "string", "pattern": "^" + registry_model.REGISTRY_PREFIX + ":"}, "registry_id": {"type": "string"}, "resources": {"type": "array", "items": {"type": "string", "enum": list(RESOURCES)}}, "state_filter": {"type": "string"}, "key_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": RESOURCES, "max_query_items": MAX_QUERY_ITEMS, "max_limit": MAX_LIMIT, "features": ("summary entry state acceptance runtime address bounds and latest resources", "state key and text filters", "deterministic pagination", "canonical JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQuery", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryQueryRow", "VERSION", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_registry", "query_schema", "render_query_markdown", "row_schema"]
