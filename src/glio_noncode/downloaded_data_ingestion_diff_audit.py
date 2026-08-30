"""Independent assurance for downloaded-data ingestion diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_ingestion_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-ingestion-diff-audit-v1"
BOUNDARY = "public_downloaded_data_ingestion_diff_audit"
AUDIT_PREFIX = "glio-noncode-download-ingest-diff-audit"
CHECK_IDS = (
    "version",
    "boundary",
    "left-link",
    "right-link",
    "item-order",
    "change-partition",
    "left-conservation",
    "right-conservation",
    "record-key-order",
    "item-addresses",
    "public-boundary",
    "diff-address",
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


class DownloadedDataIngestionDiffAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff audit check ordinal", len(CHECK_IDS))
        if self.ordinal == 0:
            raise ValidationError("diff audit check ordinal must be positive")
        self.check_id = _label(check_id, "diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("diff audit check ID is unsupported")
        self.passed = _bool(passed, "diff audit result")
        self.detail = _text(detail, "diff audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "diff audit evidence address") for item in _sequence(evidence_addresses, "diff audit evidence", 16))
        self.content_address = _address(content_address, "diff audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "diff audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("diff audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionDiffAuditCheck:
        value = _mapping(value, "downloaded ingestion diff audit check")
        _strict(value, set(cls.FIELDS), "downloaded ingestion diff audit check")
        return cls(value["ordinal"], value["check_id"], value["passed"], value["detail"], value["evidence_addresses"], value["content_address"])


def address_check(value: DownloadedDataIngestionDiffAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataIngestionDiffAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, diff_address: str, checks: Sequence[DownloadedDataIngestionDiffAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_address = _address(diff_address, "diff audit diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataIngestionDiffAuditCheck) else DownloadedDataIngestionDiffAuditCheck.from_mapping(item) for item in _sequence(checks, "diff audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "diff audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "diff audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "diff audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "diff audit acceptance")
        self.content_address = _address(content_address, "diff audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("diff audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("diff audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionDiffAudit:
        value = _mapping(value, "downloaded ingestion diff audit")
        _strict(value, set(cls.FIELDS), "downloaded ingestion diff audit")
        return cls(value["diff_address"], value["checks"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: DownloadedDataIngestionDiffAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataIngestionDiffAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)}
    provisional = DownloadedDataIngestionDiffAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataIngestionDiffAuditCheck(**body, content_address=address_check(provisional))


def audit_diff(value: diff_model.DownloadedDataIngestionDiff) -> DownloadedDataIngestionDiffAudit:
    if not isinstance(value, diff_model.DownloadedDataIngestionDiff):
        raise ValidationError("diff audit requires a typed diff")
    evidence = (value.content_address, value.left_batch_address, value.right_batch_address)
    checks = (
        _check(1, "version", value.version == diff_model.VERSION, "diff version is current", evidence),
        _check(2, "boundary", value.boundary == diff_model.BOUNDARY, "diff boundary is public", evidence),
        _check(3, "left-link", value.left_batch_address.startswith(ingestion_model.INGEST_PREFIX + ":"), "left batch is addressed", (value.left_batch_address,)),
        _check(4, "right-link", value.right_batch_address.startswith(ingestion_model.INGEST_PREFIX + ":"), "right batch is addressed", (value.right_batch_address,)),
        _check(5, "item-order", tuple(item.ordinal for item in value.items) == tuple(range(1, len(value.items) + 1)), "diff items are canonically ordered", evidence),
        _check(6, "change-partition", value.added_count + value.removed_count + value.changed_count + value.unchanged_count == len(value.items), "change classes partition items", evidence),
        _check(7, "left-conservation", value.left_record_count == value.removed_count + value.changed_count + value.unchanged_count, "left records are conserved", (value.left_batch_address,)),
        _check(8, "right-conservation", value.right_record_count == value.added_count + value.changed_count + value.unchanged_count, "right records are conserved", (value.right_batch_address,)),
        _check(9, "record-key-order", tuple(item.record_key for item in value.items) == tuple(sorted(item.record_key for item in value.items)), "record keys are sorted", evidence),
        _check(10, "item-addresses", all(diff_model.address_item(item) == item.content_address for item in value.items), "diff item addresses replay", tuple(item.content_address for item in value.items[:8])),
        _check(11, "public-boundary", _public(value.to_dict()), "diff output contains no prohibited public keys", evidence),
        _check(12, "diff-address", diff_model.address_diff(value) == value.content_address, "diff address replays", (value.content_address,)),
    )
    body = {"diff_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataIngestionDiffAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataIngestionDiffAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataIngestionDiffAudit:
    return DownloadedDataIngestionDiffAudit.from_mapping(value)


def audit_json(value: DownloadedDataIngestionDiffAudit) -> str:
    return canonical_json(DownloadedDataIngestionDiffAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataIngestionDiffAudit) -> str:
    value = DownloadedDataIngestionDiffAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataIngestionDiffAudit) -> str:
    value = DownloadedDataIngestionDiffAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Ingestion Diff Audit", "", f"- Diff: `{value.diff_address}`", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion diff audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion diff audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"diff_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_diff", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown")}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataIngestionDiffAudit", "DownloadedDataIngestionDiffAuditCheck", "address_audit", "address_check", "audit_csv", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
