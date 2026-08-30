"""Independent audit for persisted archive inspection runtimes."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-audit-v1"
BOUNDARY = runtime_model.BOUNDARY + "_audit"
AUDIT_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("runtime-address", "version-boundary", "stage-order", "stage-addresses", "stage-state", "acceptance-replay", "archive-link", "archive-audit-link", "query-link", "query-audit-link", "component-acceptance", "public-boundary", "mapping-round-trip", "summary-replay", "component-replay")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("runtime_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public content address")
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
    private_markers = ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\")
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.casefold()
        return not any(marker in lowered for marker in private_markers)
    return value is None or isinstance(value, (bool, int, float))


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAuditCheck:
    """One addressed runtime assertion."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime audit check ordinal", MAX_CHECKS)
        if self.ordinal == 0 or check_id not in CHECK_IDS:
            raise ValidationError("runtime audit check ID is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "runtime audit check result")
        self.detail = _text(detail, "runtime audit check detail", 2048)
        self.evidence_addresses = tuple(sorted({_address(item, "runtime audit evidence address") for item in _sequence(evidence_addresses, "runtime audit evidence addresses", 12)}))
        if not self.evidence_addresses:
            raise ValidationError("runtime audit checks require evidence")
        self.content_address = _address(content_address, "runtime audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("runtime audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "runtime audit check")
        _strict(value, set(cls.FIELDS), "runtime audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAuditCheck):
        raise ValidationError("runtime audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit:
    """The complete independent runtime audit."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, runtime_address: str, checks: Sequence[Any], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAuditCheck.from_mapping(item) for item in _sequence(checks, "runtime audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "runtime audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime audit acceptance")
        self.content_address = _address(content_address, "runtime audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("runtime audit counters do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit):
        raise ValidationError("runtime audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: tuple[str, ...]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAuditCheck:
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAuditCheck(ordinal, check_id, passed, detail, evidence, address_check(provisional))


def _stage_addresses(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> bool:
    expected = (value.archive_address, value.archive_address, value.archive_audit_address, value.query_address, value.query_audit_address, value.query_audit_address)
    return tuple(item.address for item in value.stages) == expected


def _stage_state(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> bool:
    return all(item.state == ("ready" if item.accepted else "blocked") for item in value.stages) and value.stages[0].accepted and value.stages[1].accepted and value.stages[3].accepted and value.stages[-1].accepted == value.accepted


def _component_replay(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> bool:
    if any(item is None for item in (value.archive, value.archive_audit, value.query, value.query_audit)):
        return True
    return value.archive.archive_id == value.archive_id and value.archive.content_address == value.archive_address and value.archive_audit.archive_address == value.archive_address and value.archive_audit.content_address == value.archive_audit_address and value.query.archive_address == value.archive_address and value.query.content_address == value.query_address and value.query_audit.query_address == value.query_address and value.query_audit.content_address == value.query_audit_address


def audit_runtime(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit:
    if not isinstance(value, runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime):
        raise ValidationError("runtime audit requires a typed runtime")
    runtime_model.verify_runtime(value)
    evidence = (value.content_address, value.archive_address, value.archive_audit_address, value.query_address, value.query_audit_address)
    private_available = all(item is not None for item in (value.archive, value.archive_audit, value.query, value.query_audit))
    components_accept = value.accepted == (value.archive_audit.accepted and value.query_audit.accepted) if private_available else value.accepted == (value.stages[2].accepted and value.stages[4].accepted)
    checks = (
        ("runtime-address", runtime_model.address_runtime(value) == value.content_address, "runtime address reproduces from the path-free receipt"),
        ("version-boundary", value.version == runtime_model.VERSION and value.boundary == runtime_model.BOUNDARY, "runtime version and public boundary are current"),
        ("stage-order", value.stage_count == len(runtime_model.STAGES) and tuple(item.stage for item in value.stages) == runtime_model.STAGES and tuple(item.ordinal for item in value.stages) == tuple(range(1, len(runtime_model.STAGES) + 1)), "runtime stages are complete and ordered"),
        ("stage-addresses", _stage_addresses(value), "each stage points at the expected component receipt"),
        ("stage-state", _stage_state(value), "stage state follows stage acceptance"),
        ("acceptance-replay", value.accepted == (value.stages[2].accepted and value.stages[4].accepted), "runtime acceptance reproduces from archive and query audits"),
        ("archive-link", value.archive is None or (value.archive.archive_id == value.archive_id and value.archive.content_address == value.archive_address), "archive identity and address are linked"),
        ("archive-audit-link", value.archive_audit is None or (value.archive_audit.archive_address == value.archive_address and value.archive_audit.content_address == value.archive_audit_address), "archive audit identity and address are linked"),
        ("query-link", value.query is None or (value.query.archive_address == value.archive_address and value.query.content_address == value.query_address), "query identity and address are linked"),
        ("query-audit-link", value.query_audit is None or (value.query_audit.query_address == value.query_address and value.query_audit.content_address == value.query_audit_address), "query audit identity and address are linked"),
        ("component-acceptance", components_accept, "component audit acceptance reproduces runtime acceptance"),
        ("public-boundary", _public(value.to_dict()), "runtime receipt contains no private path or identity fields"),
        ("mapping-round-trip", runtime_model.runtime_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "public runtime mapping round-trips"),
        ("summary-replay", tuple(item["stage"] for item in value.summary()["stage_states"]) == runtime_model.STAGES, "runtime summary preserves stage order"),
        ("component-replay", _component_replay(value), "optional materialized component receipts replay their lineage"),
    )
    findings = tuple(_check(index, check_id, passed, detail, evidence) for index, (check_id, passed, detail) in enumerate(checks, 1))
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit(value.content_address, findings, MAX_CHECKS, sum(item.passed for item in findings), sum(not item.passed for item in findings), all(item.passed for item in findings), AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit(provisional.runtime_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit:
    value = _mapping(value, "runtime audit")
    _strict(value, set(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit.FIELDS), "runtime audit")
    checks = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "runtime audit checks", MAX_CHECKS))
    result = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit(value["runtime_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])
    if address_audit(result) != result.content_address:
        raise ValidationError("runtime audit address does not replay")
    return result


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Policy Package Registry Observatory Archive Runtime Audit", "", f"- Runtime: `{value.runtime_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"runtime_address": {"type": "string", "pattern": "^" + runtime_model.RUNTIME_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent stage replay", "component lineage verification", "acceptance conservation", "path-free runtime audit", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
