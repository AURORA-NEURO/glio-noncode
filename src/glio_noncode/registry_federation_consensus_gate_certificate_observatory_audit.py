"""Independent audit for the certificate-history observatory projection."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate as certificate_model
from . import registry_federation_consensus_gate_certificate_observatory as observatory_model
from . import registry_federation_consensus_gate_certificate_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = observatory_model.VERSION + "-audit-v1"
BOUNDARY = observatory_model.BOUNDARY + "_audit"
AUDIT_PREFIX = observatory_model.OBSERVATORY_PREFIX + "-audit"
FINDING_PREFIX = observatory_model.OBSERVATORY_PREFIX + "-audit-finding"
CHECK_IDS = ("exact-fields", "public-boundary", "history-conservation", "observation-conservation", "ordinal-conservation", "counter-conservation", "history-addresses", "entry-ordinals", "entry-addresses", "certificate-addresses", "audit-addresses", "disposition-vocabulary", "acceptance-conservation", "mapping-round-trip", "content-address", "path-free")


def _text(value: Any, field: str, maximum: int = observatory_model.MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unsupported address")
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.lower() not in forbidden and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return all(marker not in lowered for marker in ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\"))
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateCertificateObservatoryAuditFinding:
    """One independently recomputed observatory invariant."""

    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate observatory audit finding ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "certificate observatory audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("certificate observatory audit check ID is unsupported")
        self.passed = _bool(passed, "certificate observatory audit finding result")
        self.observed = _text(observed, "certificate observatory audit observed value")
        self.expected = _text(expected, "certificate observatory audit expected value")
        self.detail = _text(detail, "certificate observatory audit detail", required=True)
        self.content_address = _address(content_address, "certificate observatory audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("certificate observatory audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryAuditFinding:
        value = _mapping(value, "certificate observatory audit finding")
        _strict(value, set(cls.FIELDS), "certificate observatory audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryAuditFinding):
        raise ValidationError("certificate observatory finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryAudit:
    """Addressed independent audit of one certificate observatory."""

    FIELDS = ("observatory_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, observatory_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.observatory_address = _address(observatory_address, "audited certificate observatory address", observatory_model.OBSERVATORY_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateObservatoryAuditFinding) for item in self.checks):
            raise ValidationError("certificate observatory audit checks must be typed")
        self.check_count = _count(check_count, "certificate observatory audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "certificate observatory audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "certificate observatory audit failed count", self.check_count)
        self.accepted = _bool(accepted, "certificate observatory audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("certificate observatory audit counters are not conserved")
        self.content_address = _address(content_address, "certificate observatory audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("certificate observatory audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"observatory_address": self.observatory_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryAudit:
        value = _mapping(value, "certificate observatory audit")
        _strict(value, set(cls.FIELDS), "certificate observatory audit")
        return cls(value["observatory_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryAudit):
        raise ValidationError("certificate observatory audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateCertificateObservatoryAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_observatory(value: observatory_model.RegistryFederationConsensusGateCertificateObservatory) -> RegistryFederationConsensusGateCertificateObservatoryAudit:
    """Recompute aggregate counts, ordered membership, links, and identity."""

    value = observatory_model.verify_observatory(value)
    observations = value.observations
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(observatory_model.RegistryFederationConsensusGateCertificateObservatory.FIELDS), tuple(sorted(value.to_dict())), observatory_model.RegistryFederationConsensusGateCertificateObservatory.FIELDS, "observatory fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "observatory is public and path-free"),
        _finding(3, "history-conservation", len(value.history_addresses) == value.history_count, (len(value.history_addresses), value.history_count), "history count", "history membership matches count"),
        _finding(4, "observation-conservation", len(observations) == value.observation_count, (len(observations), value.observation_count), "observation count", "observation membership matches count"),
        _finding(5, "ordinal-conservation", tuple(item.ordinal for item in observations) == tuple(range(1, value.observation_count + 1)), tuple(item.ordinal for item in observations), tuple(range(1, value.observation_count + 1)), "observation ordinals are contiguous"),
        _finding(6, "counter-conservation", value.issued_count == sum(item.state == "issued" for item in observations) and value.withheld_count == sum(item.state == "withheld" for item in observations) and value.accepted_count == sum(item.accepted for item in observations) and value.held_count == sum(not item.accepted for item in observations) and value.total_check_count == sum(item.check_count for item in observations) and value.total_failed_count == sum(item.failed_count for item in observations), (value.issued_count, value.withheld_count, value.accepted_count, value.held_count, value.total_check_count, value.total_failed_count), "replayed counters", "observatory counters replay"),
        _finding(7, "history-addresses", len(set(value.history_addresses)) == value.history_count and all(item.history_address in value.history_addresses for item in observations), "unique history addresses", "every observation history address", "history references are conserved"),
        _finding(8, "entry-ordinals", all(1 <= item.entry_ordinal <= history_model.MAX_ENTRIES for item in observations), "bounded entry ordinals", history_model.MAX_ENTRIES, "entry ordinals remain bounded"),
        _finding(9, "entry-addresses", all(item.entry_address.startswith(history_model.ENTRY_PREFIX + ":") for item in observations), "entry address vocabulary", history_model.ENTRY_PREFIX + ":", "entry references are addressed"),
        _finding(10, "certificate-addresses", all(item.certificate_address.startswith(certificate_model.CERTIFICATE_PREFIX + ":") for item in observations), "certificate address vocabulary", certificate_model.CERTIFICATE_PREFIX + ":", "certificate references are addressed"),
        _finding(11, "audit-addresses", all(item.audit_address.startswith(certificate_model.CERTIFICATE_PREFIX + "-audit:") for item in observations), "audit address vocabulary", certificate_model.CERTIFICATE_PREFIX + "-audit:", "audit references are addressed"),
        _finding(12, "disposition-vocabulary", all(item.state in observatory_model.STATES and item.decision in observatory_model.DECISIONS for item in observations), observatory_model.STATES, observatory_model.DECISIONS, "observations use certificate disposition vocabulary"),
        _finding(13, "acceptance-conservation", all(item.accepted == (item.state == "issued" and item.decision == "promote" and item.failed_count == 0) for item in observations), "observation acceptance", "issued/promote with zero failures", "acceptance is fail-closed"),
        _finding(14, "mapping-round-trip", observatory_model.observatory_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original observatory", "mapping conversion is lossless"),
        _finding(15, "content-address", observatory_model.address_observatory(value) == value.content_address, value.content_address, observatory_model.address_observatory(value), "observatory content address replays"),
        _finding(16, "path-free", _public(value.to_dict()), True, True, "observatory contains no local paths or attribution metadata"),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryAudit(provisional.observatory_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryAudit) -> RegistryFederationConsensusGateCertificateObservatoryAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("certificate observatory audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Release Certificate Observatory Audit", "", f"- Observatory: `{value.observatory_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryAudit.FIELDS), "properties": {"observatory_address": {"type": "string", "pattern": "^" + observatory_model.OBSERVATORY_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent certificate observatory checks", "history and observation conservation", "issued and withheld counter validation", "certificate and audit link validation", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryAudit", "RegistryFederationConsensusGateCertificateObservatoryAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_observatory", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
