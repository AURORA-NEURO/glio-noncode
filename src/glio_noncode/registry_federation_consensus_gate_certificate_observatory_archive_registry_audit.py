"""Independent audit for certificate-observatory archive registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-audit-v1"
BOUNDARY = registry_model.BOUNDARY + "_audit"
AUDIT_PREFIX = registry_model.REGISTRY_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
CHECK_IDS = (
    "registry-address",
    "public-boundary",
    "entry-order",
    "entry-identity",
    "archive-addresses",
    "entry-addresses",
    "metrics-conservation",
    "index-address",
    "index-groups",
    "group-members",
    "group-counters",
    "package-cardinality",
    "mapping-round-trip",
    "path-free",
    "export-replay",
    "bounded-vocabulary",
)
MAX_TEXT = 2048


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
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
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return registry_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding:
    """One independently addressable registry assertion."""

    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry audit finding ordinal", len(CHECK_IDS))
        if self.ordinal == 0 or not isinstance(check_id, str) or check_id not in CHECK_IDS:
            raise ValidationError("registry audit finding check ID is undeclared")
        self.check_id = check_id
        self.passed = _bool(passed, "registry audit finding pass state")
        self.observed = _text(observed, "registry audit observed value", 1024)
        self.expected = _text(expected, "registry audit expected value", 1024)
        self.detail = _text(detail, "registry audit detail", 2048)
        self.evidence_address = _address(evidence_address, "registry audit evidence address")
        self.content_address = _address(content_address, "registry audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("registry audit finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding":
        value = _mapping(value, "registry audit finding")
        _strict(value, set(cls.FIELDS), "registry audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding):
        raise ValidationError("registry audit finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit:
    """Full registry audit; acceptance requires every declared check."""

    FIELDS = ("registry_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, registry_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.registry_address = _address(registry_address, "registry audit registry address", registry_model.REGISTRY_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding.from_mapping(item) for item in _sequence(checks, "registry audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "registry audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "registry audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "registry audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "registry audit acceptance")
        self.content_address = _address(content_address, "registry audit address", AUDIT_PREFIX)
        if self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("registry audit check order is not exact")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("registry audit counters are not conserved")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("registry audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_address": self.registry_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("registry_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit":
        value = _mapping(value, "registry audit")
        _strict(value, set(cls.FIELDS), "registry audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding.from_mapping(item) for item in _sequence(value["checks"], "registry audit checks", len(CHECK_IDS)))
        return cls(value["registry_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit):
        raise ValidationError("registry audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str, evidence: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding:
    observed_text = str(observed)
    expected_text = str(expected)
    if len(observed_text) > 1024:
        observed_text = observed_text[:1021] + "..."
    if len(expected_text) > 1024:
        expected_text = expected_text[:1021] + "..."
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding(ordinal, check_id, passed, observed_text, expected_text, detail, evidence, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding(ordinal, check_id, passed, provisional.observed, provisional.expected, detail, evidence, address_finding(provisional))


def audit_registry(value: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit:
    value = registry_model.verify_registry(value)
    entries = value.entries
    expected_entry_ids = tuple(sorted(item.entry_id for item in entries))
    expected_archive_addresses = tuple(sorted(item.archive_address for item in entries))
    derived_metrics = registry_model._metrics(entries)
    derived_index = registry_model._build_index(entries)
    round_trip = registry_model.registry_from_mapping(value.to_dict()).to_dict() == value.to_dict()
    bounded = len(entries) <= registry_model.MAX_ENTRIES and len(value.index.groups) <= registry_model.MAX_ENTRIES
    checks = (
        _finding(1, "registry-address", registry_model.address_registry(value) == value.content_address, value.content_address, registry_model.address_registry(value), "registry address reproduces from public fields", value.content_address),
        _finding(2, "public-boundary", _public(value.to_dict()), _public(value.to_dict()), True, "registry contains only public values", value.content_address),
        _finding(3, "entry-order", tuple(item.entry_id for item in entries) == expected_entry_ids, tuple(item.entry_id for item in entries), expected_entry_ids, "entry order is deterministic", value.content_address),
        _finding(4, "entry-identity", len({item.entry_id for item in entries}) == len(entries) and len({item.archive_id for item in entries}) == len(entries) and len({item.archive_address for item in entries}) == len(entries), "unique", "unique", "entry identities are unique", value.content_address),
        _finding(5, "archive-addresses", all(item.archive_address.startswith(registry_model.archive_model.ARCHIVE_PREFIX + ":") for item in entries), expected_archive_addresses, "archive addresses", "every entry links to an archive address", value.content_address),
        _finding(6, "entry-addresses", all(registry_model.address_entry(item) == item.content_address for item in entries), True, True, "every entry address replays", value.content_address),
        _finding(7, "metrics-conservation", derived_metrics.to_dict() == value.metrics.to_dict(), value.metrics.to_dict(), derived_metrics.to_dict(), "aggregate counters derive from entries", value.content_address),
        _finding(8, "index-address", registry_model.address_index(value.index) == value.index.content_address, value.index.content_address, registry_model.address_index(value.index), "package index address replays", value.index.content_address),
        _finding(9, "index-groups", derived_index.to_dict() == value.index.to_dict(), value.index.to_dict(), derived_index.to_dict(), "package groups derive from entries", value.index.content_address),
        _finding(10, "group-members", all(set(group.entry_ids) <= set(expected_entry_ids) and len(group.archive_addresses) == len(group.entry_ids) for group in value.index.groups), True, True, "package groups reference known entries", value.index.content_address),
        _finding(11, "group-counters", all(group.accepted_count + group.held_count == len(group.entry_ids) for group in value.index.groups), True, True, "package group counters conserve members", value.index.content_address),
        _finding(12, "package-cardinality", value.metrics.unique_package_count == len(value.index.groups), value.metrics.unique_package_count, len(value.index.groups), "package cardinality matches index groups", value.index.content_address),
        _finding(13, "mapping-round-trip", round_trip, round_trip, True, "public mapping reloads exactly", value.content_address),
        _finding(14, "path-free", _public(value.to_dict()), True, True, "registry projection does not expose paths", value.content_address),
        _finding(15, "export-replay", bool(registry_model.registry_from_mapping(value.to_dict()).to_dict() == value.to_dict() and registry_model.registry_json(value)), True, True, "JSON export is replayable", value.content_address),
        _finding(16, "bounded-vocabulary", bounded, bounded, True, "entry and group counts remain bounded", value.content_address),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit(provisional.registry_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_registry_directory(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit:
    return audit_registry(registry_model.load_registry(source))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit:
    value = _mapping(value, "registry audit")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit.FIELDS), "registry audit")
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("registry audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    fields = ("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow({field: item.to_dict()[field] for field in fields})
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Archive Registry Audit", "", f"- Registry: `{value.registry_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit.FIELDS), "properties": {"registry_address": {"type": "string", "pattern": "^" + registry_model.REGISTRY_PREFIX + ":"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS), "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent registry verification", "entry identity checks", "metrics conservation", "package index replay", "bounded vocabulary checks", "addressable findings", "path-free JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "FINDING_PREFIX",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAuditFinding",
    "VERSION",
    "address_audit",
    "address_finding",
    "audit_csv",
    "audit_from_mapping",
    "audit_json",
    "audit_registry",
    "audit_registry_directory",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
