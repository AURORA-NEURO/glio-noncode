"""Independent assurance for decision-ledger transition diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_diff as diff_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "diff-linkage",
    "item-count",
    "item-order",
    "operation-coverage",
    "classification-conservation",
    "added-shape",
    "removed-shape",
    "unchanged-shape",
    "changed-shape",
    "outcome-preservation",
    "evidence-preservation",
    "public-boundary",
    "address-replay",
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
    return diff_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff audit ordinal", MAX_CHECKS)
        self.check_id = _label(check_id, "diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("diff audit check ID is unsupported")
        self.passed = _bool(passed, "diff audit result")
        self.detail = _text(detail, "diff audit detail", 4096)
        self.evidence_addresses = tuple(_text(item, "diff audit evidence address", 2048) for item in _sequence(evidence_addresses, "diff audit evidence", diff_model.MAX_ITEMS + 8))
        self.content_address = _address(content_address, "diff audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("diff audit check evidence is not public")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck:
        value = _mapping(value, "diff audit check")
        _strict(value, set(cls.FIELDS), "diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit:
    FIELDS = ("diff_id", "diff_address", "left_ledger_address", "right_ledger_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, diff_id: str, diff_address: str, left_ledger_address: str, right_ledger_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "diff audit diff ID")
        self.diff_address = _address(diff_address, "diff audit diff address", diff_model.DIFF_PREFIX)
        self.left_ledger_address = _address(left_ledger_address, "diff audit left ledger address", diff_model.ledger_model.LEDGER_PREFIX)
        self.right_ledger_address = _address(right_ledger_address, "diff audit right ledger address", diff_model.ledger_model.LEDGER_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck.from_mapping(item) for item in _sequence(checks, "diff audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "diff audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "diff audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "diff audit failed count", self.check_count)
        self.accepted = _bool(accepted, "diff audit acceptance")
        self.content_address = _address(content_address, "diff audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("diff audit counters are not conserved")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("diff audit checks are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("diff audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("diff audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "diff_address": self.diff_address, "left_ledger_address": self.left_ledger_address, "right_ledger_address": self.right_ledger_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("diff_id", "diff_address", "left_ledger_address", "right_ledger_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit:
        value = _mapping(value, "diff audit")
        _strict(value, set(cls.FIELDS), "diff audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "diff audit checks", MAX_CHECKS))
        return cls(value["diff_id"], value["diff_address"], value["left_ledger_address"], value["right_ledger_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_diff(value: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit:
    value = diff_model.verify_diff(value)
    items = value.items
    evidence = (value.content_address, value.left_ledger_address, value.right_ledger_address)
    checks = (
        _check(1, "diff-linkage", bool(value.diff_id and value.left_ledger_address and value.right_ledger_address), "diff identity and both ledger links are populated", evidence),
        _check(2, "item-count", value.item_count == len(items) and value.item_count > 0, "diff item count matches its rows", evidence),
        _check(3, "item-order", tuple(item.ordinal for item in items) == tuple(range(1, len(items) + 1)), "diff rows use canonical ordinal order", tuple(item.content_address for item in items[:4]) or evidence),
        _check(4, "operation-coverage", len({item.operation_address for item in items}) == len(items), "each operation address appears once", tuple(item.operation_address for item in items[:4]) or evidence),
        _check(5, "classification-conservation", value.item_count == value.added_count + value.removed_count + value.changed_count + value.unchanged_count, "classification counters cover every row", evidence),
        _check(6, "added-shape", all(item.change != "added" or (not item.left_disposition and item.right_disposition and item.changed_fields == ("operation",)) for item in items), "added rows contain only right-side decision data", tuple(item.content_address for item in items if item.change == "added")[:4] or evidence),
        _check(7, "removed-shape", all(item.change != "removed" or (item.left_disposition and not item.right_disposition and item.changed_fields == ("operation",)) for item in items), "removed rows contain only left-side decision data", tuple(item.content_address for item in items if item.change == "removed")[:4] or evidence),
        _check(8, "unchanged-shape", all(item.change != "unchanged" or (item.left_disposition == item.right_disposition and item.left_status == item.right_status and not item.changed_fields) for item in items), "unchanged rows have no changed fields", tuple(item.content_address for item in items if item.change == "unchanged")[:4] or evidence),
        _check(9, "changed-shape", all(item.change != "changed" or (item.left_disposition and item.right_disposition and item.changed_fields) for item in items), "changed rows retain both sides and changed fields", tuple(item.content_address for item in items if item.change == "changed")[:4] or evidence),
        _check(10, "outcome-preservation", isinstance(value.left_accepted, bool) and isinstance(value.right_accepted, bool) and isinstance(value.left_release_ready, bool) and isinstance(value.right_release_ready, bool), "both ledger outcomes are retained", evidence),
        _check(11, "evidence-preservation", all(item.operation_address in item.evidence_addresses and value.left_ledger_address in item.evidence_addresses and value.right_ledger_address in item.evidence_addresses for item in items), "every transition row retains both ledgers and its operation", tuple(item.content_address for item in items[:4]) or evidence),
        _check(12, "public-boundary", _public(value.to_dict()), "diff evidence contains no prohibited private fields", evidence),
        _check(13, "address-replay", diff_model.address_diff(value) == value.content_address and all(diff_model.address_item(item) == item.content_address for item in items), "diff and item addresses replay", evidence),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit(value.diff_id, value.content_address, value.left_ledger_address, value.right_ledger_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit(provisional.diff_id, provisional.diff_address, provisional.left_ledger_address, provisional.right_ledger_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit):
        raise ValidationError("diff audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("diff audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Reconciliation Decision Ledger Diff Audit", "", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | result | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit.FIELDS), "properties": {"diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "left_ledger_address": {"type": "string"}, "right_ledger_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "independent": True, "operations": ("audit_diff", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = [
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "CHECK_PREFIX",
    "MAX_CHECKS",
    "VERSION",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAudit",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffAuditCheck",
    "address_audit",
    "address_check",
    "audit_csv",
    "audit_diff",
    "audit_from_mapping",
    "audit_json",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
