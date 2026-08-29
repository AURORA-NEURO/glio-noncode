"""Independent audit for consensus remediation plans."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus as consensus_model
from . import registry_federation_consensus_remediation as remediation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = remediation_model.VERSION + "-audit-v1"
BOUNDARY = remediation_model.BOUNDARY + "_audit"
AUDIT_PREFIX = consensus_model.CONSENSUS_PREFIX + "-remediation-audit"
CHECK_PREFIX = consensus_model.CONSENSUS_PREFIX + "-remediation-audit-check"
CHECK_IDS = ("exact-fields", "public-boundary", "consensus-link", "step-conservation", "action-conservation", "status-conservation", "blocking-conservation", "readiness-conservation", "address-conservation", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 32768, *, required: bool = False) -> str:
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
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusRemediationAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "remediation audit finding ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "remediation audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("remediation audit check ID is unsupported")
        self.passed = _bool(passed, "remediation audit result")
        self.observed = _text(observed, "remediation audit observed value")
        self.expected = _text(expected, "remediation audit expected value")
        self.detail = _text(detail, "remediation audit detail")
        self.content_address = _address(content_address, "remediation audit finding address", CHECK_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("remediation audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("remediation audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "passed": self.passed, "observed": self.observed, "expected": self.expected, "detail": self.detail, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusRemediationAuditFinding:
        value = _mapping(value, "remediation audit finding")
        _strict(value, set(cls.FIELDS), "remediation audit finding")
        return cls(value["ordinal"], value["check_id"], value["passed"], value["observed"], value["expected"], value["detail"], value["content_address"])


def address_finding(value: RegistryFederationConsensusRemediationAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusRemediationAuditFinding):
        raise ValidationError("remediation finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusRemediationAudit:
    FIELDS = ("remediation_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, remediation_address: str, checks: Sequence[RegistryFederationConsensusRemediationAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.remediation_address = _address(remediation_address, "audited remediation address", remediation_model.REMEDIATION_PREFIX)
        self.checks = tuple(checks)
        self.check_count = _count(check_count, "remediation audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "remediation audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "remediation audit failed count", self.check_count)
        self.accepted = _bool(accepted, "remediation audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("remediation audit counters are not conserved")
        self.content_address = _address(content_address, "remediation audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("remediation audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("remediation audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"remediation_address": self.remediation_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusRemediationAudit:
        value = _mapping(value, "remediation audit")
        _strict(value, set(cls.FIELDS), "remediation audit")
        return cls(value["remediation_address"], tuple(RegistryFederationConsensusRemediationAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusRemediationAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusRemediationAudit):
        raise ValidationError("remediation audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusRemediationAuditFinding:
    provisional = RegistryFederationConsensusRemediationAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusRemediationAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_remediation(value: remediation_model.RegistryFederationConsensusRemediation) -> RegistryFederationConsensusRemediationAudit:
    value = remediation_model.verify_remediation(value)
    checks: list[RegistryFederationConsensusRemediationAuditFinding] = []
    checks.append(_finding(1, "exact-fields", set(value.to_dict()) == set(remediation_model.RegistryFederationConsensusRemediation.FIELDS), tuple(sorted(value.to_dict())), remediation_model.RegistryFederationConsensusRemediation.FIELDS, "remediation fields are exact"))
    checks.append(_finding(2, "public-boundary", _public(value.to_dict()), True, True, "remediation is public and path-free"))
    checks.append(_finding(3, "consensus-link", value.consensus_address.startswith(consensus_model.CONSENSUS_PREFIX + ":"), value.consensus_address, "consensus address", "plan points to one consensus receipt"))
    checks.append(_finding(4, "step-conservation", value.step_count == len(value.steps) and tuple(item.ordinal for item in value.steps) == tuple(range(1, value.step_count + 1)), (value.step_count, len(value.steps)), "ordered steps", "step count matches ordinals"))
    checks.append(_finding(5, "action-conservation", len({item.action_id for item in value.steps}) == value.step_count and all(item.package_id and item.kind for item in value.steps), "unique action-linked steps", "one package and kind per step", "steps retain action identity"))
    checks.append(_finding(6, "status-conservation", all(item.status in remediation_model.STATUSES and item.severity in consensus_model.SEVERITIES for item in value.steps), "known step statuses", remediation_model.STATUSES, "step status follows the public vocabulary"))
    checks.append(_finding(7, "blocking-conservation", value.blocking_count == sum(item.severity == "blocking" for item in value.steps) and value.review_count == sum(item.severity == "review" for item in value.steps), (value.blocking_count, value.review_count), "severity counters", "blocking and review counts replay"))
    checks.append(_finding(8, "readiness-conservation", value.ready == (value.blocking_count == 0), value.ready, "ready iff no blocking steps", "readiness is fail-closed"))
    checks.append(_finding(9, "address-conservation", all(remediation_model.address_step(item) == item.content_address for item in value.steps), "replayed step addresses", "stored step addresses", "every step address replays"))
    checks.append(_finding(10, "mapping-round-trip", remediation_model.remediation_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original remediation", "mapping conversion is lossless"))
    checks.append(_finding(11, "path-free", _public(value.to_dict()), True, True, "instructions and evidence contain no paths"))
    provisional = RegistryFederationConsensusRemediationAudit(value.content_address, tuple(checks), len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusRemediationAudit(provisional.remediation_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusRemediationAudit:
    return verify_audit(RegistryFederationConsensusRemediationAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusRemediationAudit) -> RegistryFederationConsensusRemediationAudit:
    if not isinstance(value, RegistryFederationConsensusRemediationAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("remediation audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusRemediationAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusRemediationAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusRemediationAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for finding in value.checks:
        writer.writerow(finding.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusRemediationAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Remediation Audit", "", f"- Remediation: `{value.remediation_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusRemediationAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusRemediationAudit.FIELDS), "properties": {"remediation_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "features": ("independent remediation counter checks", "action identity conservation", "fail-closed readiness validation", "content-address replay", "mapping round-trip verification"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "RegistryFederationConsensusRemediationAudit", "RegistryFederationConsensusRemediationAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_remediation", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
