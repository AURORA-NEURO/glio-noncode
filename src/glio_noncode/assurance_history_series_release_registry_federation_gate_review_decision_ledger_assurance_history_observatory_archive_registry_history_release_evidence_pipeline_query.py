"""Bounded queries over consolidated release-evidence pipeline receipts.

The pipeline receipt is intentionally compact, while operators often need a
stage-oriented view.  This module provides deterministic summary, stage,
decision, and address-evidence resources without reopening downloaded data.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = pipeline_model.VERSION + "-query-v1"
BOUNDARY = pipeline_model.BOUNDARY + "_query"
QUERY_PREFIX = pipeline_model.PIPELINE_PREFIX + "-query"
DEFAULT_LIMIT = 50
MAX_LIMIT = 64
MAX_QUERY_ITEMS = 16
MAX_TEXT = 512
RESOURCES = ("summary", "stages", "decisions", "evidence")
STAGE_IDS = ("history-load", "release-gate", "package", "package-audit", "release-certificate")
STATE_VALUES = (*pipeline_model.STATES, "loaded", "materialized", "complete", "audited")


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
    return pipeline_model._public(value)


class RegistryHistoryReleaseEvidencePipelineQuery:
    """A bounded filter over one consolidated release-evidence receipt."""

    RESOURCES = RESOURCES

    def __init__(self, resource: str = "summary", accepted: bool | None = None, state: str | None = None, stage: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "release evidence pipeline query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("release evidence pipeline query resource is not supported")
        self.accepted = None if accepted is None else _bool(accepted, "release evidence pipeline query accepted")
        self.state = None if state is None else _text(state, "release evidence pipeline query state", 32)
        if self.state is not None and self.state not in STATE_VALUES:
            raise ValidationError("release evidence pipeline query state is not supported")
        self.stage = None if stage is None else _text(stage, "release evidence pipeline query stage", 64)
        if self.stage is not None and self.stage not in STAGE_IDS:
            raise ValidationError("release evidence pipeline query stage is not supported")
        self.text = None if text is None else _text(text, "release evidence pipeline query text", MAX_TEXT)
        self.offset = _count(offset, "release evidence pipeline query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "release evidence pipeline query limit", MAX_LIMIT, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "accepted": self.accepted, "state": self.state, "stage": self.stage, "text": self.text, "offset": self.offset, "limit": self.limit}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineQuery:
        value = _mapping(value, "release evidence pipeline query")
        _strict(value, {"resource", "accepted", "state", "stage", "text", "offset", "limit"}, "release evidence pipeline query")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineQueryResult:
    """A content-addressed page of public pipeline records."""

    def __init__(self, pipeline_address: str, query: RegistryHistoryReleaseEvidencePipelineQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.pipeline_address = _address(pipeline_address, "release evidence pipeline query pipeline address", pipeline_model.PIPELINE_PREFIX)
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(dict(record) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.query, RegistryHistoryReleaseEvidencePipelineQuery):
            raise ValidationError("release evidence pipeline query result query must be typed")
        _count(self.total_count, "release evidence pipeline query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "release evidence pipeline query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("release evidence pipeline query window is invalid")
        if any(not isinstance(record, Mapping) or not _public(record) for record in self.records):
            raise ValidationError("release evidence pipeline query result contains a private record")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence pipeline query content address")
        else:
            _address(self.content_address, "release evidence pipeline query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("release evidence pipeline query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"pipeline_address": self.pipeline_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineQueryResult:
        value = _mapping(value, "release evidence pipeline query result")
        _strict(value, {"pipeline_address", "query", "total_count", "returned_count", "records", "content_address"}, "release evidence pipeline query result")
        query = RegistryHistoryReleaseEvidencePipelineQuery.from_mapping(_mapping(value["query"], "release evidence pipeline query"))
        records = tuple(_mapping(record, "release evidence pipeline query record") for record in _sequence(value["records"], "release evidence pipeline query records", MAX_QUERY_ITEMS))
        result = cls(value["pipeline_address"], query, value["total_count"], records, value["content_address"])
        if result.returned_count != value["returned_count"]:
            raise ValidationError("release evidence pipeline query returned count is not conserved")
        return result


def address_query(value: RegistryHistoryReleaseEvidencePipelineQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineQueryResult):
        raise ValidationError("release evidence pipeline query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _stage_records(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline) -> tuple[Mapping[str, Any], ...]:
    return (
        {"stage": "history-load", "accepted": True, "state": "loaded", "address": value.history_address, "snapshot_count": value.snapshot_count},
        {"stage": "release-gate", "accepted": value.gate_accepted, "state": value.gate_state, "address": value.gate_address},
        {"stage": "package", "accepted": True, "state": "materialized", "address": value.package_manifest_address, "file_count": value.package_file_count},
        {"stage": "package-audit", "accepted": value.package_audit_accepted, "state": value.package_audit_state, "address": value.package_audit_address},
        {"stage": "release-certificate", "accepted": value.certificate_accepted, "state": value.certificate_state, "address": value.certificate_address},
    )


def _decision_records(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline) -> tuple[Mapping[str, Any], ...]:
    return (
        {"decision": "gate", "accepted": value.gate_accepted, "state": value.gate_state, "address": value.gate_address},
        {"decision": "certificate", "accepted": value.certificate_accepted, "state": value.certificate_state, "address": value.certificate_address},
        {"decision": "release", "accepted": value.release_ready, "state": value.state, "address": value.content_address},
    )


def _evidence_records(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline) -> tuple[Mapping[str, Any], ...]:
    return (
        {"evidence": "history", "address": value.history_address},
        {"evidence": "release-gate", "address": value.gate_address},
        {"evidence": "package-manifest", "address": value.package_manifest_address},
        {"evidence": "package-audit", "address": value.package_audit_address},
        {"evidence": "release-certificate", "address": value.certificate_address},
        {"evidence": "pipeline", "address": value.content_address},
    )


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineQuery) -> bool:
    if query.accepted is not None and record.get("accepted") is not query.accepted:
        return False
    if query.state is not None and record.get("state") != query.state:
        return False
    if query.stage is not None and record.get("stage") != query.stage:
        return False
    return query.text is None or query.text.casefold() in canonical_json(record).casefold()


def _records(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline, query: RegistryHistoryReleaseEvidencePipelineQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        candidates: tuple[Mapping[str, Any], ...] = (value.summary(),)
    elif query.resource == "stages":
        candidates = _stage_records(value)
    elif query.resource == "decisions":
        candidates = _decision_records(value)
    else:
        candidates = _evidence_records(value)
    return tuple(record for record in candidates if _matches(record, query))


def query_pipeline(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline, query: RegistryHistoryReleaseEvidencePipelineQuery | None = None, *, resource: str = "summary", accepted: bool | None = None, state: str | None = None, stage: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineQueryResult:
    pipeline_model.verify_pipeline(value)
    if query is not None and any(argument != default for argument, default in ((resource, "summary"), (accepted, None), (state, None), (stage, None), (text, None), (offset, 0), (limit, DEFAULT_LIMIT))):
        raise ValidationError("release evidence pipeline query accepts either a query object or keyword filters")
    selected = query or RegistryHistoryReleaseEvidencePipelineQuery(resource=resource, accepted=accepted, state=state, stage=stage, text=text, offset=offset, limit=limit)
    records = _records(value, selected)
    total_count = len(records)
    window = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineQueryResult(value.content_address, selected, total_count, window, "pending:query")
    return RegistryHistoryReleaseEvidencePipelineQueryResult(value.content_address, selected, total_count, window, address_query(provisional))


def query_history_directory(source: str, query: RegistryHistoryReleaseEvidencePipelineQuery | None = None, *, package_destination: str | None = None, overwrite: bool = False, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineQueryResult:
    """Build the pipeline from downloaded history and query its receipt."""

    return query_pipeline(pipeline_model.build_pipeline(source, package_destination, overwrite=overwrite), query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineQueryResult) -> RegistryHistoryReleaseEvidencePipelineQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineQueryResult):
        raise ValidationError("release evidence pipeline query verification requires a typed result")
    value._validate()
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineQueryResult:
    return RegistryHistoryReleaseEvidencePipelineQueryResult.from_mapping(value)


def query_json(value: RegistryHistoryReleaseEvidencePipelineQueryResult) -> str:
    verify_query(value)
    return canonical_json(value.to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineQueryResult) -> str:
    verify_query(value)
    rows = list(value.records)
    fields = sorted({str(key) for record in rows for key in record}) or ["content_address"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in rows:
        writer.writerow({field: canonical_json(record[field]) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineQueryResult) -> str:
    verify_query(value)
    lines = ["# Assurance History Observatory Release Evidence Pipeline Query", "", f"- Resource: `{value.query.resource}`", f"- Accepted filter: `{value.query.accepted}`", f"- State filter: `{value.query.state}`", f"- Stage filter: `{value.query.stage}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- Pipeline: `{value.pipeline_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records:
        fields = sorted({str(key) for record in value.records for key in record})
        lines.extend(["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"])
        lines.extend("| " + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields) + " |" for record in value.records)
    else:
        lines.append("No matching records.")
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(RESOURCES)}, "accepted": {"type": ["boolean", "null"]}, "state": {"type": ["string", "null"], "enum": [*STATE_VALUES, None]}, "stage": {"type": ["string", "null"], "enum": [*STAGE_IDS, None]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["pipeline_address", "query", "total_count", "returned_count", "records", "content_address"], "properties": {"pipeline_address": {"type": "string", "pattern": "^" + pipeline_model.PIPELINE_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "stages": STAGE_IDS, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS}, "features": ("bounded pipeline summary inspection", "stage-by-stage release evidence", "gate certificate and final decision resources", "content-address evidence resource", "accepted state stage and text filtering", "deterministic pagination", "content-addressed result replay", "downloaded-history pipeline query", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MAX_QUERY_ITEMS",
    "QUERY_PREFIX",
    "RESOURCES",
    "STATE_VALUES",
    "STAGE_IDS",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineQuery",
    "RegistryHistoryReleaseEvidencePipelineQueryResult",
    "address_query",
    "capabilities",
    "query_csv",
    "query_history_directory",
    "query_json",
    "query_pipeline",
    "query_result_from_mapping",
    "query_result_schema",
    "query_schema",
    "render_query_markdown",
    "verify_query",
]
