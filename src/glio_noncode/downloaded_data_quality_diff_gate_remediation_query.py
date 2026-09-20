"""Bounded queries over downloaded-data quality gate remediation plans."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate as gate_model
from . import downloaded_data_quality_diff_gate_remediation as remediation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-remediation-query-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_remediation_query"
QUERY_PREFIX = "glio-noncode-download-quality-diff-gate-remediation-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "actions", "required", "blocked", "review", "critical")
MAX_TOTAL_COUNT = remediation_model.MAX_ACTIONS * len(RESOURCES) + 1
MAX_LIMIT = 100
DEFAULT_LIMIT = 25
ROW_FIELDS = ("ordinal", "resource", "finding_address", "identity", "change", "direction", "outcome", "reason_codes", "action", "priority", "required", "evidence_addresses", "action_address", "content_address")
QUERY_FIELDS = ("plan_address", "version", "boundary", "resources", "outcome", "action", "priority", "required_only", "identity", "reason", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, optional: bool = False) -> str:
    if optional and value == "":
        return ""
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    namespace, digest = value.split(":", 1)
    if not namespace or (digest != "pending" and (len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest))):
        raise ValidationError(f"{field} must be a canonical content address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
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
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _ordered_labels(value: Any, field: str, allowed: Sequence[str]) -> tuple[str, ...]:
    labels = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not labels or len(set(labels)) != len(labels) or any(item not in allowed for item in labels) or tuple(sorted(labels, key=allowed.index)) != labels:
        raise ValidationError(f"{field} contains unsupported or unordered labels")
    return labels


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataQualityDiffGateRemediationQueryRow:
    """One bounded projection row for a remediation query."""

    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, finding_address: str, identity: str, change: str, direction: str, outcome: str, reason_codes: Sequence[str], action: str, priority: str, required: bool, evidence_addresses: Sequence[str], action_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality gate remediation query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "quality gate remediation query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("quality gate remediation query row resource is unsupported")
        self.finding_address = _address(finding_address, "quality gate remediation query row finding address", gate_model.FINDING_PREFIX, optional=self.resource == "summary")
        self.identity = _text(identity, "quality gate remediation query row identity", 4096)
        self.change = _label(change, "quality gate remediation query row change")
        self.direction = _label(direction, "quality gate remediation query row direction")
        self.outcome = _label(outcome, "quality gate remediation query row outcome")
        if self.resource != "summary" and self.outcome not in gate_model.OUTCOMES:
            raise ValidationError("quality gate remediation query row outcome is unsupported")
        self.reason_codes = tuple(_label(item, "quality gate remediation query row reason") for item in _sequence(reason_codes, "quality gate remediation query row reasons", len(gate_model.REASON_CODES)))
        self.action = _label(action, "quality gate remediation query row action")
        if self.resource != "summary" and self.action not in remediation_model.ACTION_KINDS:
            raise ValidationError("quality gate remediation query row action is unsupported")
        self.priority = _label(priority, "quality gate remediation query row priority")
        if self.resource != "summary" and self.priority not in remediation_model.PRIORITIES:
            raise ValidationError("quality gate remediation query row priority is unsupported")
        self.required = _bool(required, "quality gate remediation query row requiredness")
        self.evidence_addresses = tuple(sorted({_address(item, "quality gate remediation query row evidence address") for item in _sequence(evidence_addresses, "quality gate remediation query row evidence", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("quality gate remediation query rows require evidence")
        self.action_address = _address(action_address, "quality gate remediation query row action address", remediation_model.ACTION_PREFIX, optional=True)
        self.content_address = _address(content_address, "quality gate remediation query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        summary_only = self.resource == "summary"
        if summary_only and any((self.finding_address, self.change != "summary", self.direction != "summary", self.outcome != "summary", self.reason_codes, self.action != "summary", self.priority != "summary", self.required, self.action_address)):
            raise ValidationError("quality gate remediation summary row has action-only fields")
        if not summary_only and (not self.finding_address or self.change == "summary" or self.direction == "summary" or self.outcome == "summary" or self.action == "summary" or self.priority == "summary" or not self.action_address):
            raise ValidationError("quality gate remediation action row is incomplete")
        if not _public(self.to_dict()):
            raise ValidationError("quality gate remediation query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("quality gate remediation query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationQueryRow":
        value = _mapping(value, "quality gate remediation query row")
        _strict(value, set(cls.FIELDS), "quality gate remediation query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataQualityDiffGateRemediationQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataQualityDiffGateRemediationQuery:
    """A deterministic, paginated remediation query result."""

    FIELDS = QUERY_FIELDS

    def __init__(self, plan_address: str, version: str, boundary: str, resources: Sequence[str], outcome: str, action: str, priority: str, required_only: bool, identity: str, reason: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataQualityDiffGateRemediationQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.plan_address = _address(plan_address, "quality gate remediation query plan address", remediation_model.PLAN_PREFIX)
        self.version = _text(version, "quality gate remediation query version")
        self.boundary = _text(boundary, "quality gate remediation query boundary", 512)
        self.resources = _ordered_labels(resources, "quality gate remediation query resources", RESOURCES)
        self.outcome = _label(outcome, "quality gate remediation query outcome", required=False)
        if self.outcome and self.outcome not in gate_model.OUTCOMES:
            raise ValidationError("quality gate remediation query outcome is unsupported")
        self.action = _label(action, "quality gate remediation query action", required=False)
        if self.action and self.action not in remediation_model.ACTION_KINDS:
            raise ValidationError("quality gate remediation query action is unsupported")
        self.priority = _label(priority, "quality gate remediation query priority", required=False)
        if self.priority and self.priority not in remediation_model.PRIORITIES:
            raise ValidationError("quality gate remediation query priority is unsupported")
        self.required_only = _bool(required_only, "quality gate remediation query requiredness filter")
        self.identity = _text(identity, "quality gate remediation query identity", 4096, required=False)
        self.reason = _label(reason, "quality gate remediation query reason", required=False)
        if self.reason and self.reason not in gate_model.REASON_CODES:
            raise ValidationError("quality gate remediation query reason is unsupported")
        self.text = _text(text, "quality gate remediation query text", 1024, required=False)
        self.offset = _count(offset, "quality gate remediation query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "quality gate remediation query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "quality gate remediation query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "quality gate remediation query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "quality gate remediation query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "quality gate remediation query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "quality gate remediation query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataQualityDiffGateRemediationQueryRow) else DownloadedDataQualityDiffGateRemediationQueryRow.from_mapping(item) for item in _sequence(rows, "quality gate remediation query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "quality gate remediation query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality gate remediation query version or boundary is not current")
        if len(self.rows) != self.returned_count or self.returned_count > self.limit or tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("quality gate remediation query rows are not contiguous")
        if self.matched_count > self.total_count or self.returned_count > self.matched_count or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("quality gate remediation query counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("quality gate remediation query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("quality gate remediation query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"plan_address": self.plan_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "outcome": self.outcome, "action": self.action, "priority": self.priority, "required_only": self.required_only, "identity": self.identity, "reason": self.reason, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationQuery":
        value = _mapping(value, "quality gate remediation query")
        _strict(value, set(cls.FIELDS), "quality gate remediation query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataQualityDiffGateRemediationQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _summary_row(plan: remediation_model.DownloadedDataQualityDiffGateRemediationPlan) -> DownloadedDataQualityDiffGateRemediationQueryRow:
    body = {"ordinal": 1, "resource": "summary", "finding_address": "", "identity": "summary", "change": "summary", "direction": "summary", "outcome": "summary", "reason_codes": (), "action": "summary", "priority": "summary", "required": False, "evidence_addresses": (plan.content_address, plan.gate_address), "action_address": "", "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationQueryRow(**body)
    return DownloadedDataQualityDiffGateRemediationQueryRow(**(body | {"content_address": address_row(provisional)}))


def _action_row(item: remediation_model.DownloadedDataQualityDiffGateRemediationAction, resource: str, ordinal: int) -> DownloadedDataQualityDiffGateRemediationQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "finding_address": item.finding_address, "identity": item.identity, "change": item.change, "direction": item.direction, "outcome": item.outcome, "reason_codes": item.reason_codes, "action": item.action, "priority": item.priority, "required": item.required, "evidence_addresses": item.evidence_addresses, "action_address": item.content_address, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationQueryRow(**body)
    return DownloadedDataQualityDiffGateRemediationQueryRow(**(body | {"content_address": address_row(provisional)}))


def _readdress(row: DownloadedDataQualityDiffGateRemediationQueryRow, ordinal: int) -> DownloadedDataQualityDiffGateRemediationQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationQueryRow(**body)
    return DownloadedDataQualityDiffGateRemediationQueryRow(**(body | {"content_address": address_row(provisional)}))


def _project_rows(plan: remediation_model.DownloadedDataQualityDiffGateRemediationPlan, resources: Sequence[str]) -> tuple[DownloadedDataQualityDiffGateRemediationQueryRow, ...]:
    rows: list[DownloadedDataQualityDiffGateRemediationQueryRow] = []
    if "summary" in resources:
        rows.append(_summary_row(plan))
    for resource in resources:
        if resource == "summary":
            continue
        selected = plan.actions
        if resource == "required":
            selected = tuple(item for item in selected if item.required)
        elif resource == "blocked":
            selected = tuple(item for item in selected if item.outcome == "blocked")
        elif resource == "review":
            selected = tuple(item for item in selected if item.outcome == "review")
        elif resource == "critical":
            selected = tuple(item for item in selected if item.priority == "critical")
        rows.extend(_action_row(item, resource, len(rows) + 1) for item in selected)
    return tuple(rows)


def _matches(row: DownloadedDataQualityDiffGateRemediationQueryRow, query: DownloadedDataQualityDiffGateRemediationQuery) -> bool:
    if row.resource not in query.resources:
        return False
    if row.resource == "summary":
        return not any((query.outcome, query.action, query.priority, query.required_only, query.identity, query.reason)) and (not query.text or query.text.casefold() in "summary".casefold())
    if query.outcome and row.outcome != query.outcome:
        return False
    if query.action and row.action != query.action:
        return False
    if query.priority and row.priority != query.priority:
        return False
    if query.required_only and not row.required:
        return False
    if query.identity and query.identity.casefold() not in row.identity.casefold():
        return False
    if query.reason and query.reason not in row.reason_codes:
        return False
    if query.text and query.text.casefold() not in (row.identity + " " + row.detail if hasattr(row, "detail") else row.identity).casefold():
        haystack = " ".join((row.identity, row.change, row.direction, row.outcome, row.action, row.priority, *row.reason_codes))
        if query.text.casefold() not in haystack.casefold():
            return False
    return True


def query_plan(plan: remediation_model.DownloadedDataQualityDiffGateRemediationPlan, *, resources: Sequence[str] = ("summary", "actions"), outcome: str = "", action: str = "", priority: str = "", required_only: bool = False, identity: str = "", reason: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataQualityDiffGateRemediationQuery:
    if not isinstance(plan, remediation_model.DownloadedDataQualityDiffGateRemediationPlan):
        raise ValidationError("quality gate remediation query requires a typed plan")
    requested = _ordered_labels(resources, "quality gate remediation query resources", RESOURCES)
    offset = _count(offset, "quality gate remediation query offset", MAX_TOTAL_COUNT)
    limit = _count(limit, "quality gate remediation query limit", MAX_LIMIT, positive=True)
    probe = DownloadedDataQualityDiffGateRemediationQuery(plan.content_address, VERSION, BOUNDARY, requested, outcome, action, priority, required_only, identity, reason, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    all_rows = _project_rows(plan, requested)
    matched = tuple(row for row in all_rows if _matches(row, probe))
    total_count = len(all_rows)
    page = matched[offset:offset + limit]
    rows = tuple(_readdress(row, ordinal) for ordinal, row in enumerate(page, 1))
    body = {"plan_address": plan.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": requested, "outcome": outcome, "action": action, "priority": priority, "required_only": required_only, "identity": identity, "reason": reason, "text": text, "offset": offset, "limit": limit, "total_count": total_count, "matched_count": len(matched), "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < len(matched), "rows": rows}
    provisional = DownloadedDataQualityDiffGateRemediationQuery(**body, content_address=QUERY_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateRemediationQuery(**body, content_address=address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRemediationQuery:
    return DownloadedDataQualityDiffGateRemediationQuery.from_mapping(value)


def query_json(value: DownloadedDataQualityDiffGateRemediationQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataQualityDiffGateRemediationQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    for item in value.rows:
        row = item.to_dict()
        writer.writerow(";".join(row[field]) if field in {"reason_codes", "evidence_addresses"} else row[field] for field in ROW_FIELDS)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataQualityDiffGateRemediationQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Remediation Query", "", f"- Plan: `{value.plan_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Matched / returned: `{value.matched_count} / {value.returned_count}`", f"- Truncated: `{value.truncated}`", "", "| # | resource | outcome | action | priority | required | identity |", "| ---: | --- | --- | --- | --- | ---: | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.outcome}` | `{row.action}` | `{row.priority}` | `{row.required}` | `{row.identity}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate remediation query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"plan_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "outcome": {"type": "string"}, "action": {"type": "string"}, "priority": {"type": "string"}, "required_only": {"type": "boolean"}, "identity": {"type": "string"}, "reason": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def row_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data quality diff gate remediation query row",
        "type": "object",
        "additionalProperties": False,
        "required": list(ROW_FIELDS),
        "properties": {
            "ordinal": {"type": "integer", "minimum": 1},
            "resource": {"enum": list(RESOURCES)},
            "finding_address": {"type": "string"},
            "identity": {"type": "string"},
            "change": {"type": "string"},
            "direction": {"type": "string"},
            "outcome": {"type": "string"},
            "reason_codes": {"type": "array", "items": {"type": "string"}},
            "action": {"type": "string"},
            "priority": {"type": "string"},
            "required": {"type": "boolean"},
            "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
            "action_address": {"type": "string"},
            "content_address": {"type": "string"},
        },
    }


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "operations": ("query_plan", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataQualityDiffGateRemediationQuery", "DownloadedDataQualityDiffGateRemediationQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_plan", "query_schema", "render_query_markdown", "row_schema"]
