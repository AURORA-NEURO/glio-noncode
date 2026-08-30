"""Independent assurance for downloaded-data contract runtime closures."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-runtime-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_runtime_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-runtime-audit"
CHECK_IDS = (
    "version",
    "boundary",
    "manifest-files",
    "manifest-address",
    "batch-linkage",
    "contract-audit",
    "query-linkage",
    "query-audit",
    "aggregate-state",
    "contract-state",
    "release-readiness",
    "runtime-address",
    "mapping-round-trip",
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


class DownloadedDataProfileContractRuntimeAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "contract runtime audit ordinal", len(CHECK_IDS))
        if not self.ordinal:
            raise ValidationError("contract runtime audit ordinal must be positive")
        self.check_id = _label(check_id, "contract runtime audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("contract runtime audit check ID is unsupported")
        self.passed = _bool(passed, "contract runtime audit result")
        self.detail = _text(detail, "contract runtime audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "contract runtime audit evidence address") for item in _sequence(evidence_addresses, "contract runtime audit evidence", 16))
        self.content_address = _address(content_address, "contract runtime audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "contract runtime audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("contract runtime audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("contract runtime audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractRuntimeAuditCheck:
        value = _mapping(value, "contract runtime audit check")
        _strict(value, set(cls.FIELDS), "contract runtime audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractRuntimeAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataProfileContractRuntimeAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, runtime_address: str, checks: Sequence[DownloadedDataProfileContractRuntimeAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "contract runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractRuntimeAuditCheck) else DownloadedDataProfileContractRuntimeAuditCheck.from_mapping(item) for item in _sequence(checks, "contract runtime audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "contract runtime audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "contract runtime audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "contract runtime audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "contract runtime audit acceptance")
        self.content_address = _address(content_address, "contract runtime audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract runtime audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("contract runtime audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("contract runtime audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    def check(self, check_id: str) -> DownloadedDataProfileContractRuntimeAuditCheck:
        check_id = _label(check_id, "contract runtime audit lookup ID")
        for item in self.checks:
            if item.check_id == check_id:
                return item
        raise ValidationError("contract runtime audit check was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractRuntimeAudit:
        value = _mapping(value, "contract runtime audit")
        _strict(value, set(cls.FIELDS), "contract runtime audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractRuntimeAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractRuntimeAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:16]}
    provisional = DownloadedDataProfileContractRuntimeAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataProfileContractRuntimeAuditCheck(**body, content_address=address_check(provisional))


def audit_runtime(value: runtime_model.DownloadedDataProfileContractRuntime) -> DownloadedDataProfileContractRuntimeAudit:
    """Audit contract runtime links and derived readiness without source values."""

    if not isinstance(value, runtime_model.DownloadedDataProfileContractRuntime):
        raise ValidationError("contract runtime audit requires a typed runtime")
    evidence = (value.content_address, value.manifest.content_address, value.contract_address, value.batch_address)
    checks = (
        _check(1, "version", value.version == runtime_model.VERSION, "contract runtime version is current", evidence),
        _check(2, "boundary", value.boundary == runtime_model.BOUNDARY, "contract runtime boundary is public", evidence),
        _check(3, "manifest-files", value.manifest.files == runtime_model.FILES and len(value.manifest.artifact_addresses) == len(runtime_model.MANIFEST_ARTIFACT_FILES), "manifest closes the exact contract runtime file set", (value.manifest.content_address,)),
        _check(4, "manifest-address", runtime_model.address_manifest(value.manifest) == value.manifest.content_address, "contract runtime manifest address replays", (value.manifest.content_address,)),
        _check(5, "batch-linkage", value.batch_address.startswith(ingestion_model.INGEST_PREFIX + ":"), "contract runtime retains the ingestion batch linkage", (value.batch_address, value.profile_address)),
        _check(6, "contract-audit", value.audit.contract_address == value.contract_address and value.audit.accepted, "contract audit closes the inferred contract", (value.audit_address, value.contract_address)),
        _check(7, "query-linkage", value.query.contract_address == value.contract_address and value.query_address == value.query.content_address, "contract query links to the same contract", (value.query_address, value.contract_address)),
        _check(8, "query-audit", value.query_audit.query_address == value.query_address and value.query_audit.accepted, "contract query audit closes the query", (value.query_audit_address, value.query_address)),
        _check(9, "aggregate-state", (value.record_count, value.member_count, value.field_count) == (value.contract.record_count, value.contract.member_count, value.contract.field_count), "runtime record, member, and field aggregates replay the contract", evidence),
        _check(10, "contract-state", (value.required_field_count, value.optional_field_count, value.sparse_field_count, value.mixed_type_field_count) == (value.contract.required_field_count, value.contract.optional_field_count, value.contract.sparse_field_count, value.contract.mixed_type_field_count), "runtime schema-state aggregates replay the contract", evidence),
        _check(11, "release-readiness", value.accepted == (value.audit.accepted and value.query_audit.accepted) and value.release_ready == value.accepted and value.state == ("complete" if value.release_ready else "incomplete"), "runtime readiness is derived from accepted component closure", evidence),
        _check(12, "runtime-address", runtime_model.address_runtime(value) == value.content_address, "contract runtime address replays", (value.content_address,)),
        _check(13, "mapping-round-trip", runtime_model.runtime_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "contract runtime mapping round-trips without projection drift", evidence),
    )
    body = {"runtime_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataProfileContractRuntimeAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractRuntimeAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractRuntimeAudit:
    return DownloadedDataProfileContractRuntimeAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractRuntimeAudit) -> str:
    return canonical_json(DownloadedDataProfileContractRuntimeAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractRuntimeAudit) -> str:
    value = DownloadedDataProfileContractRuntimeAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractRuntimeAudit) -> str:
    value = DownloadedDataProfileContractRuntimeAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Runtime Audit", "", f"- Runtime: `{value.runtime_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract runtime audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract runtime audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"runtime_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_runtime", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": len(CHECK_IDS)}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataProfileContractRuntimeAudit", "DownloadedDataProfileContractRuntimeAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
