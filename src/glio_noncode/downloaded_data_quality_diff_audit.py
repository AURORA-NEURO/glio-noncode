"""Independent conservation audit for downloaded-data quality diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality as quality_model
from . import downloaded_data_quality_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-audit-v1"
BOUNDARY = "public_downloaded_data_quality_diff_audit"
AUDIT_PREFIX = "glio-noncode-download-quality-diff-audit"
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "quality-linkage",
    "policy-linkage",
    "item-conservation",
    "item-order",
    "identity-conservation",
    "left-conservation",
    "right-conservation",
    "direction-conservation",
    "transition-conservation",
    "nested-addresses",
    "content-address",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataQualityDiffAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality diff audit check ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "quality diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("quality diff audit check ID is unsupported")
        self.passed = _bool(passed, "quality diff audit check result")
        self.detail = _text(detail, "quality diff audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "quality diff audit evidence address") for item in _sequence(evidence_addresses, "quality diff audit evidence", 16))
        self.content_address = _address(content_address, "quality diff audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "quality diff audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("quality diff audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("quality diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffAuditCheck":
        value = _mapping(value, "downloaded data quality diff audit check")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataQualityDiffAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataQualityDiffAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, diff_address: str, checks: Sequence[DownloadedDataQualityDiffAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_address = _address(diff_address, "quality diff audit diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataQualityDiffAuditCheck) else DownloadedDataQualityDiffAuditCheck.from_mapping(item) for item in _sequence(checks, "quality diff audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "quality diff audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "quality diff audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "quality diff audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "quality diff audit acceptance")
        self.content_address = _address(content_address, "quality diff audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("quality diff audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("quality diff audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    def check(self, check_id: str) -> DownloadedDataQualityDiffAuditCheck:
        check_id = _label(check_id, "quality diff audit lookup ID")
        for item in self.checks:
            if item.check_id == check_id:
                return item
        raise ValidationError("quality diff audit check was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffAudit":
        value = _mapping(value, "downloaded data quality diff audit")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataQualityDiffAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataQualityDiffAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:16]}
    provisional = DownloadedDataQualityDiffAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataQualityDiffAuditCheck(**body, content_address=address_check(provisional))


def audit_diff(value: diff_model.DownloadedDataQualityDiff) -> DownloadedDataQualityDiffAudit:
    """Recompute diff conservation independently of the diff builder."""

    if not isinstance(value, diff_model.DownloadedDataQualityDiff):
        raise ValidationError("quality diff audit requires a typed diff")
    counts = {change: sum(item.change == change for item in value.items) for change in diff_model.CHANGES}
    directions = {direction: sum(item.direction == direction for item in value.items) for direction in diff_model.DIRECTIONS}
    evidence = (value.content_address, value.left_quality_address, value.right_quality_address)
    checks = (
        _check(1, "exact-fields", set(value.to_dict()) == set(diff_model.DIFF_FIELDS), "diff exposes exactly its declared public fields", evidence),
        _check(2, "public-boundary", _public(value.to_dict()), "diff and nested finding snapshots contain no forbidden attribution keys", evidence),
        _check(3, "quality-linkage", value.left_quality_address.startswith(quality_model.QUALITY_PREFIX + ":") and value.right_quality_address.startswith(quality_model.QUALITY_PREFIX + ":"), "diff retains both quality decision addresses", (value.left_quality_address, value.right_quality_address)),
        _check(4, "policy-linkage", value.left_policy_address.startswith(quality_model.POLICY_PREFIX + ":") and value.right_policy_address.startswith(quality_model.POLICY_PREFIX + ":"), "diff retains both policy addresses", (value.left_policy_address, value.right_policy_address)),
        _check(5, "item-conservation", len(value.items) == sum(counts.values()), "diff items conserve every transition row", (value.content_address,)),
        _check(6, "item-order", tuple(item.ordinal for item in value.items) == tuple(range(1, len(value.items) + 1)), "diff item ordinals are contiguous", (value.content_address,)),
        _check(7, "identity-conservation", len({item.identity for item in value.items}) == len(value.items), "diff identities are unique", tuple(item.content_address for item in value.items)),
        _check(8, "left-conservation", value.left_check_count == counts["removed"] + counts["changed"] + counts["unchanged"], "left findings are conserved across transitions", evidence),
        _check(9, "right-conservation", value.right_check_count == counts["added"] + counts["changed"] + counts["unchanged"], "right findings are conserved across transitions", evidence),
        _check(10, "direction-conservation", value.improved_count == directions["improved"] and value.regressed_count == directions["regressed"], "improved and regressed transitions are conserved", evidence),
        _check(11, "transition-conservation", all(item.change in diff_model.CHANGES and item.direction in diff_model.DIRECTIONS for item in value.items), "every row has a declared transition and direction", tuple(item.content_address for item in value.items)),
        _check(12, "nested-addresses", all((not item.left_snapshot or item.left_snapshot.get("content_address") == item.left_address) and (not item.right_snapshot or item.right_snapshot.get("content_address") == item.right_address) for item in value.items), "every snapshot address matches its transition side", tuple(item.content_address for item in value.items)),
        _check(13, "content-address", diff_model.address_diff(value) == value.content_address, "diff content address replays", (value.content_address,)),
        _check(14, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "typed diff mapping round-trips without projection drift", evidence),
    )
    body = {"diff_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataQualityDiffAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataQualityDiffAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffAudit:
    return DownloadedDataQualityDiffAudit.from_mapping(value)


def audit_json(value: DownloadedDataQualityDiffAudit) -> str:
    return canonical_json(DownloadedDataQualityDiffAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataQualityDiffAudit) -> str:
    value = DownloadedDataQualityDiffAudit.from_mapping(value.to_dict())
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataQualityDiffAudit) -> str:
    value = DownloadedDataQualityDiffAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Audit", "", f"- Diff: `{value.diff_address}`", f"- Accepted: `{value.accepted}`", f"- Passed: `{value.passed_count}/{value.check_count}`", "", "| ordinal | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"diff_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_diff", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown")}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataQualityDiffAudit", "DownloadedDataQualityDiffAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_diff", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
