"""Independent assurance for downloaded-data runtime closures."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_catalog_audit as catalog_audit_model
from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_ingestion_query as query_model
from . import downloaded_data_ingestion_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-ingestion-runtime-audit-v1"
BOUNDARY = "public_downloaded_data_ingestion_runtime_audit"
AUDIT_PREFIX = "glio-noncode-download-ingest-runtime-audit"
CHECK_IDS = (
    "version",
    "boundary",
    "manifest-files",
    "manifest-address",
    "catalog-address",
    "catalog-audit",
    "batch-address",
    "ingestion-audit",
    "query-address",
    "query-audit",
    "aggregate-state",
    "release-readiness",
    "runtime-address",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("runtime_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


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


class DownloadedDataIngestionRuntimeAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime audit check ordinal", len(CHECK_IDS))
        if self.ordinal == 0:
            raise ValidationError("runtime audit check ordinal must be positive")
        self.check_id = _label(check_id, "runtime audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("runtime audit check ID is unsupported")
        self.passed = _bool(passed, "runtime audit result")
        self.detail = _text(detail, "runtime audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "runtime audit evidence address") for item in _sequence(evidence_addresses, "runtime audit evidence", 16))
        self.content_address = _address(content_address, "runtime audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "runtime audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("runtime audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionRuntimeAuditCheck:
        value = _mapping(value, "downloaded runtime audit check")
        _strict(value, set(cls.FIELDS), "downloaded runtime audit check")
        return cls(value["ordinal"], value["check_id"], value["passed"], value["detail"], value["evidence_addresses"], value["content_address"])


def address_check(value: DownloadedDataIngestionRuntimeAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataIngestionRuntimeAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, runtime_address: str, checks: Sequence[DownloadedDataIngestionRuntimeAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataIngestionRuntimeAuditCheck) else DownloadedDataIngestionRuntimeAuditCheck.from_mapping(item) for item in _sequence(checks, "runtime audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "runtime audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "runtime audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "runtime audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "runtime audit acceptance")
        self.content_address = _address(content_address, "runtime audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "runtime audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("runtime audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionRuntimeAudit:
        value = _mapping(value, "downloaded runtime audit")
        _strict(value, set(cls.FIELDS), "downloaded runtime audit")
        return cls(value["runtime_address"], value["checks"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: DownloadedDataIngestionRuntimeAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataIngestionRuntimeAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)}
    provisional = DownloadedDataIngestionRuntimeAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataIngestionRuntimeAuditCheck(**body, content_address=address_check(provisional))


def audit_runtime(value: runtime_model.DownloadedDataIngestionRuntime) -> DownloadedDataIngestionRuntimeAudit:
    if not isinstance(value, runtime_model.DownloadedDataIngestionRuntime):
        raise ValidationError("runtime audit requires a typed runtime")
    evidence = (value.content_address, value.manifest.content_address, value.batch_address)
    checks = (
        _check(1, "version", value.version == runtime_model.VERSION, "runtime version is current", evidence),
        _check(2, "boundary", value.boundary == runtime_model.BOUNDARY, "runtime boundary is public", evidence),
        _check(3, "manifest-files", value.manifest.files == runtime_model.FILES and len(value.manifest.artifact_addresses) == len(runtime_model.MANIFEST_ARTIFACT_FILES), "runtime manifest closes the exact file set", (value.manifest.content_address,)),
        _check(4, "manifest-address", runtime_model.address_manifest(value.manifest) == value.manifest.content_address, "runtime manifest address replays", (value.manifest.content_address,)),
        _check(5, "catalog-address", value.catalog.content_address == value.catalog_address and catalog_model_address(value.catalog) == value.catalog_address, "catalog address is retained", (value.catalog_address,)),
        _check(6, "catalog-audit", catalog_audit_model.audit_catalog(value.catalog).accepted, "catalog structural audit is accepted", (value.catalog_address,)),
        _check(7, "batch-address", ingestion_model.address_batch(value.batch) == value.batch_address, "ingestion batch address replays", (value.batch_address,)),
        _check(8, "ingestion-audit", value.audit.accepted and value.audit.batch_address == value.batch_address, "ingestion audit closes the batch", (value.audit_address, value.batch_address)),
        _check(9, "query-address", query_model.address_query(value.query) == value.query_address and value.query.batch_address == value.batch_address, "query address and batch link replay", (value.query_address, value.batch_address)),
        _check(10, "query-audit", value.query_audit.accepted and value.query_audit.query_address == value.query_address, "query audit closes the query", (value.query_audit_address, value.query_address)),
        _check(11, "aggregate-state", value.record_count == value.batch.record_count and value.available_record_count == value.batch.available_record_count and value.selected_member_count == value.batch.selected_member_count, "runtime aggregates replay the batch", evidence),
        _check(12, "release-readiness", value.accepted == (value.audit.accepted and value.query_audit.accepted) and value.release_ready == (value.accepted and value.complete), "runtime readiness is derived from accepted closure", evidence),
        _check(13, "runtime-address", runtime_model.address_runtime(value) == value.content_address, "runtime address replays", (value.content_address,)),
    )
    body = {"runtime_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataIngestionRuntimeAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataIngestionRuntimeAudit(**body, content_address=address_audit(provisional))


def catalog_model_address(value: Any) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix="glio-noncode-download-catalog")


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataIngestionRuntimeAudit:
    return DownloadedDataIngestionRuntimeAudit.from_mapping(value)


def audit_json(value: DownloadedDataIngestionRuntimeAudit) -> str:
    return canonical_json(DownloadedDataIngestionRuntimeAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataIngestionRuntimeAudit) -> str:
    value = DownloadedDataIngestionRuntimeAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataIngestionRuntimeAudit) -> str:
    value = DownloadedDataIngestionRuntimeAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Ingestion Runtime Audit", "", f"- Runtime: `{value.runtime_address}`", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion runtime audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion runtime audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"runtime_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_runtime", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown")}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataIngestionRuntimeAudit", "DownloadedDataIngestionRuntimeAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
