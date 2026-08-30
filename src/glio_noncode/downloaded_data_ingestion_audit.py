"""Independent structural assurance for downloaded-data ingestion batches."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-ingestion-audit-v1"
BOUNDARY = "public_downloaded_data_ingestion_audit"
AUDIT_PREFIX = "glio-noncode-download-ingest-audit"
CHECK_IDS = (
    "version",
    "boundary",
    "source-address",
    "catalog-address",
    "selection-link",
    "member-count",
    "record-count",
    "overflow-state",
    "record-order",
    "lineage-links",
    "member-ordinals",
    "record-ids",
    "record-addresses",
    "value-sizes",
    "public-boundary",
    "batch-address",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("batch_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
FORBIDDEN_PUBLIC_KEYS = ingestion_model.FORBIDDEN_PUBLIC_KEYS


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or (required and not value)
        or any(ord(char) < 32 and char not in "\n\t" for char in value)
    ):
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
        return all(str(key).casefold() not in FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataIngestionAuditCheck:
    """One independently recomputable ingestion assurance finding."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "ingestion audit check ordinal", len(CHECK_IDS))
        if self.ordinal == 0:
            raise ValidationError("ingestion audit check ordinal must be positive")
        self.check_id = _label(check_id, "ingestion audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("ingestion audit check ID is unsupported")
        self.passed = _bool(passed, "ingestion audit result")
        self.detail = _text(detail, "ingestion audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "ingestion audit evidence address") for item in _sequence(evidence_addresses, "ingestion audit evidence", 16))
        self.content_address = _address(content_address, "ingestion audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "ingestion audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("ingestion audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("ingestion audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionAuditCheck:
        value = _mapping(value, "downloaded ingestion audit check")
        _strict(value, set(cls.FIELDS), "downloaded ingestion audit check")
        return cls(value["ordinal"], value["check_id"], value["passed"], value["detail"], value["evidence_addresses"], value["content_address"])


def address_check(value: DownloadedDataIngestionAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataIngestionAudit:
    """Fixed-size, content-addressed assurance over one ingestion batch."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, batch_address: str, checks: Sequence[DownloadedDataIngestionAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.batch_address = _address(batch_address, "ingestion audit batch address", ingestion_model.INGEST_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataIngestionAuditCheck) else DownloadedDataIngestionAuditCheck.from_mapping(item) for item in _sequence(checks, "ingestion audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "ingestion audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "ingestion audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "ingestion audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "ingestion audit acceptance")
        self.content_address = _address(content_address, "ingestion audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "ingestion audit address")
        self._validate()

    def _validate(self) -> None:
        if (
            self.check_count != len(self.checks)
            or self.check_count != len(CHECK_IDS)
            or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1))
            or tuple(item.check_id for item in self.checks) != CHECK_IDS
            or self.passed_count != sum(item.passed for item in self.checks)
            or self.failed_count != sum(not item.passed for item in self.checks)
            or self.accepted != (self.failed_count == 0)
            or not _public(self.to_dict())
        ):
            raise ValidationError("ingestion audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("ingestion audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"batch_address": self.batch_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionAudit:
        value = _mapping(value, "downloaded ingestion audit")
        _strict(value, set(cls.FIELDS), "downloaded ingestion audit")
        return cls(value["batch_address"], value["checks"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: DownloadedDataIngestionAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataIngestionAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)}
    provisional = DownloadedDataIngestionAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataIngestionAuditCheck(**body, content_address=address_check(provisional))


def audit_ingest(value: ingestion_model.DownloadedDataIngestBatch) -> DownloadedDataIngestionAudit:
    if not isinstance(value, ingestion_model.DownloadedDataIngestBatch):
        raise ValidationError("ingestion audit requires a typed ingestion batch")
    evidence = (value.content_address, value.catalog_address, value.selection.content_address)
    checks = (
        _check(1, "version", value.version == ingestion_model.VERSION, "ingestion version is current", evidence),
        _check(2, "boundary", value.boundary == ingestion_model.BOUNDARY, "ingestion boundary is public", evidence),
        _check(3, "source-address", value.source_address.startswith(ingestion_model.SOURCE_PREFIX + ":"), "source bytes are content-addressed", (value.source_address,)),
        _check(4, "catalog-address", value.catalog_address.startswith("glio-noncode-download-catalog:"), "catalog lineage is retained", (value.catalog_address,)),
        _check(5, "selection-link", value.selection.catalog_address == value.catalog_address, "selection points to the catalog", (value.selection.content_address, value.catalog_address)),
        _check(6, "member-count", 0 < value.selected_member_count <= ingestion_model.MAX_SELECTED_MEMBERS, "selected member count is bounded", evidence),
        _check(7, "record-count", value.available_record_count == value.record_count + value.dropped_record_count and value.record_count == len(value.records), "record counts conserve available and emitted records", evidence),
        _check(8, "overflow-state", value.truncated == (value.dropped_record_count > 0) and value.complete == (not value.truncated), "overflow state is explicit", evidence),
        _check(9, "record-order", tuple(item.ordinal for item in value.records) == tuple(range(1, value.record_count + 1)), "records are canonically ordered", evidence),
        _check(10, "lineage-links", all(item.lineage.source_address == value.source_address and item.lineage.catalog_address == value.catalog_address and item.lineage.selection_address == value.selection.content_address for item in value.records), "every record retains batch lineage", evidence),
        _check(11, "member-ordinals", all(1 <= item.lineage.member_ordinal <= 4096 for item in value.records), "member ordinals remain bounded", evidence),
        _check(12, "record-ids", len({item.record_id for item in value.records}) == value.record_count, "record IDs are unique", evidence),
        _check(13, "record-addresses", all(ingestion_model.address_record(item) == item.content_address for item in value.records), "record addresses replay", tuple(item.content_address for item in value.records[:8])),
        _check(14, "value-sizes", all(item.value_size == len(canonical_json(item.value).encode("utf-8")) for item in value.records), "value sizes match canonical bytes", evidence),
        _check(15, "public-boundary", _public(value.to_dict()), "ingestion output contains no prohibited public keys", evidence),
        _check(16, "batch-address", ingestion_model.address_batch(value) == value.content_address, "batch address replays", (value.content_address,)),
    )
    body = {"batch_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataIngestionAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataIngestionAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataIngestionAudit:
    return DownloadedDataIngestionAudit.from_mapping(value)


def audit_json(value: DownloadedDataIngestionAudit) -> str:
    return canonical_json(DownloadedDataIngestionAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataIngestionAudit) -> str:
    value = DownloadedDataIngestionAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataIngestionAudit) -> str:
    value = DownloadedDataIngestionAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Ingestion Audit", "", f"- Batch: `{value.batch_address}`", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"batch_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_ingest", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown")}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataIngestionAudit", "DownloadedDataIngestionAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_ingest", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
