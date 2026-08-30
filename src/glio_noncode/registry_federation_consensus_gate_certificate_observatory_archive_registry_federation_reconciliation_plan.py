"""Non-mutating per-peer reconciliation plans for registry federations.

The resolution layer says what the evidence means.  This layer says what an
operator could do next, without touching a downloaded registry.  Every peer
and entry receives exactly one operation: retain the matching evidence, ask a
missing peer to retrieve the quorate entry, replace a present dissenting copy,
or route an unresolved row to manual review.  Operations are public receipts,
not executable filesystem commands.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus as consensus_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution as resolution_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = resolution_model.VERSION + "-reconciliation-plan-v1"
BOUNDARY = resolution_model.BOUNDARY + "_reconciliation_plan"
PLAN_PREFIX = resolution_model.RESOLUTION_PREFIX + "-plan"
OPERATION_PREFIX = PLAN_PREFIX + "-operation"
DEFAULT_PLAN_ID = "consensus-certificate-observatory-archive-registry-federation-reconciliation-plan"
MAX_OPERATIONS = resolution_model.MAX_ITEMS * resolution_model.MAX_PEERS

ACTIONS = ("no-op", "request-missing", "replace-with-consensus", "manual-review")
STATUSES = ("no-op", "planned", "review", "blocked")
PRIORITIES = ("none", "high", "critical")
REASONS = ("already-matches-selected", "missing-peer-can-retrieve-quorum-entry", "present-peer-diverges-from-quorum-entry", "quorum-unavailable", "multiple-nonquorate-candidates")


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
    return resolution_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation:
    """One path-free suggested operation for one peer and one entry."""

    FIELDS = ("ordinal", "peer_id", "registry_id", "entry_id", "package_id", "source_state", "action", "status", "priority", "observed_archive_address", "desired_archive_address", "requires_confirmation", "reason", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, peer_id: str, registry_id: str, entry_id: str, package_id: str, source_state: str, action: str, status: str, priority: str, observed_archive_address: str, desired_archive_address: str, requires_confirmation: bool, reason: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "reconciliation operation ordinal", MAX_OPERATIONS, positive=True)
        self.peer_id = _label(peer_id, "reconciliation operation peer ID")
        self.registry_id = _label(registry_id, "reconciliation operation registry ID")
        self.entry_id = _label(entry_id, "reconciliation operation entry ID")
        self.package_id = _label(package_id, "reconciliation operation package ID", required=False)
        self.source_state = _label(source_state, "reconciliation operation source state")
        self.action = _label(action, "reconciliation operation action")
        self.status = _label(status, "reconciliation operation status")
        self.priority = _label(priority, "reconciliation operation priority")
        self.observed_archive_address = _address(observed_archive_address, "reconciliation observed archive address", federation_model.registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.desired_archive_address = _address(desired_archive_address, "reconciliation desired archive address", federation_model.registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.requires_confirmation = _bool(requires_confirmation, "reconciliation confirmation requirement")
        self.reason = _label(reason, "reconciliation operation reason")
        self.evidence_addresses = tuple(_text(item, "reconciliation operation evidence address", 2048) for item in _sequence(evidence_addresses, "reconciliation operation evidence", resolution_model.MAX_PEERS + 4))
        self.content_address = _address(content_address, "reconciliation operation address", OPERATION_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "reconciliation operation address")
        self._validate()

    def _validate(self) -> None:
        if self.source_state not in resolution_model.STATES or self.action not in ACTIONS or self.status not in STATUSES or self.priority not in PRIORITIES or self.reason not in REASONS or not self.evidence_addresses:
            raise ValidationError("reconciliation operation vocabulary is unsupported")
        if self.action == "no-op" and (self.status != "no-op" or self.priority != "none" or not self.observed_archive_address or self.desired_archive_address != self.observed_archive_address or self.requires_confirmation):
            raise ValidationError("no-op reconciliation operation is not conserved")
        if self.action == "request-missing" and (self.observed_archive_address or self.status not in {"planned", "blocked"} or not self.requires_confirmation or (self.status == "planned" and (not self.desired_archive_address or self.reason != "missing-peer-can-retrieve-quorum-entry")) or (self.status == "blocked" and (self.desired_archive_address or self.reason != "quorum-unavailable"))):
            raise ValidationError("missing-entry operation is not conserved")
        if self.action == "replace-with-consensus" and (not self.observed_archive_address or not self.desired_archive_address or self.observed_archive_address == self.desired_archive_address or self.status != "planned" or not self.requires_confirmation):
            raise ValidationError("replacement operation is not conserved")
        if self.action == "manual-review" and (self.status not in {"review", "blocked"} or self.priority != "critical" or not self.requires_confirmation or self.desired_archive_address):
            raise ValidationError("manual-review operation is not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("reconciliation operation crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_operation(self) != self.content_address:
            raise ValidationError("reconciliation operation address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "evidence_addresses"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation":
        value = _mapping(value, "reconciliation operation")
        _strict(value, set(cls.FIELDS), "reconciliation operation")
        return cls(*(value[field] for field in cls.FIELDS))


def address_operation(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OPERATION_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan:
    """A complete, non-mutating reconciliation plan for a federation."""

    FIELDS = ("plan_id", "version", "boundary", "resolution_id", "resolution_address", "federation_id", "federation_address", "operations", "peer_count", "entry_count", "operation_count", "noop_count", "request_count", "replace_count", "review_count", "blocked_count", "accepted", "release_ready", "state", "content_address")

    def __init__(self, plan_id: str, version: str, boundary: str, resolution_id: str, resolution_address: str, federation_id: str, federation_address: str, operations: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation], peer_count: int, entry_count: int, operation_count: int, noop_count: int, request_count: int, replace_count: int, review_count: int, blocked_count: int, accepted: bool, release_ready: bool, state: str, content_address: str) -> None:
        self.plan_id = _label(plan_id, "reconciliation plan ID")
        self.version = _text(version, "reconciliation plan version")
        self.boundary = _text(boundary, "reconciliation plan boundary", 512)
        self.resolution_id = _label(resolution_id, "reconciliation plan resolution ID")
        self.resolution_address = _address(resolution_address, "reconciliation plan resolution address", resolution_model.RESOLUTION_PREFIX)
        self.federation_id = _label(federation_id, "reconciliation plan federation ID")
        self.federation_address = _address(federation_address, "reconciliation plan federation address", federation_model.FEDERATION_PREFIX)
        self.operations = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation.from_mapping(item) for item in _sequence(operations, "reconciliation operations", MAX_OPERATIONS))
        self.peer_count = _count(peer_count, "reconciliation plan peer count", resolution_model.MAX_PEERS, positive=True)
        self.entry_count = _count(entry_count, "reconciliation plan entry count", resolution_model.MAX_ITEMS, positive=True)
        self.operation_count = _count(operation_count, "reconciliation plan operation count", MAX_OPERATIONS, positive=True)
        self.noop_count = _count(noop_count, "reconciliation plan no-op count", self.operation_count)
        self.request_count = _count(request_count, "reconciliation plan request count", self.operation_count)
        self.replace_count = _count(replace_count, "reconciliation plan replacement count", self.operation_count)
        self.review_count = _count(review_count, "reconciliation plan review count", self.operation_count)
        self.blocked_count = _count(blocked_count, "reconciliation plan blocked count", self.operation_count)
        self.accepted = _bool(accepted, "reconciliation plan acceptance")
        self.release_ready = _bool(release_ready, "reconciliation plan release readiness")
        self.state = _label(state, "reconciliation plan state")
        self.content_address = _address(content_address, "reconciliation plan address", PLAN_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "reconciliation plan address")
        self._validate()

    def _validate(self) -> None:
        if self.operation_count != len(self.operations) or self.operation_count != self.peer_count * self.entry_count:
            raise ValidationError("reconciliation plan operation count does not cover the matrix")
        if tuple(item.ordinal for item in self.operations) != tuple(range(1, self.operation_count + 1)) or len({(item.peer_id, item.entry_id) for item in self.operations}) != self.operation_count:
            raise ValidationError("reconciliation plan operations are not canonical")
        if self.noop_count != sum(item.action == "no-op" for item in self.operations) or self.request_count != sum(item.action == "request-missing" for item in self.operations) or self.replace_count != sum(item.action == "replace-with-consensus" for item in self.operations) or self.review_count != sum(item.action == "manual-review" for item in self.operations) or self.blocked_count != sum(item.status == "blocked" for item in self.operations):
            raise ValidationError("reconciliation plan counters do not replay")
        expected_state = "blocked" if self.blocked_count else "review" if any(item.action != "no-op" for item in self.operations) else "ready"
        if self.state != expected_state or self.accepted != (self.blocked_count == 0) or self.release_ready != (self.state == "ready"):
            raise ValidationError("reconciliation plan outcome does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("reconciliation plan crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_plan(self) != self.content_address:
            raise ValidationError("reconciliation plan address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"plan_id": self.plan_id, "version": self.version, "boundary": self.boundary, "resolution_id": self.resolution_id, "resolution_address": self.resolution_address, "federation_id": self.federation_id, "federation_address": self.federation_address, "operations": tuple(item.to_dict() for item in self.operations), "peer_count": self.peer_count, "entry_count": self.entry_count, "operation_count": self.operation_count, "noop_count": self.noop_count, "request_count": self.request_count, "replace_count": self.replace_count, "review_count": self.review_count, "blocked_count": self.blocked_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("plan_id", "version", "boundary", "resolution_id", "resolution_address", "federation_id", "federation_address", "peer_count", "entry_count", "operation_count", "noop_count", "request_count", "replace_count", "review_count", "blocked_count", "accepted", "release_ready", "state", "content_address")}

    def operation(self, peer_id: str, entry_id: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation:
        peer_id = _label(peer_id, "reconciliation operation peer ID")
        entry_id = _label(entry_id, "reconciliation operation entry ID")
        for item in self.operations:
            if item.peer_id == peer_id and item.entry_id == entry_id:
                return item
        raise ValidationError("reconciliation operation was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan":
        value = _mapping(value, "reconciliation plan")
        _strict(value, set(cls.FIELDS), "reconciliation plan")
        operations = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation.from_mapping(item) for item in _sequence(value["operations"], "reconciliation operations", MAX_OPERATIONS))
        return cls(value["plan_id"], value["version"], value["boundary"], value["resolution_id"], value["resolution_address"], value["federation_id"], value["federation_address"], operations, value["peer_count"], value["entry_count"], value["operation_count"], value["noop_count"], value["request_count"], value["replace_count"], value["review_count"], value["blocked_count"], value["accepted"], value["release_ready"], value["state"], value["content_address"])


def address_plan(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PLAN_PREFIX)


def _observed_by_peer(consensus: consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for decision in consensus.decisions:
        for candidate in consensus.candidates:
            if candidate.entry_id == decision.entry_id:
                for peer_id in candidate.peer_ids:
                    result.setdefault(peer_id, {})[decision.entry_id] = candidate.archive_address
    return result


def _operation(ordinal: int, peer: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer, item: resolution_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem, observed: str, *, federation_observation_address: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation:
    if item.state == "resolved":
        if observed == item.selected_archive_address:
            action, status, priority, desired, confirmation, reason = "no-op", "no-op", "none", observed, False, "already-matches-selected"
        elif not observed:
            action, status, priority, desired, confirmation, reason = "request-missing", "planned", "high", item.selected_archive_address, True, "missing-peer-can-retrieve-quorum-entry"
        else:
            action, status, priority, desired, confirmation, reason = "replace-with-consensus", "planned", "high", item.selected_archive_address, True, "present-peer-diverges-from-quorum-entry"
    elif item.state == "blocked":
        if observed:
            action, desired, reason = "manual-review", "", "quorum-unavailable"
        else:
            action, desired, reason = "request-missing", "", "quorum-unavailable"
        status, priority, confirmation = "blocked", "critical", True
    else:
        action, status, priority, desired, confirmation, reason = "manual-review", "review", "critical", "", True, "multiple-nonquorate-candidates"
    evidence = (item.content_address, federation_observation_address) + tuple(item.evidence_addresses[:2])
    body = dict(ordinal=ordinal, peer_id=peer.peer_id, registry_id=peer.registry_id, entry_id=item.entry_id, package_id=item.package_id, source_state=item.state, action=action, status=status, priority=priority, observed_archive_address=observed, desired_archive_address=desired, requires_confirmation=confirmation, reason=reason, evidence_addresses=evidence)
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation(**body, content_address=OPERATION_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation(**body, content_address=address_operation(provisional))


def build_plan(
    federation: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation,
    resolution: resolution_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution,
    *,
    consensus: consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus | None = None,
    plan_id: str = DEFAULT_PLAN_ID,
) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan:
    federation = federation_model.verify_federation(federation)
    resolution = resolution_model.verify_resolution(resolution)
    selected_consensus = consensus_model.build_consensus(federation) if consensus is None else consensus_model.verify_consensus(consensus)
    if resolution.federation_address != federation.content_address or resolution.federation_id != federation.federation_id or resolution.consensus_address != selected_consensus.content_address:
        raise ValidationError("reconciliation plan inputs do not share one federation and consensus")
    observations = {item.entry_id: item for item in federation.observations}
    observed = _observed_by_peer(selected_consensus)
    peers = tuple(sorted(federation.peers, key=lambda item: item.peer_id))
    items = {item.entry_id: item for item in resolution.items}
    operations: list[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation] = []
    ordinal = 1
    for entry_id in sorted(items):
        item = items[entry_id]
        observation = observations[entry_id]
        for peer in peers:
            operations.append(_operation(ordinal, peer, item, observed.get(peer.peer_id, {}).get(entry_id, ""), federation_observation_address=observation.content_address))
            ordinal += 1
    counts = {action: sum(operation.action == action for operation in operations) for action in ACTIONS}
    body = dict(plan_id=plan_id, version=VERSION, boundary=BOUNDARY, resolution_id=resolution.resolution_id, resolution_address=resolution.content_address, federation_id=federation.federation_id, federation_address=federation.content_address, operations=tuple(operations), peer_count=federation.peer_count, entry_count=resolution.entry_count, operation_count=len(operations), noop_count=counts["no-op"], request_count=counts["request-missing"], replace_count=counts["replace-with-consensus"], review_count=counts["manual-review"], blocked_count=sum(operation.status == "blocked" for operation in operations), accepted=all(operation.status != "blocked" for operation in operations), release_ready=all(operation.status == "no-op" for operation in operations), state="blocked" if any(operation.status == "blocked" for operation in operations) else "review" if any(operation.action != "no-op" for operation in operations) else "ready")
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan(**body, content_address=PLAN_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan(**body, content_address=address_plan(provisional))


def plan_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan:
    return verify_plan(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan.from_mapping(value))


def verify_plan(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan):
        raise ValidationError("reconciliation plan verification requires a typed plan")
    value._validate()
    if not value.content_address.endswith(":pending") and address_plan(value) != value.content_address:
        raise ValidationError("reconciliation plan address verification failed")
    return value


def plan_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan) -> str:
    return canonical_json(verify_plan(value).to_dict())


def plan_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan) -> str:
    value = verify_plan(value)
    stream = io.StringIO()
    fields = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation.FIELDS
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.operations:
        row = item.to_dict()
        for field in fields:
            if isinstance(row[field], tuple):
                row[field] = ",".join(row[field])
        writer.writerow(row)
    return stream.getvalue()


def render_plan_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan) -> str:
    value = verify_plan(value)
    lines = ["# Archive Registry Federation Reconciliation Plan", "", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Operations: `{value.operation_count}`", f"- No-op: `{value.noop_count}`", f"- Requests: `{value.request_count}`", f"- Replacements: `{value.replace_count}`", f"- Manual review: `{value.review_count}`", f"- Blocked: `{value.blocked_count}`", "", "| # | peer | entry | action | status | observed | desired |", "| ---: | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.peer_id}` | `{item.entry_id}` | `{item.action}` | `{item.status}` | `{item.observed_archive_address}` | `{item.desired_archive_address}` |" for item in value.operations)
    return "\n".join(lines) + "\n"


def operation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "peer_id": {"type": "string"}, "registry_id": {"type": "string"}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "source_state": {"enum": list(resolution_model.STATES)}, "action": {"enum": list(ACTIONS)}, "status": {"enum": list(STATUSES)}, "priority": {"enum": list(PRIORITIES)}, "observed_archive_address": {"type": "string"}, "desired_archive_address": {"type": "string"}, "requires_confirmation": {"type": "boolean"}, "reason": {"enum": list(REASONS)}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def plan_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan.FIELDS), "properties": {"plan_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resolution_id": {"type": "string"}, "resolution_address": {"type": "string"}, "federation_id": {"type": "string"}, "federation_address": {"type": "string"}, "operations": {"type": "array", "items": operation_schema()}, "peer_count": {"type": "integer", "minimum": 1}, "entry_count": {"type": "integer", "minimum": 1}, "operation_count": {"type": "integer", "minimum": 1}, "noop_count": {"type": "integer", "minimum": 0}, "request_count": {"type": "integer", "minimum": 0}, "replace_count": {"type": "integer", "minimum": 0}, "review_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["ready", "review", "blocked"]}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "analysis_only": True, "operations": ("build_plan", "plan_from_mapping", "plan_json", "plan_csv", "render_plan_markdown", "verify_plan"), "actions": ACTIONS, "statuses": STATUSES, "priorities": PRIORITIES, "reasons": REASONS, "max_operations": MAX_OPERATIONS}


__all__ = ["ACTIONS", "BOUNDARY", "DEFAULT_PLAN_ID", "MAX_OPERATIONS", "OPERATION_PREFIX", "PLAN_PREFIX", "PRIORITIES", "REASONS", "STATUSES", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan", "address_operation", "address_plan", "build_plan", "capabilities", "operation_schema", "plan_csv", "plan_from_mapping", "plan_json", "plan_schema", "render_plan_markdown", "verify_plan"]
