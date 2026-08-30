"""Independent assurance for non-mutating federation reconciliation plans."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan as plan_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = plan_model.VERSION + "-audit-v1"
BOUNDARY = plan_model.BOUNDARY + "_audit"
AUDIT_PREFIX = plan_model.PLAN_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("plan-linkage", "operation-count", "operation-order", "action-conservation", "status-conservation", "matrix-coverage", "confirmation", "address-replay", "source-states", "accepted-state", "evidence", "nested-links", "public-boundary", "plan-address")
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
    return plan_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "plan audit ordinal", MAX_CHECKS)
        self.check_id = _label(check_id, "plan audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("plan audit check ID is unsupported")
        self.passed = _bool(passed, "plan audit result")
        self.detail = _text(detail, "plan audit detail", 4096)
        self.evidence_addresses = tuple(_text(item, "plan audit evidence address", 2048) for item in _sequence(evidence_addresses, "plan audit evidence", plan_model.MAX_OPERATIONS + 4))
        self.content_address = _address(content_address, "plan audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "plan audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("plan audit check evidence is not public")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("plan audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck":
        value = _mapping(value, "plan audit check")
        _strict(value, set(cls.FIELDS), "plan audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit:
    FIELDS = ("plan_id", "plan_address", "resolution_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, plan_id: str, plan_address: str, resolution_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.plan_id = _label(plan_id, "plan audit plan ID")
        self.plan_address = _address(plan_address, "plan audit plan address", plan_model.PLAN_PREFIX)
        self.resolution_address = _address(resolution_address, "plan audit resolution address", plan_model.resolution_model.RESOLUTION_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck.from_mapping(item) for item in _sequence(checks, "plan audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "plan audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "plan audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "plan audit failed count", self.check_count)
        self.accepted = _bool(accepted, "plan audit acceptance")
        self.content_address = _address(content_address, "plan audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "plan audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("plan audit counters are not conserved")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("plan audit checks are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("plan audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("plan audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"plan_id": self.plan_id, "plan_address": self.plan_address, "resolution_address": self.resolution_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("plan_id", "plan_address", "resolution_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit":
        value = _mapping(value, "plan audit")
        _strict(value, set(cls.FIELDS), "plan audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "plan audit checks", MAX_CHECKS))
        return cls(value["plan_id"], value["plan_address"], value["resolution_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_plan(value: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit:
    value = plan_model.verify_plan(value)
    operation_addresses = tuple(item.content_address for item in value.operations)
    action_counts = {action: sum(item.action == action for item in value.operations) for action in plan_model.ACTIONS}
    checks = (
        _check(1, "plan-linkage", bool(value.resolution_id and value.resolution_address and value.federation_id and value.federation_address), "plan retains source resolution and federation links", (value.content_address, value.resolution_address, value.federation_address)),
        _check(2, "operation-count", value.operation_count == len(value.operations) and value.operation_count == value.peer_count * value.entry_count, "operation count covers every peer-entry cell", operation_addresses or (value.content_address,)),
        _check(3, "operation-order", tuple(item.ordinal for item in value.operations) == tuple(range(1, value.operation_count + 1)), "operations have contiguous deterministic ordinals", operation_addresses or (value.content_address,)),
        _check(4, "action-conservation", value.noop_count == action_counts["no-op"] and value.request_count == action_counts["request-missing"] and value.replace_count == action_counts["replace-with-consensus"] and value.review_count == action_counts["manual-review"], "action counters conserve the operation matrix", (value.content_address,)),
        _check(5, "status-conservation", value.blocked_count == sum(item.status == "blocked" for item in value.operations), "blocked status count replays", (value.content_address,)),
        _check(6, "matrix-coverage", len({(item.peer_id, item.entry_id) for item in value.operations}) == value.operation_count, "each peer-entry cell appears exactly once", operation_addresses or (value.content_address,)),
        _check(7, "confirmation", all((item.action == "no-op" and not item.requires_confirmation) or (item.action != "no-op" and item.requires_confirmation) for item in value.operations), "only no-op operations avoid confirmation", operation_addresses or (value.content_address,)),
        _check(8, "address-replay", all(plan_model.address_operation(item) == item.content_address for item in value.operations), "operation content addresses replay", operation_addresses or (value.content_address,)),
        _check(9, "source-states", all(item.source_state in plan_model.resolution_model.STATES for item in value.operations), "operations retain supported resolution states", operation_addresses or (value.content_address,)),
        _check(10, "accepted-state", value.accepted == (value.blocked_count == 0) and value.release_ready == (value.state == "ready"), "accepted and release-ready projections replay", (value.content_address,)),
        _check(11, "evidence", all(item.evidence_addresses for item in value.operations), "every operation carries source evidence", operation_addresses or (value.content_address,)),
        _check(12, "nested-links", value.resolution_address.startswith(plan_model.resolution_model.RESOLUTION_PREFIX + ":") and value.federation_address.startswith(plan_model.federation_model.FEDERATION_PREFIX + ":"), "nested resolution and federation addresses use public namespaces", (value.resolution_address, value.federation_address)),
        _check(13, "public-boundary", _public(value.to_dict()), "plan projections contain no private fields", (value.content_address,)),
        _check(14, "plan-address", plan_model.address_plan(value) == value.content_address, "plan content address replays", (value.content_address,)),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit(value.plan_id, value.content_address, value.resolution_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit(provisional.plan_id, provisional.plan_address, provisional.resolution_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit):
        raise ValidationError("plan audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("plan audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Reconciliation Plan Audit", "", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | result | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit.FIELDS), "properties": {"plan_id": {"type": "string"}, "plan_address": {"type": "string"}, "resolution_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "independent": True, "operations": ("audit_plan", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_plan", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
