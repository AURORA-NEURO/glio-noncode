"""Bounded queries over value-free compatibility remediation plans."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility as compatibility_model
from . import downloaded_data_profile_contract_compatibility_remediation as remediation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "actions")
MAX_TOTAL_COUNT = remediation_model.MAX_ACTIONS + 1
MAX_LIMIT = 100
ROW_FIELDS = ("ordinal", "resource", "identity", "change", "outcome", "reason_codes", "action", "priority", "required", "evidence_addresses", "action_address", "content_address")
QUERY_FIELDS = ("plan_address", "version", "boundary", "resources", "outcome", "resource", "priority", "action", "required", "identity", "reason", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
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


class DownloadedDataProfileContractCompatibilityRemediationQueryRow:
    """One bounded remediation summary or action row."""

    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, change: str, outcome: str, reason_codes: Sequence[str], action: str, priority: str, required: bool, evidence_addresses: Sequence[str], action_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "remediation query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "remediation query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("remediation query row resource is unsupported")
        self.identity = _text(identity, "remediation query row identity", 4096)
        self.change = _label(change, "remediation query row change")
        self.outcome = _label(outcome, "remediation query row outcome")
        if self.outcome != "summary" and self.outcome not in compatibility_model.OUTCOMES:
            raise ValidationError("remediation query row outcome is unsupported")
        self.reason_codes = tuple(_label(item, "remediation query row reason") for item in _sequence(reason_codes, "remediation query row reasons", len(compatibility_model.REASON_CODES)))
        self.action = _label(action, "remediation query row action")
        if self.action != "summary" and self.action not in remediation_model.ACTION_KINDS:
            raise ValidationError("remediation query row action is unsupported")
        self.priority = _label(priority, "remediation query row priority")
        if self.priority != "summary" and self.priority not in remediation_model.PRIORITIES:
            raise ValidationError("remediation query row priority is unsupported")
        self.required = _bool(required, "remediation query row requiredness")
        self.evidence_addresses = tuple(sorted({_address(item, "remediation query row evidence address") for item in _sequence(evidence_addresses, "remediation query row evidence", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("remediation query rows require evidence")
        self.action_address = _address(action_address, "remediation query row action address") if action_address else ""
        self.content_address = _address(content_address, "remediation query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and any((self.change != "summary", self.outcome != "summary", self.action != "summary", self.priority != "summary", self.action_address)):
            raise ValidationError("remediation summary row has action-only fields")
        if self.resource == "actions" and (self.change == "summary" or self.outcome == "summary" or self.action == "summary" or self.priority == "summary" or not self.action_address):
            raise ValidationError("remediation action row is incomplete")
        if not _public(self.to_dict()):
            raise ValidationError("remediation query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("remediation query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationQueryRow:
        value = _mapping(value, "remediation query row")
        _strict(value, set(cls.FIELDS), "remediation query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationQuery:
    """A deterministic, paginated remediation query result."""

    FIELDS = QUERY_FIELDS

    def __init__(self, plan_address: str, version: str, boundary: str, resources: Sequence[str], outcome: str, resource: str, priority: str, action: str, required: bool, identity: str, reason: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractCompatibilityRemediationQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.plan_address = _address(plan_address, "remediation query plan address", remediation_model.PLAN_PREFIX)
        self.version = _text(version, "remediation query version")
        self.boundary = _text(boundary, "remediation query boundary", 512)
        self.resources = _ordered_labels(resources, "remediation query resources", RESOURCES)
        self.outcome = _label(outcome, "remediation query outcome", required=False)
        if self.outcome and self.outcome not in compatibility_model.OUTCOMES:
            raise ValidationError("remediation query outcome is unsupported")
        self.resource = _label(resource, "remediation query action resource", required=False)
        if self.resource and self.resource not in compatibility_model.diff_model.RESOURCES:
            raise ValidationError("remediation query action resource is unsupported")
        self.priority = _label(priority, "remediation query priority", required=False)
        if self.priority and self.priority not in remediation_model.PRIORITIES:
            raise ValidationError("remediation query priority is unsupported")
        self.action = _label(action, "remediation query action", required=False)
        if self.action and self.action not in remediation_model.ACTION_KINDS:
            raise ValidationError("remediation query action is unsupported")
        self.required = _bool(required, "remediation query requiredness")
        self.identity = _text(identity, "remediation query identity", 4096, required=False)
        self.reason = _label(reason, "remediation query reason", required=False)
        if self.reason and self.reason not in compatibility_model.REASON_CODES:
            raise ValidationError("remediation query reason is unsupported")
        self.text = _text(text, "remediation query text", 1024, required=False)
        self.offset = _count(offset, "remediation query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "remediation query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "remediation query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "remediation query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "remediation query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "remediation query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "remediation query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationQueryRow) else DownloadedDataProfileContractCompatibilityRemediationQueryRow.from_mapping(item) for item in _sequence(rows, "remediation query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "remediation query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("remediation query version or boundary is not current")
        if len(self.rows) != self.returned_count or self.returned_count > self.limit or tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("remediation query rows are not contiguous")
        if self.matched_count > self.total_count or self.returned_count > self.matched_count or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("remediation query counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("remediation query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("remediation query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"plan_address": self.plan_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "outcome": self.outcome, "resource": self.resource, "priority": self.priority, "action": self.action, "required": self.required, "identity": self.identity, "reason": self.reason, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationQuery:
        value = _mapping(value, "remediation query")
        _strict(value, set(cls.FIELDS), "remediation query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _summary_row(plan: remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan) -> DownloadedDataProfileContractCompatibilityRemediationQueryRow:
    body = {"ordinal": 1, "resource": "summary", "identity": "summary", "change": "summary", "outcome": "summary", "reason_codes": (), "action": "summary", "priority": "summary", "required": False, "evidence_addresses": (plan.content_address, plan.gate_address), "action_address": "", "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationQueryRow(**(body | {"content_address": address_row(provisional)}))


def _action_row(item: remediation_model.DownloadedDataProfileContractCompatibilityRemediationAction, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationQueryRow:
    body = {"ordinal": ordinal, "resource": "actions", "identity": item.identity, "change": item.change, "outcome": item.outcome, "reason_codes": item.reason_codes, "action": item.action, "priority": item.priority, "required": item.required, "evidence_addresses": item.evidence_addresses, "action_address": item.content_address, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationQueryRow(**(body | {"content_address": address_row(provisional)}))


def _readdress(row: DownloadedDataProfileContractCompatibilityRemediationQueryRow, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationQueryRow(**(body | {"content_address": address_row(provisional)}))


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationQueryRow, query: DownloadedDataProfileContractCompatibilityRemediationQuery) -> bool:
    if row.resource not in query.resources:
        return False
    if row.resource == "summary":
        return not any((query.outcome, query.resource, query.priority, query.action, query.identity, query.reason)) and (not query.text or query.text.casefold() in "summary".casefold())
    if query.outcome and row.outcome != query.outcome:
        return False
    if query.resource and row.resource != "actions":
        return False
    if query.priority and row.priority != query.priority:
        return False
    if query.action and row.action != query.action:
        return False
    if query.required and not row.required:
        return False
    if query.identity and query.identity.casefold() not in row.identity.casefold():
        return False
    if query.reason and query.reason not in row.reason_codes:
        return False
    haystack = " ".join((row.resource, row.identity, row.change, row.outcome, row.action, row.priority, *row.reason_codes)).casefold()
    return not query.text or query.text.casefold() in haystack


def query_plan(value: remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan, *, resources: Sequence[str] = RESOURCES, outcome: str = "", resource: str = "", priority: str = "", action: str = "", required: bool = False, identity: str = "", reason: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationQuery:
    if not isinstance(value, remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan):
        raise ValidationError("remediation query requires a typed plan")
    provisional = DownloadedDataProfileContractCompatibilityRemediationQuery(value.content_address, VERSION, BOUNDARY, resources, outcome, resource, priority, action, required, identity, reason, text, offset, limit, 0, 0, 0, 0, False, (), QUERY_PREFIX + ":pending")
    rows: list[DownloadedDataProfileContractCompatibilityRemediationQueryRow] = []
    if "summary" in provisional.resources:
        rows.append(_summary_row(value))
    if "actions" in provisional.resources:
        rows.extend(_action_row(item, len(rows) + 1) for item in value.actions)
    matched = tuple(row for row in rows if _matches(row, provisional))
    selected = tuple(_readdress(row, ordinal) for ordinal, row in enumerate(matched[offset:offset + limit], 1))
    body = {"plan_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": provisional.resources, "outcome": provisional.outcome, "resource": provisional.resource, "priority": provisional.priority, "action": provisional.action, "required": provisional.required, "identity": provisional.identity, "reason": provisional.reason, "text": provisional.text, "offset": provisional.offset, "limit": provisional.limit, "total_count": len(rows), "matched_count": len(matched), "returned_count": len(selected), "next_offset": provisional.offset + len(selected), "truncated": provisional.offset + len(selected) < len(matched), "rows": selected, "content_address": QUERY_PREFIX + ":pending"}
    final = DownloadedDataProfileContractCompatibilityRemediationQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationQuery(**(body | {"content_address": address_query(final)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationQuery:
    return DownloadedDataProfileContractCompatibilityRemediationQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationQuery) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationQuery) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationQuery.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(";".join(item.reason_codes) if field == "reason_codes" else ";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in ROW_FIELDS) for item in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationQuery) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Query", "", f"- Plan: `{value.plan_address}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Truncated: `{value.truncated}`", f"- Address: `{value.content_address}`", "", "| # | identity | outcome | action | priority | required |", "| ---: | --- | --- | --- | --- | ---: |"]
    lines.extend(f"| {row.ordinal} | `{row.identity}` | `{row.outcome}` | `{row.action}` | `{row.priority}` | `{row.required}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "change": {"type": "string"}, "outcome": {"type": "string"}, "reason_codes": {"type": "array", "items": {"enum": list(compatibility_model.REASON_CODES)}}, "action": {"enum": list(remediation_model.ACTION_KINDS) + ["summary"]}, "priority": {"enum": list(remediation_model.PRIORITIES) + ["summary"]}, "required": {"type": "boolean"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "action_address": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"plan_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "outcome": {"type": "string"}, "resource": {"type": "string"}, "priority": {"type": "string"}, "action": {"type": "string"}, "required": {"type": "boolean"}, "identity": {"type": "string"}, "reason": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "actions": remediation_model.ACTION_KINDS, "priorities": remediation_model.PRIORITIES, "operations": ("query_plan", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "DownloadedDataProfileContractCompatibilityRemediationQuery", "DownloadedDataProfileContractCompatibilityRemediationQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_plan", "query_schema", "render_query_markdown", "row_schema"]
