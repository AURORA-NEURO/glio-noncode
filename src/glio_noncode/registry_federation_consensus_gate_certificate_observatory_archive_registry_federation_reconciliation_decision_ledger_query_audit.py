"""Independent assurance for decision-ledger query projections."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_query as query_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.RESULT_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "query-linkage",
    "resource-vocabulary",
    "filter-replay",
    "row-order",
    "row-coverage",
    "projection-replay",
    "matched-count",
    "pagination",
    "truncation",
    "row-addresses",
    "public-boundary",
    "result-address",
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
    return query_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "query audit ordinal", MAX_CHECKS)
        self.check_id = _label(check_id, "query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("query audit check ID is unsupported")
        self.passed = _bool(passed, "query audit result")
        self.detail = _text(detail, "query audit detail", 4096)
        self.evidence_addresses = tuple(_text(item, "query audit evidence address", 2048) for item in _sequence(evidence_addresses, "query audit evidence", query_model.MAX_QUERY_ITEMS + 8))
        self.content_address = _address(content_address, "query audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "query audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("query audit check evidence is not public")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck:
        value = _mapping(value, "query audit check")
        _strict(value, set(cls.FIELDS), "query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit:
    FIELDS = ("query_id", "result_address", "ledger_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, query_id: str, result_address: str, ledger_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_id = _label(query_id, "query audit query ID")
        self.result_address = _address(result_address, "query audit result address", query_model.RESULT_PREFIX)
        self.ledger_address = _address(ledger_address, "query audit ledger address", query_model.ledger_model.LEDGER_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "query audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "query audit failed count", self.check_count)
        self.accepted = _bool(accepted, "query audit acceptance")
        self.content_address = _address(content_address, "query audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "query audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("query audit counters are not conserved")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("query audit checks are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "result_address": self.result_address, "ledger_address": self.ledger_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("query_id", "result_address", "ledger_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit:
        value = _mapping(value, "query audit")
        _strict(value, set(cls.FIELDS), "query audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "query audit checks", MAX_CHECKS))
        return cls(value["query_id"], value["result_address"], value["ledger_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_query(value: query_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit:
    value = query_model.verify_query_result(value)
    query = value.query
    rows = value.rows
    evidence = (value.content_address, query.content_address, query.ledger_address)
    filter_passed = all(
        (not query.operation_address or row.operation_address == query.operation_address)
        and (not query.peer_id or row.peer_id == query.peer_id)
        and (not query.entry_id or row.entry_id == query.entry_id)
        and (not query.plan_status or row.plan_status == query.plan_status)
        and (not query.action or row.action == query.action)
        and (not query.priority or row.priority == query.priority)
        and (not query.disposition or row.disposition == query.disposition)
        and (not query.status or row.status == query.status)
        for row in rows
    )
    checks = (
        _check(1, "query-linkage", bool(query.ledger_address and value.ledger_id and query.query_id), "query links to one ledger and result identity", evidence),
        _check(2, "resource-vocabulary", all(row.resource in query.resources for row in rows), "returned rows use requested resources", tuple(row.content_address for row in rows[:4]) or evidence),
        _check(3, "filter-replay", filter_passed, "returned rows satisfy every exact filter", tuple(row.content_address for row in rows[:4]) or evidence),
        _check(4, "row-order", tuple(row.ordinal for row in rows) == tuple(range(query.offset + 1, query.offset + len(rows) + 1)), "returned rows are page-ordinalled", evidence),
        _check(5, "row-coverage", len({row.row_id for row in rows}) == len(rows), "returned row identifiers are unique", tuple(row.content_address for row in rows[:4]) or evidence),
        _check(6, "projection-replay", all(row.resource in query_model.RESOURCES and row.evidence_addresses for row in rows), "each row is a complete public projection", tuple(row.content_address for row in rows[:4]) or evidence),
        _check(7, "matched-count", value.matched_count <= value.total_count and value.returned_count <= value.matched_count and value.returned_count == len(rows), "query counts are conserved", evidence),
        _check(8, "pagination", value.next_offset == query.offset + value.returned_count, "next offset advances by returned rows", evidence),
        _check(9, "truncation", value.truncated == (value.next_offset < value.matched_count), "truncation flag follows the page boundary", evidence),
        _check(10, "row-addresses", all(query_model.address_row(row) == row.content_address for row in rows), "row content addresses replay", tuple(row.content_address for row in rows[:4]) or evidence),
        _check(11, "public-boundary", _public(value.to_dict()), "query results contain no prohibited private fields", evidence),
        _check(12, "result-address", query_model.address_result(value) == value.content_address, "query result content address replays", (value.content_address,)),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit(value.query.query_id, value.content_address, value.query.ledger_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit(provisional.query_id, provisional.result_address, provisional.ledger_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit):
        raise ValidationError("query audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("query audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Reconciliation Decision Ledger Query Audit", "", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | result | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit.FIELDS), "properties": {"query_id": {"type": "string"}, "result_address": {"type": "string"}, "ledger_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "independent": True, "operations": ("audit_query", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = [
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "CHECK_PREFIX",
    "MAX_CHECKS",
    "VERSION",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAuditCheck",
    "address_audit",
    "address_check",
    "audit_csv",
    "audit_from_mapping",
    "audit_json",
    "audit_query",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
