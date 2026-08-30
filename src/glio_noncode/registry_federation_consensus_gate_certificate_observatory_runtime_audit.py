"""Independent audit for the certificate-observatory runtime envelope."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-audit-v1"
BOUNDARY = runtime_model.BOUNDARY + "_audit"
AUDIT_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit"
FINDING_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit-finding"
CHECK_IDS = ("exact-fields", "public-boundary", "observatory-link", "observatory-audit-link", "query-link", "query-audit-link", "report-link", "report-audit-link", "package-state", "stage-acceptance", "mapping-round-trip", "content-address", "path-free")


def _text(value: Any, field: str, maximum: int = runtime_model.MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.lower() not in forbidden and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return all(marker not in lowered for marker in ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\"))
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal, self.check_id = _count(ordinal, "observatory runtime audit finding ordinal", len(CHECK_IDS), positive=True), _label(check_id, "observatory runtime audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("observatory runtime audit check ID is unsupported")
        self.passed, self.observed, self.expected, self.detail = _bool(passed, "observatory runtime audit result"), _text(observed, "observatory runtime audit observed"), _text(expected, "observatory runtime audit expected"), _text(detail, "observatory runtime audit detail", required=True)
        self.content_address = _address(content_address, "observatory runtime audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("observatory runtime audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory runtime audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding:
        value = _mapping(value, "observatory runtime audit finding")
        _strict(value, set(cls.FIELDS), "observatory runtime audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit:
    FIELDS = ("runtime_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, runtime_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "audited certificate observatory runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding) for item in self.checks):
            raise ValidationError("observatory runtime audit checks must be typed")
        self.check_count, self.passed_count, self.failed_count = _count(check_count, "observatory runtime audit check count", len(CHECK_IDS), positive=True), _count(passed_count, "observatory runtime audit passed count", check_count), _count(failed_count, "observatory runtime audit failed count", check_count)
        self.accepted = _bool(accepted, "observatory runtime audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("observatory runtime audit counters are not conserved")
        self.content_address = _address(content_address, "observatory runtime audit address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("observatory runtime audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory runtime audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit:
        value = _mapping(value, "observatory runtime audit")
        _strict(value, set(cls.FIELDS), "observatory runtime audit")
        return cls(value["runtime_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_runtime(value: runtime_model.RegistryFederationConsensusGateCertificateObservatoryRuntime) -> RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit:
    value = runtime_model.verify_runtime(value)
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(runtime_model.RegistryFederationConsensusGateCertificateObservatoryRuntime.FIELDS), tuple(sorted(value.to_dict())), runtime_model.RegistryFederationConsensusGateCertificateObservatoryRuntime.FIELDS, "runtime fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "runtime is public and path-free"),
        _finding(3, "observatory-link", value.observatory.content_address == value.observatory_audit.observatory_address == value.query.query.observatory_address == value.report.observatory_address, (value.observatory.content_address, value.observatory_audit.observatory_address, value.query.query.observatory_address, value.report.observatory_address), "observatory address", "all stages link to observatory"),
        _finding(4, "observatory-audit-link", value.observatory_audit.accepted and value.observatory_audit.observatory_address == value.observatory.content_address, value.observatory_audit.accepted, True, "aggregate audit links and passes"),
        _finding(5, "query-link", value.query.query.observatory_address == value.observatory.content_address, value.query.query.observatory_address, value.observatory.content_address, "query links to observatory"),
        _finding(6, "query-audit-link", value.query_audit.accepted and value.query_audit.result_address == value.query.content_address, value.query_audit.accepted, True, "query audit links and passes"),
        _finding(7, "report-link", value.report.observatory_address == value.observatory.content_address, value.report.observatory_address, value.observatory.content_address, "report links to observatory"),
        _finding(8, "report-audit-link", value.report_audit.accepted and value.report_audit.report_address == value.report.content_address, value.report_audit.accepted, True, "report audit links and passes"),
        _finding(9, "package-state", value.persisted == bool(value.package_address), (value.persisted, bool(value.package_address)), "persisted matches package address", "package state is explicit"),
        _finding(10, "stage-acceptance", value.observatory_audit.accepted and value.query_audit.accepted and value.report_audit.accepted, (value.observatory_audit.accepted, value.query_audit.accepted, value.report_audit.accepted), True, "all runtime stages are accepted"),
        _finding(11, "mapping-round-trip", runtime_model.runtime_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original runtime", "mapping conversion is lossless"),
        _finding(12, "content-address", runtime_model.address_runtime(value) == value.content_address, value.content_address, runtime_model.address_runtime(value), "runtime address replays"),
        _finding(13, "path-free", _public(value.to_dict()), True, True, "runtime has no local paths or attribution metadata"),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit(provisional.runtime_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit) -> RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("observatory runtime audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in verify_audit(value).checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Runtime Audit", "", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding.FIELDS), "properties": {field: {"type": "integer"} if field == "ordinal" else {"type": "boolean"} if field == "passed" else {"type": "string"} for field in RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding.FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit.FIELDS), "properties": {"runtime_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent runtime composition checks", "nested stage link validation", "persistence-state validation", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryRuntimeAudit", "RegistryFederationConsensusGateCertificateObservatoryRuntimeAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
