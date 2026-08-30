"""Independent audit contract for archive-registry federations."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-audit-v1"
BOUNDARY = federation_model.BOUNDARY + "_audit"
AUDIT_PREFIX = federation_model.FEDERATION_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("peer-count", "peer-order", "peer-links", "observation-count", "observation-order", "observation-state", "observation-peer-links", "conflict-count", "address-replay", "public-boundary", "bounded-input", "federation-address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 2048, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} must use its public address namespace")
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
    return federation_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "federation audit ordinal", MAX_CHECKS)
        self.check_id = _label(check_id, "federation audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("federation audit check ID is unsupported")
        self.passed = _bool(passed, "federation audit check result")
        self.detail = _text(detail, "federation audit check detail", 4096)
        self.evidence_addresses = tuple(_text(item, "federation audit evidence address", 2048) for item in _sequence(evidence_addresses, "federation audit evidence", federation_model.MAX_ENTRIES + federation_model.MAX_PEERS))
        self.content_address = _address(content_address, "federation audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses:
            raise ValidationError("federation audit checks require evidence")
        if not _public(self.to_dict()):
            raise ValidationError("federation audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("federation audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck":
        value = _mapping(value, "federation audit check")
        _strict(value, set(cls.FIELDS), "federation audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit:
    FIELDS = ("federation_id", "federation_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, federation_id: str, federation_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.federation_id = _label(federation_id, "federation audit federation ID")
        self.federation_address = _address(federation_address, "federation audit federation address", federation_model.FEDERATION_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck.from_mapping(item) for item in _sequence(checks, "federation audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "federation audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "federation audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "federation audit failed count", self.check_count)
        self.accepted = _bool(accepted, "federation audit acceptance")
        self.content_address = _address(content_address, "federation audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("federation audit counters are not conserved")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("federation audit checks are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("federation audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("federation audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"federation_id": self.federation_id, "federation_address": self.federation_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("federation_id", "federation_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit":
        value = _mapping(value, "federation audit")
        _strict(value, set(cls.FIELDS), "federation audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "federation audit checks", MAX_CHECKS))
        return cls(value["federation_id"], value["federation_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_federation(value: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit:
    value = federation_model.verify_federation(value)
    addresses = tuple(peer.content_address for peer in value.peers) + tuple(item.content_address for item in value.observations)
    checks = (
        _check(1, "peer-count", value.peer_count == len(value.peers) and value.peer_count > 0, "peer count matches the materialized peer set", tuple(peer.content_address for peer in value.peers)),
        _check(2, "peer-order", tuple(peer.peer_id for peer in value.peers) == tuple(sorted(peer.peer_id for peer in value.peers)), "peer IDs are sorted for deterministic replay", tuple(peer.content_address for peer in value.peers)),
        _check(3, "peer-links", len({peer.peer_id for peer in value.peers}) == value.peer_count, "peer IDs are unique and addressable", tuple(peer.content_address for peer in value.peers)),
        _check(4, "observation-count", value.observation_count == len(value.observations) and value.observation_count > 0, "observation count matches the union of entry IDs", tuple(item.content_address for item in value.observations)),
        _check(5, "observation-order", tuple(item.entry_id for item in value.observations) == tuple(sorted(item.entry_id for item in value.observations)), "entry observations are sorted", tuple(item.content_address for item in value.observations)),
        _check(6, "observation-state", all(item.state in federation_model.STATES for item in value.observations), "every observation has a replayable state", tuple(item.content_address for item in value.observations)),
        _check(7, "observation-peer-links", all(item.peer_count == value.peer_count and set(item.peer_ids) == {peer.peer_id for peer in value.peers} for item in value.observations), "every observation links to every federation peer", tuple(item.content_address for item in value.observations)),
        _check(8, "conflict-count", value.conflict_count == value.divergent_count + value.missing_count, "divergent and missing rows are the conflict set", tuple(item.content_address for item in value.observations if item.state != "consistent") or (value.content_address,)),
        _check(9, "address-replay", all(federation_model.address_peer(peer) == peer.content_address for peer in value.peers) and all(federation_model.address_observation(item) == item.content_address for item in value.observations), "peer and observation addresses replay", addresses),
        _check(10, "public-boundary", _public(value.to_dict()), "federation projections contain no private path or runtime metadata", (value.content_address,)),
        _check(11, "bounded-input", value.peer_count <= federation_model.MAX_PEERS and value.observation_count <= federation_model.MAX_ENTRIES, "federation limits are respected", (value.content_address,)),
        _check(12, "federation-address", federation_model.address_federation(value) == value.content_address, "federation content address replays", (value.content_address,)),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit(value.federation_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit(provisional.federation_id, provisional.federation_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit):
        raise ValidationError("federation audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("federation audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address"), lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Audit", "", f"- Federation: `{value.federation_id}`", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | result | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit.FIELDS), "properties": {"federation_id": {"type": "string"}, "federation_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "independent": True, "operations": ("audit_federation", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_federation", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
