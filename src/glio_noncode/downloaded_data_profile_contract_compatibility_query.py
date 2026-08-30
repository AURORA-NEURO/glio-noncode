"""Bounded public queries over downloaded-data compatibility findings."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility as compatibility_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-compatibility-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "findings")
MAX_TEXT = 4096
MAX_LIMIT = 10_000
MAX_TOTAL_COUNT = 1 + compatibility_model.MAX_FINDINGS
ROW_FIELDS = (
    "ordinal",
    "resource",
    "identity",
    "change",
    "outcome",
    "reason_codes",
    "left_address",
    "right_address",
    "diff_item_address",
    "finding_address",
    "content_address",
)
QUERY_FIELDS = (
    "gate_address",
    "version",
    "boundary",
    "resources",
    "outcome",
    "resource",
    "identity",
    "reason",
    "text",
    "offset",
    "limit",
    "total_count",
    "matched_count",
    "returned_count",
    "next_offset",
    "truncated",
    "rows",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
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
    value = _text(value, field, 2048, required=True)
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


def _ordered_labels(value: Any, field: str, allowed: Sequence[str], *, empty: bool = False) -> tuple[str, ...]:
    labels = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not labels and not empty:
        raise ValidationError(f"{field} must not be empty")
    if len(set(labels)) != len(labels) or any(item not in allowed for item in labels) or tuple(sorted(labels, key=allowed.index)) != labels:
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


class DownloadedDataProfileContractCompatibilityQueryRow:
    """One bounded value-free compatibility query row."""

    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, change: str, outcome: str, reason_codes: Sequence[str], left_address: str, right_address: str, diff_item_address: str, finding_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "compatibility query row ordinal", MAX_LIMIT, positive=True)
        self.resource = _label(resource, "compatibility query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("compatibility query row resource is unsupported")
        self.identity = _text(identity, "compatibility query row identity", 4096, required=True)
        self.change = _label(change, "compatibility query row change")
        self.outcome = _label(outcome, "compatibility query row outcome")
        if self.resource == "summary":
            if self.identity != "summary" or self.change != "summary" or self.outcome != "summary":
                raise ValidationError("compatibility summary query row is incomplete")
            allowed_reasons = ()
        else:
            if self.change not in compatibility_model.diff_model.CHANGES or self.outcome not in compatibility_model.OUTCOMES:
                raise ValidationError("compatibility query row transition is unsupported")
            allowed_reasons = compatibility_model.REASON_CODES
        self.reason_codes = _ordered_labels(reason_codes, "compatibility query row reason codes", allowed_reasons, empty=True)
        self.left_address = _address(left_address, "compatibility query row left address", optional=True)
        self.right_address = _address(right_address, "compatibility query row right address", optional=True)
        self.diff_item_address = _address(diff_item_address, "compatibility query row diff item address", compatibility_model.diff_model.ITEM_PREFIX, optional=True)
        self.finding_address = _address(finding_address, "compatibility query row finding address", compatibility_model.FINDING_PREFIX, optional=True)
        self.content_address = _address(content_address, "compatibility query row address", ROW_PREFIX)
        if self.resource == "summary":
            if not self.left_address or not self.right_address or self.diff_item_address or self.finding_address:
                raise ValidationError("compatibility summary query row addresses are invalid")
        elif not self.finding_address or not self.diff_item_address:
            raise ValidationError("compatibility finding query row addresses are incomplete")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("compatibility query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("compatibility query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityQueryRow:
        value = _mapping(value, "compatibility query row")
        _strict(value, set(cls.FIELDS), "compatibility query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityQuery:
    """Content-addressed bounded selection of compatibility rows."""

    FIELDS = QUERY_FIELDS

    def __init__(self, gate_address: str, version: str, boundary: str, resources: Sequence[str], outcome: str, resource: str, identity: str, reason: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractCompatibilityQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.gate_address = _address(gate_address, "compatibility query gate address", compatibility_model.GATE_PREFIX)
        self.version = _text(version, "compatibility query version", required=True)
        self.boundary = _text(boundary, "compatibility query boundary", 512, required=True)
        self.resources = _ordered_labels(resources, "compatibility query resources", RESOURCES)
        self.outcome = _label(outcome, "compatibility query outcome", required=False)
        if self.outcome and self.outcome not in compatibility_model.OUTCOMES:
            raise ValidationError("compatibility query outcome filter is unsupported")
        self.resource = _label(resource, "compatibility query resource", required=False)
        if self.resource and self.resource not in compatibility_model.diff_model.RESOURCES:
            raise ValidationError("compatibility query finding resource filter is unsupported")
        self.identity = _text(identity, "compatibility query identity", 4096)
        self.reason = _label(reason, "compatibility query reason", required=False)
        if self.reason and self.reason not in compatibility_model.REASON_CODES:
            raise ValidationError("compatibility query reason filter is unsupported")
        self.text = _text(text, "compatibility query text", MAX_TEXT)
        self.offset = _count(offset, "compatibility query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "compatibility query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "compatibility query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "compatibility query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "compatibility query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "compatibility query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "compatibility query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityQueryRow) else DownloadedDataProfileContractCompatibilityQueryRow.from_mapping(item) for item in _sequence(rows, "compatibility query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "compatibility query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("compatibility query version or boundary is not current")
        if self.total_count < self.matched_count or self.matched_count < self.returned_count or self.returned_count != len(self.rows) or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("compatibility query counts or truncation do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)) or any(item.resource not in self.resources for item in self.rows):
            raise ValidationError("compatibility query row order or resource selection is invalid")
        if self.outcome and any(item.outcome != self.outcome for item in self.rows if item.resource == "findings"):
            raise ValidationError("compatibility query outcome filter does not replay")
        if self.resource and any(item.resource != self.resource for item in self.rows if item.resource == "findings"):
            raise ValidationError("compatibility query finding resource filter does not replay")
        if self.reason and any(self.reason not in item.reason_codes for item in self.rows if item.resource == "findings"):
            raise ValidationError("compatibility query reason filter does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("compatibility query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("compatibility query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_address": self.gate_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "outcome": self.outcome, "resource": self.resource, "identity": self.identity, "reason": self.reason, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityQuery:
        value = _mapping(value, "compatibility query")
        _strict(value, set(cls.FIELDS), "compatibility query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _summary_row(gate: compatibility_model.DownloadedDataProfileContractCompatibilityGate) -> DownloadedDataProfileContractCompatibilityQueryRow:
    body = {"ordinal": 1, "resource": "summary", "identity": "summary", "change": "summary", "outcome": "summary", "reason_codes": (), "left_address": gate.diff_address, "right_address": gate.policy.content_address, "diff_item_address": "", "finding_address": "", "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityQueryRow(**(body | {"content_address": address_row(provisional)}))


def _finding_row(item: compatibility_model.DownloadedDataProfileContractCompatibilityFinding, ordinal: int) -> DownloadedDataProfileContractCompatibilityQueryRow:
    body = {"ordinal": ordinal, "resource": "findings", "identity": item.identity, "change": item.change, "outcome": item.outcome, "reason_codes": item.reason_codes, "left_address": item.left_address, "right_address": item.right_address, "diff_item_address": item.diff_item_address, "finding_address": item.content_address, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityQueryRow(**(body | {"content_address": address_row(provisional)}))


def _readdress(row: DownloadedDataProfileContractCompatibilityQueryRow, ordinal: int) -> DownloadedDataProfileContractCompatibilityQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityQueryRow(**(body | {"content_address": address_row(provisional)}))


def _matches(row: DownloadedDataProfileContractCompatibilityQueryRow, query: DownloadedDataProfileContractCompatibilityQuery) -> bool:
    if row.resource not in query.resources:
        return False
    if row.resource == "summary":
        return not any((query.outcome, query.resource, query.identity, query.reason)) and (not query.text or query.text.casefold() in "summary summary".casefold())
    if query.outcome and row.outcome != query.outcome:
        return False
    if query.resource and row.resource != "findings":
        return False
    if query.identity and query.identity.casefold() not in row.identity.casefold():
        return False
    if query.reason and query.reason not in row.reason_codes:
        return False
    haystack = " ".join((row.resource, row.identity, row.change, row.outcome, *row.reason_codes)).casefold()
    return not query.text or query.text.casefold() in haystack


def query_gate(value: compatibility_model.DownloadedDataProfileContractCompatibilityGate, *, resources: Sequence[str] = RESOURCES, outcome: str = "", resource: str = "", identity: str = "", reason: str = "", text: str = "", offset: int = 0, limit: int = 100) -> DownloadedDataProfileContractCompatibilityQuery:
    if not isinstance(value, compatibility_model.DownloadedDataProfileContractCompatibilityGate):
        raise ValidationError("compatibility query requires a typed gate")
    provisional = DownloadedDataProfileContractCompatibilityQuery(value.content_address, VERSION, BOUNDARY, resources, outcome, resource, identity, reason, text, offset, limit, 0, 0, 0, 0, False, (), QUERY_PREFIX + ":pending")
    rows: list[DownloadedDataProfileContractCompatibilityQueryRow] = []
    if "summary" in provisional.resources:
        rows.append(_summary_row(value))
    if "findings" in provisional.resources:
        rows.extend(_finding_row(item, len(rows) + 1) for item in value.findings)
    matched = tuple(row for row in rows if _matches(row, provisional))
    selected = tuple(_readdress(row, ordinal) for ordinal, row in enumerate(matched[offset:offset + limit], 1))
    body = {"gate_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": provisional.resources, "outcome": provisional.outcome, "resource": provisional.resource, "identity": provisional.identity, "reason": provisional.reason, "text": provisional.text, "offset": provisional.offset, "limit": provisional.limit, "total_count": len(rows), "matched_count": len(matched), "returned_count": len(selected), "next_offset": provisional.offset + len(selected), "truncated": provisional.offset + len(selected) < len(matched), "rows": selected, "content_address": QUERY_PREFIX + ":pending"}
    final = DownloadedDataProfileContractCompatibilityQuery(**body)
    return DownloadedDataProfileContractCompatibilityQuery(**(body | {"content_address": address_query(final)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityQuery:
    return DownloadedDataProfileContractCompatibilityQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityQuery) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityQuery) -> str:
    value = DownloadedDataProfileContractCompatibilityQuery.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(";".join(item.reason_codes) if field == "reason_codes" else item.to_dict()[field] for field in ROW_FIELDS) for item in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityQuery) -> str:
    value = DownloadedDataProfileContractCompatibilityQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Query", "", f"- Gate: `{value.gate_address}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Truncated: `{value.truncated}`", f"- Address: `{value.content_address}`", "", "| # | identity | change | outcome | reasons |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.identity}` | `{row.change}` | `{row.outcome}` | {', '.join(row.reason_codes)} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "change": {"type": "string"}, "outcome": {"type": "string"}, "reason_codes": {"type": "array", "items": {"enum": list(compatibility_model.REASON_CODES)}}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "diff_item_address": {"type": "string"}, "finding_address": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"gate_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "outcome": {"type": "string"}, "resource": {"type": "string"}, "identity": {"type": "string"}, "reason": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "outcomes": compatibility_model.OUTCOMES, "reasons": compatibility_model.REASON_CODES, "operations": ("query_gate", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "DownloadedDataProfileContractCompatibilityQuery", "DownloadedDataProfileContractCompatibilityQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_gate", "query_json", "query_schema", "render_query_markdown", "row_schema"]
