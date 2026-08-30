"""Independent assurance for federated evidence resolutions.

The resolution builder explains a quorum result, but an explanation is only
useful when it can be recomputed outside the builder.  This module performs a
fixed, addressed audit over links, ordering, state conservation, peer
evidence, action semantics, and the public boundary.  It emits a complete
report even when a hand-built public mapping is malformed, while normal typed
construction remains fail-closed.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution as resolution_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = resolution_model.VERSION + "-audit-v1"
BOUNDARY = resolution_model.BOUNDARY + "_audit"
AUDIT_PREFIX = resolution_model.RESOLUTION_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "resolution-linkage",
    "item-count",
    "item-order",
    "state-conservation",
    "action-state",
    "selected-replay",
    "missing-replay",
    "peer-evidence",
    "candidate-evidence",
    "address-links",
    "consensus-link",
    "public-boundary",
    "bounded-input",
    "resolution-address",
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
    return resolution_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck:
    """One recomputed resolution assurance finding."""

    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "resolution audit ordinal", MAX_CHECKS)
        self.check_id = _label(check_id, "resolution audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("resolution audit check ID is unsupported")
        self.passed = _bool(passed, "resolution audit result")
        self.detail = _text(detail, "resolution audit detail", 4096)
        self.evidence_addresses = tuple(_text(item, "resolution audit evidence address", 2048) for item in _sequence(evidence_addresses, "resolution audit evidence", resolution_model.MAX_ITEMS * 2 + 2))
        self.content_address = _address(content_address, "resolution audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "resolution audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("resolution audit check evidence is not public")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("resolution audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck":
        value = _mapping(value, "resolution audit check")
        _strict(value, set(cls.FIELDS), "resolution audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit:
    """The fixed-denominator independent audit report."""

    FIELDS = ("resolution_id", "resolution_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, resolution_id: str, resolution_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.resolution_id = _label(resolution_id, "resolution audit resolution ID")
        self.resolution_address = _address(resolution_address, "resolution audit resolution address", resolution_model.RESOLUTION_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck.from_mapping(item) for item in _sequence(checks, "resolution audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "resolution audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "resolution audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "resolution audit failed count", self.check_count)
        self.accepted = _bool(accepted, "resolution audit acceptance")
        self.content_address = _address(content_address, "resolution audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "resolution audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("resolution audit counters are not conserved")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("resolution audit checks are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("resolution audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("resolution audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"resolution_id": self.resolution_id, "resolution_address": self.resolution_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("resolution_id", "resolution_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit":
        value = _mapping(value, "resolution audit")
        _strict(value, set(cls.FIELDS), "resolution audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "resolution audit checks", MAX_CHECKS))
        return cls(value["resolution_id"], value["resolution_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_resolution(value: resolution_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit:
    value = resolution_model.verify_resolution(value)
    item_addresses = tuple(item.content_address for item in value.items)
    checks = (
        _check(1, "resolution-linkage", bool(value.federation_id and value.consensus_id and value.federation_address and value.consensus_address), "resolution retains both source identities and addresses", (value.content_address, value.federation_address, value.consensus_address)),
        _check(2, "item-count", value.entry_count == len(value.items) and value.entry_count > 0, "item count matches the materialized entries", item_addresses or (value.content_address,)),
        _check(3, "item-order", tuple(item.ordinal for item in value.items) == tuple(range(1, value.entry_count + 1)) and tuple(item.entry_id for item in value.items) == tuple(sorted(item.entry_id for item in value.items)), "resolution items are deterministically ordered", item_addresses or (value.content_address,)),
        _check(4, "state-conservation", value.resolved_count + value.review_count + value.blocked_count == value.entry_count, "resolved, review, and blocked rows conserve the entry total", (value.content_address,)),
        _check(5, "action-state", all((item.state == "resolved" and item.action == "retain-consensus") or (item.state == "review" and item.action == "review-divergence") or (item.state == "blocked" and item.action == "request-missing") for item in value.items), "every row action agrees with its disposition", item_addresses or (value.content_address,)),
        _check(6, "selected-replay", all((not item.selected_archive_address) or (item.selected_archive_address in item.candidate_addresses and len(item.supporting_peer_ids) >= item.required_quorum) for item in value.items), "selected addresses are candidate-backed and quorate", item_addresses or (value.content_address,)),
        _check(7, "missing-replay", all(item.presence_count + len(item.missing_peer_ids) >= item.observed_peer_count for item in value.items), "missing-peer evidence is bounded by observed peers", item_addresses or (value.content_address,)),
        _check(8, "peer-evidence", all(len(set(item.supporting_peer_ids) | set(item.missing_peer_ids) | set(item.dissenting_peer_ids)) <= value.peer_count for item in value.items), "peer evidence remains within federation membership", item_addresses or (value.content_address,)),
        _check(9, "candidate-evidence", all(item.selected_archive_address == "" or item.selected_archive_address in item.candidate_addresses for item in value.items), "selected addresses remain linked to candidates", item_addresses or (value.content_address,)),
        _check(10, "address-links", all(resolution_model.address_item(item) == item.content_address for item in value.items), "item content addresses replay", item_addresses or (value.content_address,)),
        _check(11, "consensus-link", value.consensus_address.startswith(resolution_model.consensus_model.CONSENSUS_PREFIX + ":"), "resolution retains the consensus address namespace", (value.consensus_address,)),
        _check(12, "public-boundary", _public(value.to_dict()), "resolution evidence contains no private runtime fields", (value.content_address,)),
        _check(13, "bounded-input", value.peer_count <= resolution_model.MAX_PEERS and value.entry_count <= resolution_model.MAX_ITEMS, "resolution limits are respected", (value.content_address,)),
        _check(14, "resolution-address", resolution_model.address_resolution(value) == value.content_address, "resolution content address replays", (value.content_address,)),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit(value.resolution_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit(provisional.resolution_id, provisional.resolution_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit):
        raise ValidationError("resolution audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("resolution audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Resolution Audit", "", f"- Resolution: `{value.resolution_id}`", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | result | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit.FIELDS), "properties": {"resolution_id": {"type": "string"}, "resolution_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "independent": True, "operations": ("audit_resolution", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_resolution", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
