"""Bounded, deterministic inspection queries over registry histories.

The registry-history boundary records an ordered sequence of verified
snapshots and adjacent transitions. This companion boundary makes that
timeline operationally inspectable without exposing source paths, mutable
process state, or private metadata. Query requests and result pages are
typed, bounded, content-addressed, and safe to replay from public JSON.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-query-v1"
BOUNDARY = history_model.BOUNDARY + "_query"
QUERY_PREFIX = history_model.HISTORY_PREFIX + "-query"
DEFAULT_LIMIT = 50
MAX_LIMIT = 256
MAX_QUERY_ITEMS = 2048
MAX_TEXT = 512
RESOURCES = ("summary", "snapshots", "transitions", "state-changes", "accepted", "release-ready")
STATE_VALUES = tuple(dict.fromkeys((*tuple(item.value for item in registry_model.RegistryState), *history_model.STATES)))


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return history_model._public(value)


class RegistryHistoryQuery:
    """A bounded filter over one ordered registry history."""

    RESOURCES = RESOURCES

    def __init__(self, resource: str = "summary", state: str | None = None, accepted: bool | None = None, release_ready: bool | None = None, ordinal: int | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "registry history query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("registry history query resource is not supported")
        self.state = None if state is None else _text(state, "registry history query state", 32)
        if self.state is not None and self.state not in STATE_VALUES:
            raise ValidationError("registry history query state is not supported")
        self.accepted = None if accepted is None else _bool(accepted, "registry history query accepted")
        self.release_ready = None if release_ready is None else _bool(release_ready, "registry history query release-ready")
        self.ordinal = None if ordinal is None else _count(ordinal, "registry history query ordinal", history_model.MAX_SNAPSHOTS, positive=True)
        self.text = None if text is None else _text(text, "registry history query text", MAX_TEXT)
        self.offset = _count(offset, "registry history query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "registry history query limit", MAX_LIMIT, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "ordinal": self.ordinal, "text": self.text, "offset": self.offset, "limit": self.limit}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryQuery:
        value = _mapping(value, "registry history query")
        _strict(value, {"resource", "state", "accepted", "release_ready", "ordinal", "text", "offset", "limit"}, "registry history query")
        return cls(**value)


class RegistryHistoryQueryResult:
    """A content-addressed page of public history inspection records."""

    def __init__(self, history_address: str, query: RegistryHistoryQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.history_address = history_address
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(dict(record) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.history_address, "registry history query history address", history_model.HISTORY_PREFIX)
        if not isinstance(self.query, RegistryHistoryQuery):
            raise ValidationError("registry history query result query must be typed")
        _count(self.total_count, "registry history query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "registry history query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("registry history query result window is invalid")
        if any(not isinstance(record, Mapping) or not _public(record) for record in self.records):
            raise ValidationError("registry history query result contains a private record")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry history query content address")
        else:
            _address(self.content_address, "registry history query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("registry history query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryQueryResult:
        value = _mapping(value, "registry history query result")
        _strict(value, {"history_address", "query", "total_count", "returned_count", "records", "content_address"}, "registry history query result")
        query = RegistryHistoryQuery.from_mapping(_mapping(value["query"], "registry history query"))
        records = tuple(_mapping(record, "registry history query record") for record in _sequence(value["records"], "registry history query records", MAX_QUERY_ITEMS))
        result = cls(value["history_address"], query, value["total_count"], records, value["content_address"])
        if result.returned_count != value["returned_count"]:
            raise ValidationError("registry history query returned count is not conserved")
        return result


def address_query(value: RegistryHistoryQueryResult) -> str:
    if not isinstance(value, RegistryHistoryQueryResult):
        raise ValidationError("registry history query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _matches(record: Mapping[str, Any], query: RegistryHistoryQuery) -> bool:
    if query.state is not None and record.get("state") != query.state:
        return False
    if query.accepted is not None and record.get("accepted") is not query.accepted:
        return False
    if query.release_ready is not None and record.get("release_ready") is not query.release_ready:
        return False
    if query.ordinal is not None and record.get("ordinal") != query.ordinal:
        return False
    return query.text is None or query.text.casefold() in canonical_json(record).casefold()


def _records(value: history_model.RegistryHistory, query: RegistryHistoryQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        candidates: tuple[Mapping[str, Any], ...] = (value.summary(),)
    elif query.resource == "snapshots":
        candidates = tuple(snapshot.to_dict() for snapshot in value.snapshots)
    elif query.resource == "transitions":
        candidates = tuple(transition.to_dict() for transition in value.transitions)
    elif query.resource == "state-changes":
        candidates = tuple(transition.to_dict() for transition in value.transitions if transition.state != "unchanged")
    elif query.resource == "accepted":
        candidates = tuple(snapshot.to_dict() for snapshot in value.snapshots if snapshot.accepted)
    else:
        candidates = tuple(snapshot.to_dict() for snapshot in value.snapshots if snapshot.release_ready)
    return tuple(record for record in candidates if _matches(record, query))


def query_history(value: history_model.RegistryHistory, query: RegistryHistoryQuery | None = None, *, resource: str = "summary", state: str | None = None, accepted: bool | None = None, release_ready: bool | None = None, ordinal: int | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryQueryResult:
    history_model.verify_history(value)
    if query is not None and any(argument != default for argument, default in ((resource, "summary"), (state, None), (accepted, None), (release_ready, None), (ordinal, None), (text, None), (offset, 0), (limit, DEFAULT_LIMIT))):
        raise ValidationError("registry history query accepts either a query object or keyword filters")
    selected = query or RegistryHistoryQuery(resource=resource, state=state, accepted=accepted, release_ready=release_ready, ordinal=ordinal, text=text, offset=offset, limit=limit)
    records = _records(value, selected)
    total_count = len(records)
    window = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryHistoryQueryResult(value.content_address, selected, total_count, window, "pending:query")
    return RegistryHistoryQueryResult(value.content_address, selected, total_count, window, address_query(provisional))


def verify_query(value: RegistryHistoryQueryResult) -> RegistryHistoryQueryResult:
    if not isinstance(value, RegistryHistoryQueryResult):
        raise ValidationError("registry history query verification requires a typed result")
    value._validate()
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryQueryResult:
    return RegistryHistoryQueryResult.from_mapping(value)


def query_json(value: RegistryHistoryQueryResult) -> str:
    verify_query(value)
    return canonical_json(value.to_dict())


def query_csv(value: RegistryHistoryQueryResult) -> str:
    verify_query(value)
    rows = list(value.records)
    fields = sorted({str(key) for record in rows for key in record}) or ["content_address"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in rows:
        writer.writerow({field: canonical_json(record[field]) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryQueryResult) -> str:
    verify_query(value)
    lines = ["# Assurance History Observatory Archive Registry History Query", "", f"- Resource: `{value.query.resource}`", f"- State filter: `{value.query.state}`", f"- Accepted filter: `{value.query.accepted}`", f"- Release-ready filter: `{value.query.release_ready}`", f"- Ordinal filter: `{value.query.ordinal}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- History: `{value.history_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records:
        fields = sorted({str(key) for record in value.records for key in record})
        lines.extend(["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"])
        lines.extend("| " + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields) + " |" for record in value.records)
    else:
        lines.append("No matching records.")
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    fields = {
        "resource": {"type": "string", "enum": list(RESOURCES)},
        "state": {"type": ["string", "null"], "enum": [*STATE_VALUES, None]},
        "accepted": {"type": ["boolean", "null"]},
        "release_ready": {"type": ["boolean", "null"]},
        "ordinal": {"type": ["integer", "null"], "minimum": 1, "maximum": history_model.MAX_SNAPSHOTS},
        "text": {"type": ["string", "null"], "maxLength": MAX_TEXT},
        "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS},
        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
    }
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["history_address", "query", "total_count", "returned_count", "records", "content_address"], "properties": {"history_address": {"type": "string", "pattern": "^" + history_model.HISTORY_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATE_VALUES, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS, "max_snapshots": history_model.MAX_SNAPSHOTS}, "features": ("bounded history summary inspection", "snapshot and transition resources", "state-change filtering", "acceptance and release-readiness filtering", "ordinal and case-insensitive public text filtering", "deterministic pagination", "content-addressed result replay", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MAX_QUERY_ITEMS",
    "QUERY_PREFIX",
    "RESOURCES",
    "STATE_VALUES",
    "VERSION",
    "RegistryHistoryQuery",
    "RegistryHistoryQueryResult",
    "address_query",
    "capabilities",
    "query_csv",
    "query_history",
    "query_json",
    "query_result_from_mapping",
    "query_result_schema",
    "query_schema",
    "render_query_markdown",
    "verify_query",
]
