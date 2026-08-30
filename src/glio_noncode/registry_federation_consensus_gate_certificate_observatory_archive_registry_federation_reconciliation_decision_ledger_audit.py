"""Independent assurance for reconciliation decision ledgers.

Ledger acceptance is intentionally separate from operational readiness.  The
audit confirms that a public ledger is internally conserved, covers each plan
operation exactly once, and retains the evidence needed to replay every
disposition.  It does not turn a pending, held, rejected, or deferred action
into an approved action.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger as ledger_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = ledger_model.VERSION + "-audit-v1"
BOUNDARY = ledger_model.BOUNDARY + "_audit"
AUDIT_PREFIX = ledger_model.LEDGER_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "ledger-linkage",
    "operation-count",
    "decision-order",
    "operation-coverage",
    "decision-conservation",
    "status-conservation",
    "action-compatibility",
    "confirmation-replay",
    "note-replay",
    "evidence-link",
    "source-link",
    "accepted-replay",
    "release-replay",
    "state-replay",
    "public-boundary",
    "ledger-address",
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
    return ledger_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck:
    """One deterministic assurance assertion for a ledger."""

    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger audit ordinal", MAX_CHECKS)
        self.check_id = _label(check_id, "ledger audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("ledger audit check ID is unsupported")
        self.passed = _bool(passed, "ledger audit result")
        self.detail = _text(detail, "ledger audit detail", 4096)
        self.evidence_addresses = tuple(_text(item, "ledger audit evidence address", 2048) for item in _sequence(evidence_addresses, "ledger audit evidence", ledger_model.MAX_DECISIONS + 8))
        self.content_address = _address(content_address, "ledger audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "ledger audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("ledger audit check evidence is not public")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("ledger audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck:
        value = _mapping(value, "ledger audit check")
        _strict(value, set(cls.FIELDS), "ledger audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit:
    """The fixed-size independent audit for one decision ledger."""

    FIELDS = ("ledger_id", "ledger_address", "plan_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, ledger_id: str, ledger_address: str, plan_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.ledger_id = _label(ledger_id, "ledger audit ledger ID")
        self.ledger_address = _address(ledger_address, "ledger audit ledger address", ledger_model.LEDGER_PREFIX)
        self.plan_address = _address(plan_address, "ledger audit plan address", ledger_model.plan_model.PLAN_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck.from_mapping(item) for item in _sequence(checks, "ledger audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "ledger audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "ledger audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "ledger audit failed count", self.check_count)
        self.accepted = _bool(accepted, "ledger audit acceptance")
        self.content_address = _address(content_address, "ledger audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "ledger audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("ledger audit counters are not conserved")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("ledger audit checks are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("ledger audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("ledger audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"ledger_id": self.ledger_id, "ledger_address": self.ledger_address, "plan_address": self.plan_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("ledger_id", "ledger_address", "plan_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit:
        value = _mapping(value, "ledger audit")
        _strict(value, set(cls.FIELDS), "ledger audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "ledger audit checks", MAX_CHECKS))
        return cls(value["ledger_id"], value["ledger_address"], value["plan_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_ledger(value: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit:
    value = ledger_model.verify_ledger(value)
    decisions = value.decisions
    addresses = (value.content_address, value.plan_address, value.resolution_address, value.federation_address)
    status_counts = {status: sum(item.status == status for item in decisions) for status in ledger_model.STATUSES}
    expected_state = "blocked" if any(item.plan_status == "blocked" for item in decisions) else "review" if any(item.plan_status == "review" for item in decisions) or not value.accepted else "ready" if value.release_ready else "authorized"
    checks = (
        _check(1, "ledger-linkage", bool(value.ledger_id and value.plan_id and value.plan_address and value.federation_address), "ledger identity and upstream links are populated", addresses),
        _check(2, "operation-count", value.operation_count == value.decision_count == len(decisions), "one decision row exists for every planned operation", (value.content_address, value.plan_address)),
        _check(3, "decision-order", tuple(item.ordinal for item in decisions) == tuple(range(1, len(decisions) + 1)), "decision rows use canonical ordinal order", (value.content_address,)),
        _check(4, "operation-coverage", len({item.operation_address for item in decisions}) == len(decisions) and len({(item.peer_id, item.entry_id) for item in decisions}) == len(decisions), "operation addresses and peer-entry cells are unique", tuple(item.operation_address for item in decisions[:4]) or (value.content_address,)),
        _check(5, "decision-conservation", all(item.action in ledger_model.plan_model.ACTIONS and item.plan_status in ledger_model.plan_model.STATUSES and item.priority in ledger_model.plan_model.PRIORITIES for item in decisions), "each decision retains the plan vocabulary", tuple(item.content_address for item in decisions[:4]) or (value.content_address,)),
        _check(6, "status-conservation", all(item.status == ledger_model._status_for(item.disposition) for item in decisions), "disposition and status map deterministically", tuple(item.content_address for item in decisions[:4]) or (value.content_address,)),
        _check(7, "action-compatibility", all((item.action == "no-op" and item.disposition == "not-required") or (item.action != "no-op" and item.disposition != "not-required") or False for item in decisions), "no-op and actionable operations retain distinct dispositions", tuple(item.content_address for item in decisions[:4]) or (value.content_address,)),
        _check(8, "confirmation-replay", all((item.action == "no-op" and not item.requires_confirmation) or (item.action != "no-op" and item.requires_confirmation) for item in decisions), "confirmation requirements replay the plan action", tuple(item.content_address for item in decisions[:4]) or (value.content_address,)),
        _check(9, "note-replay", all((item.disposition not in {"hold", "reject", "defer"}) or bool(item.note) for item in decisions), "review dispositions retain a reason note", tuple(item.content_address for item in decisions[:4]) or (value.content_address,)),
        _check(10, "evidence-link", all(item.operation_address in item.evidence_addresses for item in decisions), "every row retains its operation evidence address", tuple(item.content_address for item in decisions[:4]) or (value.content_address,)),
        _check(11, "source-link", all(item.source_state in ledger_model.plan_model.resolution_model.STATES for item in decisions), "every row retains a supported source state", (value.content_address,)),
        _check(12, "accepted-replay", value.accepted == (not any(status_counts[status] for status in ("pending", "held", "rejected", "deferred"))), "ledger acceptance is the absence of unresolved dispositions", (value.content_address,)),
        _check(13, "release-replay", value.release_ready == (value.accepted and status_counts["not-required"] == len(decisions)), "release readiness requires a complete no-op closure", (value.content_address,)),
        _check(14, "state-replay", value.state == expected_state, "ledger state follows plan state and decision closure", (value.content_address,)),
        _check(15, "public-boundary", _public(value.to_dict()), "ledger evidence contains no prohibited private fields", (value.content_address,)),
        _check(16, "ledger-address", ledger_model.address_ledger(value) == value.content_address, "ledger content address replays", (value.content_address,)),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit(value.ledger_id, value.content_address, value.plan_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit(provisional.ledger_id, provisional.ledger_address, provisional.plan_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit):
        raise ValidationError("ledger audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("ledger audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Reconciliation Decision Ledger Audit", "", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | result | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit.FIELDS), "properties": {"ledger_id": {"type": "string"}, "ledger_address": {"type": "string"}, "plan_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "independent": True, "operations": ("audit_ledger", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = [
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "CHECK_PREFIX",
    "MAX_CHECKS",
    "VERSION",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAuditCheck",
    "address_audit",
    "address_check",
    "audit_csv",
    "audit_from_mapping",
    "audit_json",
    "audit_ledger",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
