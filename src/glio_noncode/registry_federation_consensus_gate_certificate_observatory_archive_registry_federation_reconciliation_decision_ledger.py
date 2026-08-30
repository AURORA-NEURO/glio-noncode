"""Decision-preserving closure for a federation reconciliation plan.

The reconciliation plan is intentionally non-mutating: it explains which
peer/entry cells already agree, which cells could be repaired, and which cells
need review.  This module adds the next boundary without pretending to
perform a repair.  It records an explicit disposition for every operation so
that a later executor can consume a complete, content-addressed handoff.

The ledger is public evidence.  It contains no filesystem paths, credentials,
operator identities, model metadata, or implicit timestamps.  A pending row is
not silently promoted.  An approved row is an authorization record only; the
source registry remains unchanged and release readiness still requires the
original plan to be a no-op plan.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan as plan_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = plan_model.VERSION + "-decision-ledger-v1"
BOUNDARY = plan_model.BOUNDARY + "_decision_ledger"
LEDGER_PREFIX = plan_model.PLAN_PREFIX + "-ledger"
DECISION_PREFIX = LEDGER_PREFIX + "-decision"
DEFAULT_LEDGER_ID = "consensus-certificate-observatory-archive-registry-federation-reconciliation-decision-ledger"
MAX_DECISIONS = plan_model.MAX_OPERATIONS

DISPOSITIONS = ("pending", "approve", "hold", "reject", "defer", "not-required")
STATUSES = ("pending", "approved", "held", "rejected", "deferred", "not-required")
STATES = ("ready", "authorized", "review", "blocked")
REASONS = (
    "awaiting-explicit-disposition",
    "action-authorized-for-separate-execution",
    "action-held-for-review",
    "action-rejected",
    "action-deferred",
    "no-op-requires-no-disposition",
)
_STATUS_BY_DISPOSITION = {
    "pending": "pending",
    "approve": "approved",
    "hold": "held",
    "reject": "rejected",
    "defer": "deferred",
    "not-required": "not-required",
}
_REASON_BY_DISPOSITION = {
    "pending": "awaiting-explicit-disposition",
    "approve": "action-authorized-for-separate-execution",
    "hold": "action-held-for-review",
    "reject": "action-rejected",
    "defer": "action-deferred",
    "not-required": "no-op-requires-no-disposition",
}


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value):
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and value and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return plan_model._public(value)


def _status_for(disposition: str) -> str:
    try:
        return _STATUS_BY_DISPOSITION[disposition]
    except KeyError as error:
        raise ValidationError("decision disposition is unsupported") from error


def _reason_for(disposition: str) -> str:
    try:
        return _REASON_BY_DISPOSITION[disposition]
    except KeyError as error:
        raise ValidationError("decision disposition is unsupported") from error


def _validate_disposition(operation: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation, disposition: str) -> None:
    if disposition not in DISPOSITIONS:
        raise ValidationError("decision disposition is unsupported")
    if operation.action == "no-op" and disposition != "not-required":
        raise ValidationError("a no-op operation only accepts not-required")
    if operation.action != "no-op" and disposition == "not-required":
        raise ValidationError("an actionable operation requires an explicit disposition")
    if operation.status == "blocked" and disposition == "approve":
        raise ValidationError("a blocked operation cannot be approved")
    if operation.status == "review" and disposition == "approve":
        raise ValidationError("a review operation cannot be approved")


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision:
    """One explicit, non-executing disposition for one plan operation."""

    FIELDS = (
        "ordinal",
        "operation_address",
        "peer_id",
        "registry_id",
        "entry_id",
        "package_id",
        "source_state",
        "action",
        "plan_status",
        "priority",
        "disposition",
        "status",
        "requires_confirmation",
        "note",
        "evidence_addresses",
        "content_address",
    )

    def __init__(
        self,
        ordinal: int,
        operation_address: str,
        peer_id: str,
        registry_id: str,
        entry_id: str,
        package_id: str,
        source_state: str,
        action: str,
        plan_status: str,
        priority: str,
        disposition: str,
        status: str,
        requires_confirmation: bool,
        note: str,
        evidence_addresses: Sequence[str],
        content_address: str,
    ) -> None:
        self.ordinal = _count(ordinal, "decision ordinal", MAX_DECISIONS, positive=True)
        self.operation_address = _address(operation_address, "decision operation address", plan_model.OPERATION_PREFIX)
        self.peer_id = _label(peer_id, "decision peer ID")
        self.registry_id = _label(registry_id, "decision registry ID")
        self.entry_id = _label(entry_id, "decision entry ID")
        self.package_id = _label(package_id, "decision package ID", required=False)
        self.source_state = _label(source_state, "decision source state")
        self.action = _label(action, "decision action")
        self.plan_status = _label(plan_status, "decision plan status")
        self.priority = _label(priority, "decision priority")
        self.disposition = _label(disposition, "decision disposition")
        self.status = _label(status, "decision status")
        self.requires_confirmation = _bool(requires_confirmation, "decision confirmation requirement")
        self.note = _text(note, "decision note", 2048, required=False)
        self.evidence_addresses = tuple(
            _text(item, "decision evidence address", 2048)
            for item in _sequence(evidence_addresses, "decision evidence", plan_model.resolution_model.MAX_PEERS + 8)
        )
        self.content_address = _address(content_address, "decision address", DECISION_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "decision address")
        self._validate()

    def _validate(self) -> None:
        if self.source_state not in plan_model.resolution_model.STATES:
            raise ValidationError("decision source state is unsupported")
        if self.action not in plan_model.ACTIONS or self.plan_status not in plan_model.STATUSES or self.priority not in plan_model.PRIORITIES:
            raise ValidationError("decision plan vocabulary is unsupported")
        if self.disposition not in DISPOSITIONS or self.status not in STATUSES or _status_for(self.disposition) != self.status:
            raise ValidationError("decision disposition and status are not conserved")
        if self.action == "no-op" and (self.disposition != "not-required" or self.requires_confirmation or self.note):
            raise ValidationError("no-op decision is not conserved")
        if self.action != "no-op" and self.disposition == "not-required":
            raise ValidationError("actionable decision cannot be not-required")
        if self.plan_status == "blocked" and self.disposition == "approve":
            raise ValidationError("blocked decision cannot be approved")
        if self.plan_status == "review" and self.disposition == "approve":
            raise ValidationError("review decision cannot be approved")
        if self.disposition in {"hold", "reject", "defer"} and not self.note:
            raise ValidationError("held, rejected, and deferred decisions require a note")
        if not self.evidence_addresses or self.operation_address not in self.evidence_addresses:
            raise ValidationError("decision evidence must include its operation")
        if not _public(self.to_dict()):
            raise ValidationError("decision crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_decision(self) != self.content_address:
            raise ValidationError("decision address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"evidence_addresses"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision:
        value = _mapping(value, "decision")
        _strict(value, set(cls.FIELDS), "decision")
        return cls(*(value[field] for field in cls.FIELDS))


def address_decision(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DECISION_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger:
    """Complete decision closure for every operation in one reconciliation plan."""

    FIELDS = (
        "ledger_id",
        "version",
        "boundary",
        "plan_id",
        "plan_address",
        "resolution_address",
        "federation_id",
        "federation_address",
        "decisions",
        "operation_count",
        "decision_count",
        "pending_count",
        "approved_count",
        "held_count",
        "rejected_count",
        "deferred_count",
        "not_required_count",
        "accepted",
        "release_ready",
        "state",
        "content_address",
    )

    def __init__(
        self,
        ledger_id: str,
        version: str,
        boundary: str,
        plan_id: str,
        plan_address: str,
        resolution_address: str,
        federation_id: str,
        federation_address: str,
        decisions: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision],
        operation_count: int,
        decision_count: int,
        pending_count: int,
        approved_count: int,
        held_count: int,
        rejected_count: int,
        deferred_count: int,
        not_required_count: int,
        accepted: bool,
        release_ready: bool,
        state: str,
        content_address: str,
    ) -> None:
        self.ledger_id = _label(ledger_id, "decision ledger ID")
        self.version = _text(version, "decision ledger version")
        self.boundary = _text(boundary, "decision ledger boundary", 512)
        self.plan_id = _label(plan_id, "decision ledger plan ID")
        self.plan_address = _address(plan_address, "decision ledger plan address", plan_model.PLAN_PREFIX)
        self.resolution_address = _address(resolution_address, "decision ledger resolution address", plan_model.resolution_model.RESOLUTION_PREFIX)
        self.federation_id = _label(federation_id, "decision ledger federation ID")
        self.federation_address = _address(federation_address, "decision ledger federation address", plan_model.federation_model.FEDERATION_PREFIX)
        self.decisions = tuple(
            item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision.from_mapping(item)
            for item in _sequence(decisions, "decision ledger decisions", MAX_DECISIONS)
        )
        self.operation_count = _count(operation_count, "decision ledger operation count", MAX_DECISIONS, positive=True)
        self.decision_count = _count(decision_count, "decision ledger decision count", MAX_DECISIONS, positive=True)
        self.pending_count = _count(pending_count, "decision ledger pending count", MAX_DECISIONS)
        self.approved_count = _count(approved_count, "decision ledger approved count", MAX_DECISIONS)
        self.held_count = _count(held_count, "decision ledger held count", MAX_DECISIONS)
        self.rejected_count = _count(rejected_count, "decision ledger rejected count", MAX_DECISIONS)
        self.deferred_count = _count(deferred_count, "decision ledger deferred count", MAX_DECISIONS)
        self.not_required_count = _count(not_required_count, "decision ledger not-required count", MAX_DECISIONS)
        self.accepted = _bool(accepted, "decision ledger acceptance")
        self.release_ready = _bool(release_ready, "decision ledger release readiness")
        self.state = _label(state, "decision ledger state")
        self.content_address = _address(content_address, "decision ledger address", LEDGER_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "decision ledger address")
        self._validate()

    def _validate(self) -> None:
        if self.operation_count != self.decision_count or self.decision_count != len(self.decisions):
            raise ValidationError("decision ledger counts do not cover the plan")
        if tuple(item.ordinal for item in self.decisions) != tuple(range(1, self.decision_count + 1)):
            raise ValidationError("decision ledger ordinals are not canonical")
        operation_keys = {(item.peer_id, item.entry_id) for item in self.decisions}
        if len(operation_keys) != self.decision_count or len({item.operation_address for item in self.decisions}) != self.decision_count:
            raise ValidationError("decision ledger operations are not unique")
        counters = {status: sum(item.status == status for item in self.decisions) for status in STATUSES}
        if (self.pending_count, self.approved_count, self.held_count, self.rejected_count, self.deferred_count, self.not_required_count) != tuple(counters[item] for item in ("pending", "approved", "held", "rejected", "deferred", "not-required")):
            raise ValidationError("decision ledger status counters do not replay")
        expected_accepted = not any(self.decisions_for_status(status) for status in ("pending", "held", "rejected", "deferred"))
        expected_release_ready = expected_accepted and self.not_required_count == self.operation_count
        if self.accepted != expected_accepted or self.release_ready != expected_release_ready:
            raise ValidationError("decision ledger outcome does not replay")
        plan_statuses = {item.plan_status for item in self.decisions}
        expected_state = "blocked" if "blocked" in plan_statuses else "review" if "review" in plan_statuses or not self.accepted else "ready" if self.release_ready else "authorized"
        if self.state not in STATES or self.state != expected_state:
            raise ValidationError("decision ledger state does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("decision ledger crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_ledger(self) != self.content_address:
            raise ValidationError("decision ledger address does not replay")

    def decisions_for_status(self, status: str) -> tuple[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision, ...]:
        status = _label(status, "decision ledger status")
        if status not in STATUSES:
            raise ValidationError("decision ledger status is unsupported")
        return tuple(item for item in self.decisions if item.status == status)

    def decision(self, operation_address: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision:
        operation_address = _address(operation_address, "decision operation address", plan_model.OPERATION_PREFIX)
        for item in self.decisions:
            if item.operation_address == operation_address:
                return item
        raise ValidationError("decision for operation was not found")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_id": self.ledger_id,
            "version": self.version,
            "boundary": self.boundary,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "resolution_address": self.resolution_address,
            "federation_id": self.federation_id,
            "federation_address": self.federation_address,
            "decisions": tuple(item.to_dict() for item in self.decisions),
            "operation_count": self.operation_count,
            "decision_count": self.decision_count,
            "pending_count": self.pending_count,
            "approved_count": self.approved_count,
            "held_count": self.held_count,
            "rejected_count": self.rejected_count,
            "deferred_count": self.deferred_count,
            "not_required_count": self.not_required_count,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "state": self.state,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "decisions"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger:
        value = _mapping(value, "decision ledger")
        _strict(value, set(cls.FIELDS), "decision ledger")
        decisions = tuple(
            RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision.from_mapping(item)
            for item in _sequence(value["decisions"], "decision ledger decisions", MAX_DECISIONS)
        )
        return cls(
            value["ledger_id"],
            value["version"],
            value["boundary"],
            value["plan_id"],
            value["plan_address"],
            value["resolution_address"],
            value["federation_id"],
            value["federation_address"],
            decisions,
            value["operation_count"],
            value["decision_count"],
            value["pending_count"],
            value["approved_count"],
            value["held_count"],
            value["rejected_count"],
            value["deferred_count"],
            value["not_required_count"],
            value["accepted"],
            value["release_ready"],
            value["state"],
            value["content_address"],
        )


def address_ledger(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=LEDGER_PREFIX)


def decision_for_operation(
    operation: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation,
    disposition: str | None = None,
    *,
    note: str = "",
    evidence_addresses: Sequence[str] | None = None,
) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision:
    if not isinstance(operation, plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation):
        raise ValidationError("decision construction requires a typed plan operation")
    operation._validate()
    disposition = "not-required" if disposition is None and operation.action == "no-op" else "pending" if disposition is None else _label(disposition, "decision disposition")
    _validate_disposition(operation, disposition)
    evidence = tuple(evidence_addresses) if evidence_addresses is not None else (operation.content_address,)
    body = {
        "ordinal": operation.ordinal,
        "operation_address": operation.content_address,
        "peer_id": operation.peer_id,
        "registry_id": operation.registry_id,
        "entry_id": operation.entry_id,
        "package_id": operation.package_id,
        "source_state": operation.source_state,
        "action": operation.action,
        "plan_status": operation.status,
        "priority": operation.priority,
        "disposition": disposition,
        "status": _status_for(disposition),
        "requires_confirmation": operation.requires_confirmation,
        "note": _text(note, "decision note", 2048, required=False),
        "evidence_addresses": evidence,
    }
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision(**body, content_address=DECISION_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision(**body, content_address=address_decision(provisional))


def _decision_input(value: Any, operation: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision:
    if isinstance(value, str):
        return decision_for_operation(operation, value)
    if isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision):
        return value
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision.from_mapping(_mapping(value, "decision input"))


def _provided_decisions(plan: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan, decisions: Sequence[Any] | Mapping[str, Any] | None) -> dict[str, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision]:
    if decisions is None:
        return {}
    operations = {item.content_address: item for item in plan.operations}
    result: dict[str, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision] = {}
    if isinstance(decisions, Mapping):
        values = tuple((key, value) for key, value in decisions.items())
        if len(values) > MAX_DECISIONS:
            raise ValidationError("decision mapping exceeds its bound")
        for key, value in values:
            address = _address(key, "decision mapping operation address", plan_model.OPERATION_PREFIX)
            if address not in operations:
                raise ValidationError("decision mapping references an unknown operation")
            if address in result:
                raise ValidationError("decision mapping repeats an operation")
            result[address] = _decision_input(value, operations[address])
    else:
        for value in _sequence(decisions, "decision inputs", MAX_DECISIONS):
            decision = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision.from_mapping(value) if isinstance(value, Mapping) else value
            if not isinstance(decision, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision):
                raise ValidationError("decision inputs must be typed decisions or mappings")
            if decision.operation_address in result:
                raise ValidationError("decision inputs repeat an operation")
            if decision.operation_address not in operations:
                raise ValidationError("decision input references an unknown operation")
            result[decision.operation_address] = decision
    for address, decision in result.items():
        operation = operations[address]
        expected = decision_for_operation(operation, decision.disposition, note=decision.note, evidence_addresses=decision.evidence_addresses)
        if decision.to_dict() != expected.to_dict():
            raise ValidationError("decision input does not match its plan operation")
    return result


def build_ledger(
    plan: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan,
    decisions: Sequence[Any] | Mapping[str, Any] | None = None,
    *,
    ledger_id: str = DEFAULT_LEDGER_ID,
) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger:
    plan = plan_model.verify_plan(plan)
    supplied = _provided_decisions(plan, decisions)
    rows = tuple(supplied.get(operation.content_address, decision_for_operation(operation)) for operation in plan.operations)
    counts = {status: sum(item.status == status for item in rows) for status in STATUSES}
    accepted = not any(counts[status] for status in ("pending", "held", "rejected", "deferred"))
    release_ready = accepted and counts["not-required"] == len(rows)
    state = "blocked" if any(item.plan_status == "blocked" for item in rows) else "review" if any(item.plan_status == "review" for item in rows) or not accepted else "ready" if release_ready else "authorized"
    body = {
        "ledger_id": ledger_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "resolution_address": plan.resolution_address,
        "federation_id": plan.federation_id,
        "federation_address": plan.federation_address,
        "decisions": rows,
        "operation_count": len(rows),
        "decision_count": len(rows),
        "pending_count": counts["pending"],
        "approved_count": counts["approved"],
        "held_count": counts["held"],
        "rejected_count": counts["rejected"],
        "deferred_count": counts["deferred"],
        "not_required_count": counts["not-required"],
        "accepted": accepted,
        "release_ready": release_ready,
        "state": state,
    }
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger(**body, content_address=LEDGER_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger(**body, content_address=address_ledger(provisional))


def apply_decisions(
    plan: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan,
    decisions: Sequence[Any] | Mapping[str, Any],
    *,
    ledger_id: str = DEFAULT_LEDGER_ID,
) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger:
    """Build a ledger with explicit decisions while retaining pending rows."""

    return build_ledger(plan, decisions, ledger_id=ledger_id)


def ledger_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger:
    return verify_ledger(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger.from_mapping(value))


def verify_ledger(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger):
        raise ValidationError("decision ledger verification requires a typed ledger")
    value._validate()
    if not value.content_address.endswith(":pending") and address_ledger(value) != value.content_address:
        raise ValidationError("decision ledger address verification failed")
    for item in value.decisions:
        if not item.content_address.endswith(":pending") and address_decision(item) != item.content_address:
            raise ValidationError("decision address verification failed")
    return value


def ledger_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger) -> str:
    return canonical_json(verify_ledger(value).to_dict())


def ledger_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger) -> str:
    value = verify_ledger(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.decisions:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_ledger_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger) -> str:
    value = verify_ledger(value)
    lines = [
        "# Archive Registry Federation Reconciliation Decision Ledger",
        "",
        f"- State: `{value.state}`",
        f"- Accepted: `{value.accepted}`",
        f"- Release ready: `{value.release_ready}`",
        f"- Operations: `{value.operation_count}`",
        f"- Pending: `{value.pending_count}`",
        f"- Approved: `{value.approved_count}`",
        f"- Held: `{value.held_count}`",
        f"- Rejected: `{value.rejected_count}`",
        f"- Deferred: `{value.deferred_count}`",
        f"- No disposition required: `{value.not_required_count}`",
        "",
        "| # | peer | entry | action | disposition | status | note |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| {item.ordinal} | `{item.peer_id}` | `{item.entry_id}` | `{item.action}` | `{item.disposition}` | `{item.status}` | {item.note} |" for item in value.decisions)
    return "\n".join(lines) + "\n"


def decision_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision.FIELDS),
        "properties": {
            "ordinal": {"type": "integer", "minimum": 1},
            "operation_address": {"type": "string"},
            "peer_id": {"type": "string"},
            "registry_id": {"type": "string"},
            "entry_id": {"type": "string"},
            "package_id": {"type": "string"},
            "source_state": {"enum": list(plan_model.resolution_model.STATES)},
            "action": {"enum": list(plan_model.ACTIONS)},
            "plan_status": {"enum": list(plan_model.STATUSES)},
            "priority": {"enum": list(plan_model.PRIORITIES)},
            "disposition": {"enum": list(DISPOSITIONS)},
            "status": {"enum": list(STATUSES)},
            "requires_confirmation": {"type": "boolean"},
            "note": {"type": "string"},
            "evidence_addresses": {"type": "array", "items": {"type": "string"}},
            "content_address": {"type": "string"},
        },
    }


def ledger_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger.FIELDS),
        "properties": {
            "ledger_id": {"type": "string"},
            "version": {"type": "string"},
            "boundary": {"type": "string"},
            "plan_id": {"type": "string"},
            "plan_address": {"type": "string"},
            "resolution_address": {"type": "string"},
            "federation_id": {"type": "string"},
            "federation_address": {"type": "string"},
            "decisions": {"type": "array", "items": decision_schema()},
            "operation_count": {"type": "integer", "minimum": 1},
            "decision_count": {"type": "integer", "minimum": 1},
            "pending_count": {"type": "integer", "minimum": 0},
            "approved_count": {"type": "integer", "minimum": 0},
            "held_count": {"type": "integer", "minimum": 0},
            "rejected_count": {"type": "integer", "minimum": 0},
            "deferred_count": {"type": "integer", "minimum": 0},
            "not_required_count": {"type": "integer", "minimum": 0},
            "accepted": {"type": "boolean"},
            "release_ready": {"type": "boolean"},
            "state": {"enum": list(STATES)},
            "content_address": {"type": "string"},
        },
    }


def capabilities() -> dict[str, Any]:
    return {
        "version": VERSION,
        "boundary": BOUNDARY,
        "public": True,
        "bounded": True,
        "content_addressed": True,
        "analysis_only": True,
        "non_mutating": True,
        "operations": (
            "build_ledger",
            "apply_decisions",
            "decision_for_operation",
            "ledger_from_mapping",
            "ledger_json",
            "ledger_csv",
            "render_ledger_markdown",
            "verify_ledger",
        ),
        "dispositions": DISPOSITIONS,
        "statuses": STATUSES,
        "states": STATES,
        "reasons": REASONS,
        "max_decisions": MAX_DECISIONS,
    }


__all__ = [
    "BOUNDARY",
    "DECISION_PREFIX",
    "DEFAULT_LEDGER_ID",
    "DISPOSITIONS",
    "LEDGER_PREFIX",
    "MAX_DECISIONS",
    "REASONS",
    "STATES",
    "STATUSES",
    "VERSION",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger",
    "address_decision",
    "address_ledger",
    "apply_decisions",
    "build_ledger",
    "capabilities",
    "decision_for_operation",
    "decision_schema",
    "ledger_csv",
    "ledger_from_mapping",
    "ledger_json",
    "ledger_schema",
    "render_ledger_markdown",
    "verify_ledger",
]
