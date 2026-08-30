"""Independent conservation audit for downloaded-data contract-diff queries."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_diff as diff_model
from . import downloaded_data_profile_contract_diff_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-diff-query-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_diff_query_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-diff-query-audit"
CHECK_IDS = ("exact-fields", "public-boundary", "diff-linkage", "resource-selection", "row-order", "count-conservation", "filter-replay", "transition-replay", "content-address", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractDiffQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "contract diff query audit check ordinal", len(CHECK_IDS))
        if not self.ordinal:
            raise ValidationError("contract diff query audit check ordinal must be positive")
        self.check_id = _label(check_id, "contract diff query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("contract diff query audit check ID is unsupported")
        self.passed = _bool(passed, "contract diff query audit result")
        self.detail = _text(detail, "contract diff query audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "contract diff query audit evidence address") for item in _sequence(evidence_addresses, "contract diff query audit evidence", 16))
        self.content_address = _address(content_address, "contract diff query audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "contract diff query audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("contract diff query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("contract diff query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffQueryAuditCheck:
        value = _mapping(value, "downloaded data profile contract diff query audit check")
        _strict(value, set(cls.FIELDS), "downloaded data profile contract diff query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractDiffQueryAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataProfileContractDiffQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: Sequence[DownloadedDataProfileContractDiffQueryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "contract diff query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractDiffQueryAuditCheck) else DownloadedDataProfileContractDiffQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "contract diff query audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "contract diff query audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "contract diff query audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "contract diff query audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "contract diff query audit acceptance")
        self.content_address = _address(content_address, "contract diff query audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract diff query audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("contract diff query audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("contract diff query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffQueryAudit:
        value = _mapping(value, "downloaded data profile contract diff query audit")
        _strict(value, set(cls.FIELDS), "downloaded data profile contract diff query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractDiffQueryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractDiffQueryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:16]}
    provisional = DownloadedDataProfileContractDiffQueryAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataProfileContractDiffQueryAuditCheck(**body, content_address=address_check(provisional))


def audit_query(value: query_model.DownloadedDataProfileContractDiffQuery) -> DownloadedDataProfileContractDiffQueryAudit:
    if not isinstance(value, query_model.DownloadedDataProfileContractDiffQuery):
        raise ValidationError("contract diff query audit requires a typed query")
    checks = (
        _check(1, "exact-fields", set(value.to_dict()) == set(query_model.QUERY_FIELDS), "query exposes exactly its declared public fields", (value.content_address,)),
        _check(2, "public-boundary", _public(value.to_dict()), "query rows contain no forbidden attribution keys", (value.content_address,)),
        _check(3, "diff-linkage", value.diff_address.startswith(diff_model.DIFF_PREFIX + ":"), "query retains the diff content address", (value.diff_address,)),
        _check(4, "resource-selection", all(row.resource in value.resources for row in value.rows), "returned rows belong to the selected resource set", (value.content_address,)),
        _check(5, "row-order", tuple(row.ordinal for row in value.rows) == tuple(range(1, value.returned_count + 1)), "returned row ordinals are contiguous", (value.content_address,)),
        _check(6, "count-conservation", value.returned_count == len(value.rows) and value.matched_count >= value.returned_count and value.total_count >= value.matched_count, "query counts conserve total, matched, and returned rows", (value.content_address,)),
        _check(7, "filter-replay", all((not value.change or row.change == value.change) and (not value.attribute or value.attribute in row.changed_attributes) and (not value.identity or value.identity.casefold() in row.identity.casefold()) and (not value.text or value.text.casefold() in " ".join((row.resource, row.change, row.identity, *row.changed_attributes)).casefold()) for row in value.rows), "each returned row satisfies every active filter", (value.content_address,)),
        _check(8, "transition-replay", all(row.resource == "summary" or diff_model.DownloadedDataProfileContractDiffItem.from_mapping({"ordinal": 1, "resource": row.resource, "identity": row.identity, "change": row.change, "changed_attributes": row.changed_attributes, "left_address": row.left_address, "right_address": row.right_address, "left_snapshot": row.left_snapshot, "right_snapshot": row.right_snapshot, "content_address": diff_model.ITEM_PREFIX + ":pending"}).change == row.change for row in value.rows), "returned transition snapshots replay as typed value-free items", (value.diff_address,)),
        _check(9, "content-address", query_model.address_query(value) == value.content_address, "query content address replays", (value.content_address,)),
        _check(10, "mapping-round-trip", query_model.query_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "typed query mapping round-trips without projection drift", (value.content_address,)),
    )
    body = {"query_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataProfileContractDiffQueryAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractDiffQueryAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffQueryAudit:
    return DownloadedDataProfileContractDiffQueryAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractDiffQueryAudit) -> str:
    return canonical_json(DownloadedDataProfileContractDiffQueryAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractDiffQueryAudit) -> str:
    value = DownloadedDataProfileContractDiffQueryAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractDiffQueryAudit) -> str:
    value = DownloadedDataProfileContractDiffQueryAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Diff Query Audit", "", f"- Query: `{value.query_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract diff query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract diff query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_query", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": len(CHECK_IDS)}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataProfileContractDiffQueryAudit", "DownloadedDataProfileContractDiffQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
