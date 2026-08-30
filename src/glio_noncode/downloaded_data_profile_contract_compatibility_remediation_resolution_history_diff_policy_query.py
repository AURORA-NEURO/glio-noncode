"""Bounded queries over history-diff policy evaluations."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy as policy_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "rules")
QUERY_FIELDS = ("evaluation_address", "version", "boundary", "resources", "resource", "rule_id", "passed", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")
ROW_FIELDS = ("ordinal", "resource", "identity", "rule_id", "passed", "observed", "limit", "detail", "content_address")
MAX_TOTAL_COUNT = policy_model.MAX_RULES + 1
MAX_LIMIT = 100


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
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


def _optional_bool(value: Any, field: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean or null")
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


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, rule_id: str, passed: bool, observed: str, limit: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff policy query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "history diff policy query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("history diff policy query row resource is unsupported")
        self.identity = _label(identity, "history diff policy query row identity")
        self.rule_id = _label(rule_id, "history diff policy query row rule ID", required=False)
        if self.resource == "summary" and self.rule_id:
            raise ValidationError("history diff policy query summary row has a rule ID")
        if self.resource == "rules" and self.rule_id not in policy_model.RULE_IDS:
            raise ValidationError("history diff policy query rule ID is unsupported")
        self.passed = _bool(passed, "history diff policy query row result")
        self.observed = _text(observed, "history diff policy query row observed value", 1024)
        self.limit = _text(limit, "history diff policy query row limit", 1024)
        self.detail = _text(detail, "history diff policy query row detail", 1024)
        self.content_address = _address(content_address, "history diff policy query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and not self.observed:
            raise ValidationError("history diff policy query summary row requires an observation")
        if not _public(self.to_dict()):
            raise ValidationError("history diff policy query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("history diff policy query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow:
        value = _mapping(value, "history diff policy query row")
        _strict(value, set(cls.FIELDS), "history diff policy query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow):
        raise ValidationError("history diff policy query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, evaluation_address: str, version: str, boundary: str, resources: Sequence[str], resource: str, rule_id: str, passed: bool | None, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.evaluation_address = _address(evaluation_address, "history diff policy query evaluation address", policy_model.EVALUATION_PREFIX)
        self.version = _text(version, "history diff policy query version")
        self.boundary = _text(boundary, "history diff policy query boundary", 512)
        self.resources = _ordered_labels(resources, "history diff policy query resources", RESOURCES)
        self.resource = _label(resource, "history diff policy query resource filter", required=False)
        if self.resource and self.resource not in RESOURCES:
            raise ValidationError("history diff policy query resource filter is unsupported")
        self.rule_id = _label(rule_id, "history diff policy query rule filter", required=False)
        if self.rule_id and self.rule_id not in policy_model.RULE_IDS:
            raise ValidationError("history diff policy query rule filter is unsupported")
        self.passed = _optional_bool(passed, "history diff policy query passed filter")
        self.text = _text(text, "history diff policy query text", 1024, required=False)
        self.offset = _count(offset, "history diff policy query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "history diff policy query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "history diff policy query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "history diff policy query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "history diff policy query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "history diff policy query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "history diff policy query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow.from_mapping(item) for item in _sequence(rows, "history diff policy query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "history diff policy query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history diff policy query version or boundary is not current")
        if len(self.rows) != self.returned_count or self.returned_count > self.limit or tuple(row.ordinal for row in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("history diff policy query row order does not replay")
        if self.matched_count > self.total_count or self.returned_count > self.matched_count or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("history diff policy query counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff policy query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("history diff policy query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"evaluation_address": self.evaluation_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "resource": self.resource, "rule_id": self.rule_id, "passed": self.passed, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(row.to_dict() for row in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery:
        value = _mapping(value, "history diff policy query")
        _strict(value, set(cls.FIELDS), "history diff policy query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery):
        raise ValidationError("history diff policy query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _summary_row(value: policy_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow:
    body = {"ordinal": 1, "resource": "summary", "identity": value.evaluation_id, "rule_id": "", "passed": value.accepted, "observed": value.state, "limit": value.decision, "detail": f"{value.passed_rule_count}/{value.rule_count} policy rules pass", "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow(**(body | {"content_address": address_row(provisional)}))


def _rule_row(value: policy_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow:
    body = {"ordinal": ordinal, "resource": "rules", "identity": value.rule_id, "rule_id": value.rule_id, "passed": value.passed, "observed": value.observed, "limit": value.limit, "detail": value.detail, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow(**(body | {"content_address": address_row(provisional)}))


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow, query: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery) -> bool:
    if query.resource and row.resource != query.resource:
        return False
    if query.rule_id and row.rule_id != query.rule_id:
        return False
    if query.passed is not None and row.passed != query.passed:
        return False
    haystack = " ".join((row.identity, row.rule_id, str(row.passed).lower(), row.observed, row.limit, row.detail)).casefold()
    return not query.text or query.text.casefold() in haystack


def query_evaluation(value: policy_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation, *, resources: Sequence[str] = RESOURCES, resource: str = "", rule_id: str = "", passed: bool | None = None, text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery:
    if not isinstance(value, policy_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation):
        raise ValidationError("history diff policy query requires a typed evaluation")
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery(value.content_address, VERSION, BOUNDARY, resources, resource, rule_id, passed, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    rows = tuple([_summary_row(value)] if "summary" in provisional.resources else []) + tuple(_rule_row(item, ordinal) for ordinal, item in enumerate(value.rules, 2) if "rules" in provisional.resources)
    matched = tuple(item for item in rows if _matches(item, provisional))
    selected = tuple(_readdress(item, ordinal) for ordinal, item in enumerate(matched[offset : offset + limit], 1))
    body = {"evaluation_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": provisional.resources, "resource": provisional.resource, "rule_id": provisional.rule_id, "passed": provisional.passed, "text": provisional.text, "offset": provisional.offset, "limit": provisional.limit, "total_count": len(rows), "matched_count": len(matched), "returned_count": len(selected), "next_offset": provisional.offset + len(selected), "truncated": provisional.offset + len(selected) < len(matched), "rows": selected, "content_address": QUERY_PREFIX + ":pending"}
    provisional_result = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery(**(body | {"content_address": address_query(provisional_result)}))


def _readdress(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in ROW_FIELDS) for item in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Diff Policy Query", "", f"- Evaluation: `{value.evaluation_address}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Truncated: `{value.truncated}`", f"- Address: `{value.content_address}`", "", "| # | resource | identity | passed | observed |", "| ---: | --- | --- | ---: | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.identity}` | `{row.passed}` | `{row.observed}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "rule_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "limit": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"evaluation_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "resource": {"type": "string"}, "rule_id": {"type": "string"}, "passed": {"type": ["boolean", "null"]}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "rule_ids": policy_model.RULE_IDS, "operations": ("query_evaluation", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_evaluation", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema"]
