"""Independent audit of quorum-based federation decisions."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus as consensus_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = consensus_model.VERSION + "-audit-v1"
BOUNDARY = consensus_model.BOUNDARY + "_audit"
AUDIT_PREFIX = consensus_model.CONSENSUS_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("decision-count", "decision-order", "quorum-bound", "candidate-links", "selected-quorum", "held-without-selection", "counter-conservation", "candidate-support", "evidence-links", "outcome-replay", "public-boundary", "consensus-address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
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
    return consensus_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "consensus audit ordinal", len(CHECK_IDS))
        self.check_id = _label(check_id, "consensus audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("consensus audit check ID is unsupported")
        self.passed = _bool(passed, "consensus audit result")
        self.detail = _text(detail, "consensus audit detail")
        self.evidence_addresses = tuple(_text(item, "consensus audit evidence address", 2048) for item in _sequence(evidence_addresses, "consensus audit evidence", consensus_model.MAX_DECISIONS + 2))
        self.content_address = _address(content_address, "consensus audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "consensus audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("consensus audit check is not public or evidenced")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("consensus audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck":
        value = _mapping(value, "consensus audit check")
        _strict(value, set(cls.FIELDS), "consensus audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit:
    FIELDS = ("consensus_id", "consensus_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, consensus_id: str, consensus_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.consensus_id = _label(consensus_id, "consensus audit ID")
        self.consensus_address = _address(consensus_address, "consensus audit consensus address", consensus_model.CONSENSUS_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck.from_mapping(item) for item in _sequence(checks, "consensus audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "consensus audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "consensus audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "consensus audit failed count", self.check_count)
        self.accepted = _bool(accepted, "consensus audit acceptance")
        self.content_address = _address(content_address, "consensus audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "consensus audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(self.checks) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("consensus audit counters or order are not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("consensus audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("consensus audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"consensus_id": self.consensus_id, "consensus_address": self.consensus_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("consensus_id", "consensus_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit":
        value = _mapping(value, "consensus audit")
        _strict(value, set(cls.FIELDS), "consensus audit")
        return cls(value["consensus_id"], value["consensus_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "consensus audit checks", len(CHECK_IDS))), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_consensus(value: consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit:
    value = consensus_model.verify_consensus(value)
    evidence = tuple(item.content_address for item in value.decisions)
    checks = (
        _check(1, "decision-count", value.entry_count == len(value.decisions) and value.entry_count > 0, "decision count matches the federation entry set", evidence),
        _check(2, "decision-order", tuple(item.ordinal for item in value.decisions) == tuple(range(1, value.entry_count + 1)) and tuple(item.entry_id for item in value.decisions) == tuple(sorted(item.entry_id for item in value.decisions)), "decisions are ordered by entry ID", evidence),
        _check(3, "quorum-bound", 1 <= value.quorum <= value.peer_count, "quorum is inside the peer bound", (value.content_address,)),
        _check(4, "candidate-links", all(item.expected_peer_count == value.peer_count and item.quorum == value.quorum for item in value.candidates), "candidate rows link to the federation quorum", tuple(item.content_address for item in value.candidates) or (value.content_address,)),
        _check(5, "selected-quorum", all(item.state != "selected" or item.support_count >= item.quorum for item in value.decisions), "every selected address reaches quorum", evidence),
        _check(6, "held-without-selection", all((item.state == "held" and not item.selected_address) or (item.state == "selected" and bool(item.selected_address)) for item in value.decisions), "held decisions do not expose a selected address", evidence),
        _check(7, "counter-conservation", value.selected_count + value.held_count == value.entry_count, "selected and held decisions conserve all entries", (value.content_address,)),
        _check(8, "candidate-support", all(item.support_count == len(item.peer_ids) and tuple(sorted(item.peer_ids)) == item.peer_ids for item in value.candidates), "candidate support equals its peer evidence", tuple(item.content_address for item in value.candidates) or (value.content_address,)),
        _check(9, "evidence-links", all(item.evidence_addresses for item in value.decisions), "every decision retains observation and candidate evidence", evidence),
        _check(10, "outcome-replay", value.accepted == (value.held_count == 0) and value.decision == ("accept" if value.accepted else "hold"), "consensus outcome replays from held count", (value.content_address,)),
        _check(11, "public-boundary", _public(value.to_dict()), "consensus contains only public typed data", (value.content_address,)),
        _check(12, "consensus-address", consensus_model.address_consensus(value) == value.content_address, "consensus content address replays", (value.content_address,)),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit(value.consensus_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit(provisional.consensus_id, provisional.consensus_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit):
        raise ValidationError("consensus audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("consensus audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Consensus Audit", "", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit.FIELDS), "properties": {"consensus_id": {"type": "string"}, "consensus_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "independent": True, "operations": ("audit_consensus", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAuditCheck", "address_audit", "address_check", "audit_consensus", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
