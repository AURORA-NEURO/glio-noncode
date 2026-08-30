"""Bounded queries over portable policy-review packages."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy as policy_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package as package_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "policy-audit", "policy-rules", "runtime-audit", "runtime-checks")
QUERY_FIELDS = ("package_address", "version", "boundary", "resources", "resource", "passed", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")
ROW_FIELDS = ("ordinal", "resource", "identity", "passed", "category", "observed", "detail", "content_address")
MAX_TOTAL_COUNT = 1 + policy_model.MAX_RULES + 2 * 12 + 16
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, passed: bool, category: str, observed: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff policy package query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "history diff policy package query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("history diff policy package query row resource is unsupported")
        self.identity = _label(identity, "history diff policy package query row identity")
        self.passed = _bool(passed, "history diff policy package query row result")
        self.category = _label(category, "history diff policy package query row category")
        self.observed = _text(observed, "history diff policy package query row observed value", 1024)
        self.detail = _text(detail, "history diff policy package query row detail", 1024)
        self.content_address = _address(content_address, "history diff policy package query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("history diff policy package query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("history diff policy package query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow:
        value = _mapping(value, "history diff policy package query row")
        _strict(value, set(cls.FIELDS), "history diff policy package query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow):
        raise ValidationError("history diff policy package query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, package_address: str, version: str, boundary: str, resources: Sequence[str], resource: str, passed: bool | None, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.package_address = _address(package_address, "history diff policy package query package address", package_model.PACKAGE_PREFIX)
        self.version = _text(version, "history diff policy package query version")
        self.boundary = _text(boundary, "history diff policy package query boundary", 512)
        self.resources = _ordered_labels(resources, "history diff policy package query resources", RESOURCES)
        self.resource = _label(resource, "history diff policy package query resource", required=False)
        if self.resource and self.resource not in RESOURCES:
            raise ValidationError("history diff policy package query resource is unsupported")
        self.passed = _optional_bool(passed, "history diff policy package query passed filter")
        self.text = _text(text, "history diff policy package query text", 512, required=False)
        self.offset = _count(offset, "history diff policy package query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "history diff policy package query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "history diff policy package query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "history diff policy package query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "history diff policy package query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "history diff policy package query next offset", MAX_TOTAL_COUNT + 1)
        self.truncated = _bool(truncated, "history diff policy package query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow.from_mapping(item) for item in _sequence(rows, "history diff policy package query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "history diff policy package query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history diff policy package query version or boundary is not current")
        if self.total_count < self.matched_count or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.matched_count < self.returned_count or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("history diff policy package query counts do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)) or not _public(self.to_dict()):
            raise ValidationError("history diff policy package query rows are incomplete or non-public")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("history diff policy package query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"package_address": self.package_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "resource": self.resource, "passed": self.passed, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery:
        value = _mapping(value, "history diff policy package query")
        _strict(value, set(cls.FIELDS), "history diff policy package query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery):
        raise ValidationError("history diff policy package query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(ordinal: int, resource: str, identity: str, passed: bool, category: str, observed: str, detail: str) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "identity": identity, "passed": passed, "category": category, "observed": observed, "detail": detail, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow(**(body | {"content_address": address_row(provisional)}))


def _rows(value: package_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage, resources: Sequence[str]) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow, ...]:
    ordinal = 1
    rows: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow] = []
    if "summary" in resources:
        rows.append(_row(ordinal, "summary", value.package_id, value.accepted, "decision", value.decision, f"{value.state}|release_ready={str(value.release_ready).lower()}"))
        ordinal += 1
    if "policy-audit" in resources:
        for item in value.policy_audit.checks:
            rows.append(_row(ordinal, "policy-audit", item.check_id, item.passed, "audit-check", "pass" if item.passed else "fail", item.detail))
            ordinal += 1
    if "policy-rules" in resources:
        for item in value.runtime.evaluation.rules:
            rows.append(_row(ordinal, "policy-rules", item.rule_id, item.passed, "policy-rule", item.observed, f"limit={item.limit};{item.detail}"))
            ordinal += 1
    if "runtime-audit" in resources:
        for item in value.runtime_audit.checks:
            rows.append(_row(ordinal, "runtime-audit", item.check_id, item.passed, "audit-check", "pass" if item.passed else "fail", item.detail))
            ordinal += 1
    if "runtime-checks" in resources:
        for item in value.runtime_audit.checks:
            rows.append(_row(ordinal, "runtime-checks", item.check_id, item.passed, "runtime-check", "pass" if item.passed else "fail", item.detail))
            ordinal += 1
    return tuple(rows)


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow, query: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery) -> bool:
    if query.resource and row.resource != query.resource:
        return False
    if query.passed is not None and row.passed != query.passed:
        return False
    haystack = " ".join((row.identity, row.category, str(row.passed).lower(), row.observed, row.detail)).casefold()
    return not query.text or query.text.casefold() in haystack


def query_package(value: package_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage, *, resources: Sequence[str] = RESOURCES, resource: str = "", passed: bool | None = None, text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery:
    if not isinstance(value, package_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage):
        raise ValidationError("history diff policy package query requires a typed package")
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery(value.content_address, VERSION, BOUNDARY, resources, resource, passed, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    rows = _rows(value, provisional.resources)
    matched = tuple(item for item in rows if _matches(item, provisional))
    selected = tuple(_readdress(item, ordinal) for ordinal, item in enumerate(matched[offset : offset + limit], 1))
    body = {"package_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": provisional.resources, "resource": provisional.resource, "passed": provisional.passed, "text": provisional.text, "offset": provisional.offset, "limit": provisional.limit, "total_count": len(rows), "matched_count": len(matched), "returned_count": len(selected), "next_offset": provisional.offset + len(selected), "truncated": provisional.offset + len(selected) < len(matched), "rows": selected, "content_address": QUERY_PREFIX + ":pending"}
    result = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery(**(body | {"content_address": address_query(result)}))


def _readdress(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in ROW_FIELDS) for item in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Diff Policy Package Query", "", f"- Package: `{value.package_address}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Truncated: `{value.truncated}`", f"- Address: `{value.content_address}`", "", "| # | resource | identity | passed | category |", "| ---: | --- | --- | ---: | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.identity}` | `{row.passed}` | `{row.category}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy package query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_TOTAL_COUNT}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "passed": {"type": "boolean"}, "category": {"type": "string"}, "observed": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy package query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"package_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "resource": {"type": "string"}, "passed": {"type": ["boolean", "null"]}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "operations": ("query_package", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_package", "query_schema", "render_query_markdown", "row_schema"]
