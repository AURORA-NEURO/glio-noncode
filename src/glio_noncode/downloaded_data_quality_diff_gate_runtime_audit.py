"""Independent closure audit for downloaded-data quality diff gate runtimes."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-runtime-audit-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_runtime_audit"
AUDIT_PREFIX = "glio-noncode-download-quality-diff-gate-runtime-audit"
CHECK_IDS = (
    "exact-fields", "public-boundary", "version-boundary", "diff-lineage",
    "gate-lineage", "component-addresses", "query-lineage", "aggregate-conservation",
    "manifest", "gate-audit-linkage", "query-audit-linkage", "gate-accepted",
    "gate-audit-accepted", "query-audit-accepted", "query-completeness",
    "readiness", "state", "nested-addresses", "mapping-round-trip",
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


class DownloadedDataQualityDiffGateRuntimeAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality diff gate runtime audit check ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "quality diff gate runtime audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("quality diff gate runtime audit check ID is unsupported")
        self.passed = _bool(passed, "quality diff gate runtime audit result")
        self.detail = _text(detail, "quality diff gate runtime audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "quality diff gate runtime audit evidence address") for item in _sequence(evidence_addresses, "quality diff gate runtime audit evidence", 24))
        self.content_address = _address(content_address, "quality diff gate runtime audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "quality diff gate runtime audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("quality diff gate runtime audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("quality diff gate runtime audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRuntimeAuditCheck":
        value = _mapping(value, "downloaded data quality diff gate runtime audit check")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate runtime audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataQualityDiffGateRuntimeAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataQualityDiffGateRuntimeAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, runtime_address: str, checks: Sequence[DownloadedDataQualityDiffGateRuntimeAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "quality diff gate runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataQualityDiffGateRuntimeAuditCheck) else DownloadedDataQualityDiffGateRuntimeAuditCheck.from_mapping(item) for item in _sequence(checks, "quality diff gate runtime audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "quality diff gate runtime audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "quality diff gate runtime audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "quality diff gate runtime audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "quality diff gate runtime audit acceptance")
        self.content_address = _address(content_address, "quality diff gate runtime audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff gate runtime audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("quality diff gate runtime audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("quality diff gate runtime audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRuntimeAudit":
        value = _mapping(value, "downloaded data quality diff gate runtime audit")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate runtime audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataQualityDiffGateRuntimeAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataQualityDiffGateRuntimeAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:24]}
    provisional = DownloadedDataQualityDiffGateRuntimeAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataQualityDiffGateRuntimeAuditCheck(**body, content_address=address_check(provisional))


def audit_runtime(value: runtime_model.DownloadedDataQualityDiffGateRuntime) -> DownloadedDataQualityDiffGateRuntimeAudit:
    """Recompute gate-runtime closure without trusting readiness projections."""

    if not isinstance(value, runtime_model.DownloadedDataQualityDiffGateRuntime):
        raise ValidationError("quality diff gate runtime audit requires a typed runtime")
    evidence = (value.content_address, value.gate_address, value.query_address)
    checks = (
        _check(1, "exact-fields", set(value.to_dict()) == set(runtime_model.RUNTIME_FIELDS), "runtime exposes exactly its declared public fields", evidence),
        _check(2, "public-boundary", _public(value.to_dict()), "runtime and nested components contain no forbidden attribution keys", evidence),
        _check(3, "version-boundary", value.version == runtime_model.VERSION and value.boundary == runtime_model.BOUNDARY, "runtime version and boundary are current", evidence),
        _check(4, "diff-lineage", value.diff_address == value.gate.diff_address == value.gate.diff.content_address, "runtime retains the diff lineage through the gate", (value.diff_address,)),
        _check(5, "gate-lineage", value.gate_address == value.gate.content_address, "runtime retains the gate address", (value.gate_address,)),
        _check(6, "component-addresses", (value.audit_address, value.query_address, value.query_audit_address) == (value.audit.content_address, value.query.content_address, value.query_audit.content_address), "runtime component addresses match nested artifacts", evidence),
        _check(7, "query-lineage", value.query.gate_address == value.gate_address and value.query_audit.query_address == value.query_address, "query components retain runtime lineage", evidence),
        _check(8, "aggregate-conservation", (value.finding_count, value.safe_count, value.review_count, value.blocked_count) == (value.gate.finding_count, value.gate.safe_count, value.gate.review_count, value.gate.blocked_count), "runtime counters conserve gate findings", evidence),
        _check(9, "manifest", value.manifest.runtime_id == value.runtime_id and value.manifest.files == runtime_model.FILES and len(value.manifest.artifact_addresses) == len(runtime_model.MANIFEST_ARTIFACT_FILES), "manifest retains the exact runtime file set", (value.manifest.content_address,)),
        _check(10, "gate-audit-linkage", value.audit.gate_address == value.gate_address, "gate audit is linked to the runtime gate", (value.audit.content_address, value.gate_address)),
        _check(11, "query-audit-linkage", value.query_audit.query_address == value.query_address, "query audit is linked to the runtime query", (value.query_audit.content_address, value.query_address)),
        _check(12, "gate-accepted", value.gate.accepted == (value.gate.decision == "promote"), "gate acceptance matches its release decision", (value.gate.content_address,)),
        _check(13, "gate-audit-accepted", value.audit.accepted, "independent gate audit is accepted", (value.audit.content_address,)),
        _check(14, "query-audit-accepted", value.query_audit.accepted, "independent gate-query audit is accepted", (value.query_audit.content_address,)),
        _check(15, "query-completeness", value.query_returned_count == value.query.returned_count and value.query_truncated == value.query.truncated and not value.query_truncated, "runtime retains a complete bounded finding query", (value.query.content_address,)),
        _check(16, "readiness", value.accepted == (value.gate.accepted and value.audit.accepted and value.query_audit.accepted and not value.query.truncated) and value.release_ready == value.accepted, "runtime readiness replays independent closure acceptance", evidence),
        _check(17, "state", (value.state == "complete") == value.release_ready, "runtime state replays release readiness", evidence),
        _check(18, "nested-addresses", runtime_model.address_runtime(value) == value.content_address and runtime_model.address_manifest(value.manifest) == value.manifest.content_address, "runtime and manifest addresses replay", evidence),
        _check(19, "mapping-round-trip", runtime_model.runtime_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "typed runtime mapping round-trips without projection drift", evidence),
    )
    body = {"runtime_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataQualityDiffGateRuntimeAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateRuntimeAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRuntimeAudit:
    return DownloadedDataQualityDiffGateRuntimeAudit.from_mapping(value)


def audit_json(value: DownloadedDataQualityDiffGateRuntimeAudit) -> str:
    return canonical_json(DownloadedDataQualityDiffGateRuntimeAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataQualityDiffGateRuntimeAudit) -> str:
    value = DownloadedDataQualityDiffGateRuntimeAudit.from_mapping(value.to_dict())
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataQualityDiffGateRuntimeAudit) -> str:
    value = DownloadedDataQualityDiffGateRuntimeAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Runtime Audit", "", f"- Runtime: `{value.runtime_address}`", f"- Accepted: `{value.accepted}`", f"- Passed: `{value.passed_count}/{value.check_count}`", "", "| ordinal | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate runtime audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate runtime audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"runtime_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_runtime", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown")}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataQualityDiffGateRuntimeAudit", "DownloadedDataQualityDiffGateRuntimeAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
