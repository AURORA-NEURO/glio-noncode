"""Bounded query projections for release-evidence bundle diffs.

Diff reports contain two useful kinds of change: semantic transitions in the
bundle projection and byte transitions in its five artifacts.  This module
keeps those planes explicit while providing one deterministic, content-
addressed query result for operators and review automation.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff as diff_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle as bundle_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-query-v1"
BOUNDARY = diff_model.BOUNDARY + "_query"
QUERY_PREFIX = diff_model.DIFF_PREFIX + "-query"
DEFAULT_LIMIT = 50
MAX_LIMIT = 256
MAX_QUERY_ITEMS = len(diff_model.BUNDLE_FIELDS) + diff_model.MAX_ITEMS
MAX_TEXT = 1024
RESOURCES = ("summary", "fields", "files", "changed", "unchanged", "evidence")
ACTIONS = diff_model.ACTIONS


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
    return diff_model._public(value)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _freeze(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


class RegistryHistoryReleaseEvidencePipelineBundleDiffQuery:
    """A bounded filter over one release-evidence bundle diff."""

    RESOURCES = RESOURCES

    def __init__(self, resource: str = "summary", action: str | None = None, name: str | None = None, changed_field: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "release evidence bundle diff query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("release evidence bundle diff query resource is not supported")
        self.action = None if action is None else _text(action, "release evidence bundle diff query action", 32)
        if self.action is not None and self.action not in ACTIONS:
            raise ValidationError("release evidence bundle diff query action is not supported")
        self.name = None if name is None else _text(name, "release evidence bundle diff query file name", 128)
        if self.name is not None and self.name not in bundle_model.FILES:
            raise ValidationError("release evidence bundle diff query file name is not supported")
        self.changed_field = None if changed_field is None else _text(changed_field, "release evidence bundle diff query changed field", 128)
        if self.changed_field is not None and self.changed_field not in (*diff_model.BUNDLE_FIELDS, *diff_model.ITEM_FIELDS):
            raise ValidationError("release evidence bundle diff query changed field is not supported")
        self.text = None if text is None else _text(text, "release evidence bundle diff query text", MAX_TEXT)
        self.offset = _count(offset, "release evidence bundle diff query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "release evidence bundle diff query limit", MAX_LIMIT, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "action": self.action, "name": self.name, "changed_field": self.changed_field, "text": self.text, "offset": self.offset, "limit": self.limit}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineBundleDiffQuery:
        value = _mapping(value, "release evidence bundle diff query")
        _strict(value, {"resource", "action", "name", "changed_field", "text", "offset", "limit"}, "release evidence bundle diff query")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult:
    """A content-addressed page of public bundle-diff records."""

    def __init__(self, diff_address: str, query: RegistryHistoryReleaseEvidencePipelineBundleDiffQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.diff_address = _address(diff_address, "release evidence bundle diff query diff address", diff_model.DIFF_PREFIX)
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(_freeze(dict(record)) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.query, RegistryHistoryReleaseEvidencePipelineBundleDiffQuery):
            raise ValidationError("release evidence bundle diff query result query must be typed")
        _count(self.total_count, "release evidence bundle diff query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "release evidence bundle diff query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("release evidence bundle diff query result window is invalid")
        if any(not isinstance(record, Mapping) or not _public(record) for record in self.records):
            raise ValidationError("release evidence bundle diff query result contains a private record")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence bundle diff query content address")
        else:
            _address(self.content_address, "release evidence bundle diff query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("release evidence bundle diff query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult:
        value = _mapping(value, "release evidence bundle diff query result")
        _strict(value, {"diff_address", "query", "total_count", "returned_count", "records", "content_address"}, "release evidence bundle diff query result")
        query = RegistryHistoryReleaseEvidencePipelineBundleDiffQuery.from_mapping(_mapping(value["query"], "release evidence bundle diff query"))
        records = tuple(_mapping(record, "release evidence bundle diff query record") for record in _sequence(value["records"], "release evidence bundle diff query records", MAX_QUERY_ITEMS))
        result = cls(value["diff_address"], query, value["total_count"], records, value["content_address"])
        if result.returned_count != value["returned_count"]:
            raise ValidationError("release evidence bundle diff query returned count is not conserved")
        return result


def address_query(value: RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult):
        raise ValidationError("release evidence bundle diff query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _projections(value: diff_model.RegistryHistoryReleaseEvidencePipelineBundleDiff) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline = {"pipeline_address": value.baseline_pipeline_address, "pipeline_state": value.baseline_pipeline_state, "pipeline_accepted": value.baseline_pipeline_accepted, "query_addresses": value.baseline_query_addresses, "artifact_count": value.baseline_artifact_count, "manifest_address": value.baseline_manifest_address, "content_address": value.baseline_address}
    candidate = {"pipeline_address": value.candidate_pipeline_address, "pipeline_state": value.candidate_pipeline_state, "pipeline_accepted": value.candidate_pipeline_accepted, "query_addresses": value.candidate_query_addresses, "artifact_count": value.candidate_artifact_count, "manifest_address": value.candidate_manifest_address, "content_address": value.candidate_address}
    return baseline, candidate


def _field_records(value: diff_model.RegistryHistoryReleaseEvidencePipelineBundleDiff) -> tuple[Mapping[str, Any], ...]:
    baseline, candidate = _projections(value)
    return tuple({"field": field, "changed": baseline[field] != candidate[field], "baseline": baseline[field], "candidate": candidate[field]} for field in diff_model.BUNDLE_FIELDS)


def _file_record(item: diff_model.RegistryHistoryReleaseEvidencePipelineBundleDiffItem) -> dict[str, Any]:
    return item.summary()


def _evidence_record(item: diff_model.RegistryHistoryReleaseEvidencePipelineBundleDiffItem) -> dict[str, Any]:
    return {"name": item.name, "action": item.action, "baseline_size": item.baseline_size, "candidate_size": item.candidate_size, "baseline_hash": item.baseline_hash, "candidate_hash": item.candidate_hash, "changed_fields": item.changed_fields, "item_address": item.content_address}


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineBundleDiffQuery) -> bool:
    if query.action is not None and record.get("action") != query.action:
        return False
    if query.name is not None and record.get("name") != query.name:
        return False
    if query.changed_field is not None and query.changed_field not in tuple(record.get("changed_fields", ())) and query.changed_field != record.get("field"):
        return False
    return query.text is None or query.text.casefold() in canonical_json(record).casefold()


def _records(value: diff_model.RegistryHistoryReleaseEvidencePipelineBundleDiff, query: RegistryHistoryReleaseEvidencePipelineBundleDiffQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        candidates: tuple[Mapping[str, Any], ...] = (value.summary(),)
    elif query.resource == "fields":
        candidates = _field_records(value)
    elif query.resource in {"files", "changed", "unchanged"}:
        candidates = tuple(_file_record(item) for item in value.items)
        if query.resource == "changed":
            candidates = tuple(record for record in candidates if record["action"] == "changed")
        elif query.resource == "unchanged":
            candidates = tuple(record for record in candidates if record["action"] == "unchanged")
    else:
        candidates = tuple(_evidence_record(item) for item in value.items)
    return tuple(record for record in candidates if _matches(record, query))


def query_diff(value: diff_model.RegistryHistoryReleaseEvidencePipelineBundleDiff, query: RegistryHistoryReleaseEvidencePipelineBundleDiffQuery | None = None, *, resource: str = "summary", action: str | None = None, name: str | None = None, changed_field: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult:
    diff_model.verify_diff(value)
    if query is not None and any(argument != default for argument, default in ((resource, "summary"), (action, None), (name, None), (changed_field, None), (text, None), (offset, 0), (limit, DEFAULT_LIMIT))):
        raise ValidationError("release evidence bundle diff query accepts either a query object or keyword filters")
    selected = query or RegistryHistoryReleaseEvidencePipelineBundleDiffQuery(resource=resource, action=action, name=name, changed_field=changed_field, text=text, offset=offset, limit=limit)
    records = _records(value, selected)
    total_count = len(records)
    window = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult(value.content_address, selected, total_count, window, "pending:query")
    return RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult(value.content_address, selected, total_count, window, address_query(provisional))


def query_bundle_directories(baseline_source: str, candidate_source: str, query: RegistryHistoryReleaseEvidencePipelineBundleDiffQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult:
    return query_diff(diff_model.build_diff(baseline_source, candidate_source), query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult) -> RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult):
        raise ValidationError("release evidence bundle diff query verification requires a typed result")
    value._validate()
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult:
    return RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult.from_mapping(value)


def query_json(value: RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult) -> str:
    verify_query(value)
    return canonical_json(value.to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult) -> str:
    verify_query(value)
    rows = list(value.records)
    fields = sorted({str(key) for record in rows for key in record}) or ["content_address"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in rows:
        writer.writerow({field: canonical_json(record[field]) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult) -> str:
    verify_query(value)
    lines = ["# Assurance History Observatory Archive Registry History Release Evidence Pipeline Bundle Diff Query", "", f"- Resource: `{value.query.resource}`", f"- Action filter: `{value.query.action}`", f"- File filter: `{value.query.name}`", f"- Changed-field filter: `{value.query.changed_field}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- Diff: `{value.diff_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records:
        fields = sorted({str(key) for record in value.records for key in record})
        lines.extend(["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"])
        lines.extend("| " + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields) + " |" for record in value.records)
    else:
        lines.append("No matching records.")
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(RESOURCES)}, "action": {"type": ["string", "null"], "enum": [*ACTIONS, None]}, "name": {"type": ["string", "null"], "enum": [*bundle_model.FILES, None]}, "changed_field": {"type": ["string", "null"], "enum": [*diff_model.BUNDLE_FIELDS, *diff_model.ITEM_FIELDS, None]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["diff_address", "query", "total_count", "returned_count", "records", "content_address"], "properties": {"diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "actions": ACTIONS, "files": bundle_model.FILES, "fields": diff_model.BUNDLE_FIELDS, "item_fields": diff_model.ITEM_FIELDS, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS}, "features": ("semantic field transition queries", "changed and unchanged file queries", "artifact hash and byte evidence", "file and field filtering", "case-insensitive public text search", "deterministic pagination", "content-addressed query replay", "strict verified bundle comparison", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY",
    "ACTIONS",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MAX_QUERY_ITEMS",
    "QUERY_PREFIX",
    "RESOURCES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineBundleDiffQuery",
    "RegistryHistoryReleaseEvidencePipelineBundleDiffQueryResult",
    "address_query",
    "capabilities",
    "query_bundle_directories",
    "query_csv",
    "query_diff",
    "query_json",
    "query_result_from_mapping",
    "query_result_schema",
    "query_schema",
    "render_query_markdown",
    "verify_query",
]
