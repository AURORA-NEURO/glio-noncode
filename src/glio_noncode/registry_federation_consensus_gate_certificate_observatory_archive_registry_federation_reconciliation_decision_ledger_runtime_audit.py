"""Independent assurance for the persisted decision-ledger runtime."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_runtime as runtime_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = runtime_model.VERSION + "-audit-v1"
BOUNDARY = runtime_model.BOUNDARY + "_audit"
AUDIT_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "runtime-linkage",
    "count-replay",
    "plan-link",
    "plan-audit",
    "ledger-link",
    "ledger-audit",
    "query-link",
    "query-audit",
    "ledger-outcome",
    "query-coverage",
    "state-replay",
    "public-boundary",
    "runtime-address",
)
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
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
    return runtime_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime audit ordinal", MAX_CHECKS)
        self.check_id = _label(check_id, "runtime audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("runtime audit check ID is unsupported")
        self.passed = _bool(passed, "runtime audit result")
        self.detail = _text(detail, "runtime audit detail", 4096)
        self.evidence_addresses = tuple(_text(item, "runtime audit evidence address", 2048) for item in _sequence(evidence_addresses, "runtime audit evidence", runtime_model.MAX_DECISIONS + 12))
        self.content_address = _address(content_address, "runtime audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "runtime audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("runtime audit check evidence is not public")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("runtime audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck:
        value = _mapping(value, "runtime audit check")
        _strict(value, set(cls.FIELDS), "runtime audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit:
    FIELDS = ("runtime_id", "runtime_address", "ledger_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, runtime_id: str, runtime_address: str, ledger_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "runtime audit runtime ID")
        self.runtime_address = _address(runtime_address, "runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.ledger_address = _address(ledger_address, "runtime audit ledger address", runtime_model.ledger_model.LEDGER_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck.from_mapping(item) for item in _sequence(checks, "runtime audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "runtime audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "runtime audit failed count", self.check_count)
        self.accepted = _bool(accepted, "runtime audit acceptance")
        self.content_address = _address(content_address, "runtime audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "runtime audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("runtime audit counters are not conserved")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime audit checks are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("runtime audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "runtime_address": self.runtime_address, "ledger_address": self.ledger_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("runtime_id", "runtime_address", "ledger_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit:
        value = _mapping(value, "runtime audit")
        _strict(value, set(cls.FIELDS), "runtime audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "runtime audit checks", MAX_CHECKS))
        return cls(value["runtime_id"], value["runtime_address"], value["ledger_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_runtime(value: runtime_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit:
    value = runtime_model.verify_runtime(value)
    evidence = (value.content_address, value.plan.content_address, value.ledger.content_address, value.query.content_address)
    checks = (
        _check(1, "runtime-linkage", bool(value.runtime_id and value.version and value.boundary), "runtime identity and boundary are populated", (value.content_address,)),
        _check(2, "count-replay", value.operation_count == value.plan.operation_count == value.decision_count == value.ledger.decision_count, "operation and decision counts replay through the closure", evidence),
        _check(3, "plan-link", value.ledger.plan_address == value.plan.content_address and value.query.query.ledger_address == value.ledger.content_address, "ledger and query retain upstream links", evidence),
        _check(4, "plan-audit", value.plan_audit.plan_address == value.plan.content_address and value.plan_audit.accepted, "upstream plan audit is accepted", (value.plan_audit.content_address, value.plan.content_address)),
        _check(5, "ledger-link", value.ledger_audit.ledger_address == value.ledger.content_address, "ledger audit points to the runtime ledger", (value.ledger_audit.content_address, value.ledger.content_address)),
        _check(6, "ledger-audit", value.ledger_audit.accepted, "decision ledger audit is accepted", (value.ledger_audit.content_address,)),
        _check(7, "query-link", value.query.query.ledger_address == value.ledger.content_address and value.query_audit.result_address == value.query.content_address, "query and query audit retain ledger/result links", (value.query.content_address, value.query_audit.content_address)),
        _check(8, "query-audit", value.query_audit.accepted, "query audit is accepted", (value.query_audit.content_address,)),
        _check(9, "ledger-outcome", value.ledger_accepted == value.ledger.accepted and value.release_ready == value.ledger.release_ready, "runtime outcome retains ledger acceptance and readiness", (value.content_address, value.ledger.content_address)),
        _check(10, "query-coverage", value.query.returned_count <= value.query.matched_count <= value.query.total_count, "bounded query counts are conserved", (value.query.content_address,)),
        _check(11, "state-replay", value.state == value.ledger.state, "runtime state replays the ledger state", (value.content_address, value.ledger.content_address)),
        _check(12, "public-boundary", _public(value.to_dict()), "runtime closure contains no prohibited private fields", (value.content_address,)),
        _check(13, "runtime-address", runtime_model.address_runtime(value) == value.content_address, "runtime content address replays", (value.content_address,)),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit(value.runtime_id, value.content_address, value.ledger.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit(provisional.runtime_id, provisional.runtime_address, provisional.ledger_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit):
        raise ValidationError("runtime audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("runtime audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Reconciliation Decision Ledger Runtime Audit", "", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | result | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit.FIELDS), "properties": {"runtime_id": {"type": "string"}, "runtime_address": {"type": "string"}, "ledger_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "independent": True, "operations": ("audit_runtime", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = [
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "CHECK_PREFIX",
    "MAX_CHECKS",
    "VERSION",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAudit",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntimeAuditCheck",
    "address_audit",
    "address_check",
    "audit_csv",
    "audit_from_mapping",
    "audit_json",
    "audit_runtime",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
