"""Independent verification for exact compatibility remediation runtimes."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_audit as audit_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_query_audit as query_audit_model,
)
from . import downloaded_data_profile_contract_compatibility_remediation_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-runtime-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_runtime_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-runtime-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "manifest-files",
    "gate-linkage",
    "plan-linkage",
    "component-linkage",
    "audit-linkage",
    "query-linkage",
    "aggregate-replay",
    "readiness-replay",
    "artifact-addresses",
    "runtime-address",
    "public-boundary",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("runtime_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationRuntimeAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "remediation runtime audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "remediation runtime audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("remediation runtime audit check ID is unsupported")
        self.passed = _bool(passed, "remediation runtime audit check result")
        self.detail = _text(detail, "remediation runtime audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "remediation runtime audit evidence address") for item in _sequence(evidence_addresses, "remediation runtime audit evidence addresses", 16)}))
        if not self.evidence_addresses:
            raise ValidationError("remediation runtime audit checks require evidence")
        self.content_address = _address(content_address, "remediation runtime audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("remediation runtime audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("remediation runtime audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationRuntimeAuditCheck:
        value = _mapping(value, "remediation runtime audit check")
        _strict(value, set(cls.FIELDS), "remediation runtime audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationRuntimeAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, runtime_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationRuntimeAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "remediation runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationRuntimeAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationRuntimeAuditCheck.from_mapping(item) for item in _sequence(checks, "remediation runtime audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "remediation runtime audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "remediation runtime audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "remediation runtime audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "remediation runtime audit acceptance")
        self.content_address = _address(content_address, "remediation runtime audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("remediation runtime audit checks are not canonical")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("remediation runtime audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("remediation runtime audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("remediation runtime audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit:
        value = _mapping(value, "remediation runtime audit")
        _strict(value, set(cls.FIELDS), "remediation runtime audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationRuntimeAuditCheck:
    provisional = DownloadedDataProfileContractCompatibilityRemediationRuntimeAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationRuntimeAuditCheck(ordinal, check_id, passed, detail, provisional.evidence_addresses, address_check(provisional))


def audit_runtime(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationRuntime) -> DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit:
    """Recompute nested audits, links, exact manifest membership, and readiness."""

    if not isinstance(value, runtime_model.DownloadedDataProfileContractCompatibilityRemediationRuntime):
        raise ValidationError("remediation runtime audit requires a typed runtime")
    runtime = value
    plan_audit = audit_model.audit_plan(runtime.plan)
    query_audit = query_audit_model.audit_query(runtime.query)
    expected_accepted = runtime.plan.accepted and plan_audit.accepted and query_audit.accepted
    evidence = (runtime.content_address, runtime.gate_address, runtime.plan_address)
    checks = (
        _check(1, "version", runtime.version == runtime_model.VERSION, "remediation runtime uses the current version", evidence),
        _check(2, "boundary", runtime.boundary == runtime_model.BOUNDARY, "remediation runtime uses the public boundary", evidence),
        _check(3, "manifest-files", runtime.manifest.files == runtime_model.FILES and len(runtime.manifest.artifact_addresses) == len(runtime_model.MANIFEST_ARTIFACT_FILES), "runtime manifest names the exact artifact set", (runtime.manifest.content_address,)),
        _check(4, "gate-linkage", runtime.gate_id == runtime.gate.gate_id and runtime.gate_address == runtime.gate.content_address, "runtime gate identity and address replay", (runtime.gate_address,)),
        _check(5, "plan-linkage", runtime.plan_id == runtime.plan.plan_id and runtime.plan_address == runtime.plan.content_address and runtime.plan.gate_address == runtime.gate_address, "runtime plan linkage replays", (runtime.plan_address, runtime.gate_address)),
        _check(6, "component-linkage", runtime.audit.plan_address == runtime.plan_address and runtime.query.plan_address == runtime.plan_address and runtime.query_audit.query_address == runtime.query_address, "runtime component links replay", (runtime.audit_address, runtime.query_address, runtime.query_audit_address)),
        _check(7, "audit-linkage", plan_audit.accepted and runtime.audit.to_dict() == plan_audit.to_dict(), "persisted plan audit replays independently", (runtime.audit_address, plan_audit.content_address)),
        _check(8, "query-linkage", query_audit.accepted and runtime.query_audit.to_dict() == query_audit.to_dict(), "persisted query audit replays independently", (runtime.query_audit_address, query_audit.content_address)),
        _check(9, "aggregate-replay", (runtime.action_count, runtime.required_action_count) == (runtime.plan.action_count, runtime.plan.required_action_count), "runtime action aggregates replay", evidence),
        _check(10, "readiness-replay", runtime.accepted == expected_accepted and runtime.release_ready == expected_accepted and (runtime.state == "complete") == expected_accepted, "runtime readiness and state replay", evidence),
        _check(11, "artifact-addresses", tuple(runtime.manifest.artifact_addresses) == tuple((runtime.gate_address, runtime.plan_address, runtime.audit_address, runtime.query_address, runtime.query_audit_address)), "manifest artifact addresses replay in canonical order", (runtime.manifest.content_address,)),
        _check(12, "runtime-address", runtime_model.address_runtime(runtime) == runtime.content_address, "runtime content address replays", (runtime.content_address,)),
        _check(13, "public-boundary", _public(runtime.to_dict()), "runtime remains value-free and public", evidence),
        _check(14, "mapping-round-trip", runtime_model.runtime_from_mapping(runtime.to_dict()).content_address == runtime.content_address, "runtime mapping round-trip is lossless", (runtime.content_address,)),
    )
    body = {"runtime_address": runtime.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit:
    return DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Runtime Audit", "", f"- Runtime: `{value.runtime_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation runtime audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation runtime audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"runtime_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_runtime", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationRuntimeAudit", "DownloadedDataProfileContractCompatibilityRemediationRuntimeAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
