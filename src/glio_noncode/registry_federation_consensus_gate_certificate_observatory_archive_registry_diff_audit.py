"""Independent validation for archive-registry version diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
CHECK_IDS = ("diff-address", "side-links", "item-order", "change-counts", "added-shape", "removed-shape", "changed-shape", "changed-fields", "entry-identity", "public-boundary", "mapping-round-trip", "bounded-diff", "side-replay")


def _text(value: Any, field: str, maximum: int = 2048, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public address")
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


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff audit finding ordinal", len(CHECK_IDS))
        if self.ordinal == 0 or check_id not in CHECK_IDS:
            raise ValidationError("diff audit finding check ID is undeclared")
        self.check_id = check_id
        self.passed = _bool(passed, "diff audit finding state")
        self.observed = _text(observed, "diff audit observed value", 1024)
        self.expected = _text(expected, "diff audit expected value", 1024)
        self.detail = _text(detail, "diff audit detail", 2048)
        self.evidence_address = _address(evidence_address, "diff audit evidence address")
        self.content_address = _address(content_address, "diff audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("diff audit finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding":
        value = _mapping(value, "diff audit finding")
        _strict(value, set(cls.FIELDS), "diff audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding):
        raise ValidationError("diff audit finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit:
    FIELDS = ("diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, diff_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_address = _address(diff_address, "diff audit diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding.from_mapping(item) for item in _sequence(checks, "diff audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "diff audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "diff audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "diff audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "diff audit acceptance")
        self.content_address = _address(content_address, "diff audit address", AUDIT_PREFIX)
        if self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("diff audit checks are not canonical")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("diff audit counters are not conserved")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("diff audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("diff_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit":
        value = _mapping(value, "diff audit")
        _strict(value, set(cls.FIELDS), "diff audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding.from_mapping(item) for item in _sequence(value["checks"], "diff audit checks", len(CHECK_IDS)))
        return cls(value["diff_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit):
        raise ValidationError("diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str, evidence: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding:
    observed_text = str(observed)
    expected_text = str(expected)
    if len(observed_text) > 1024:
        observed_text = observed_text[:1021] + "..."
    if len(expected_text) > 1024:
        expected_text = expected_text[:1021] + "..."
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding(ordinal, check_id, passed, observed_text, expected_text, detail, evidence, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding(ordinal, check_id, passed, provisional.observed, provisional.expected, detail, evidence, address_finding(provisional))


def audit_diff(value: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff, left: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry | None = None, right: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry | None = None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit:
    value = diff_model.verify_diff(value)
    left_match = left is None or registry_model.verify_registry(left).content_address == value.left_registry_address
    right_match = right is None or registry_model.verify_registry(right).content_address == value.right_registry_address
    item_order = tuple(item.ordinal for item in value.items) == tuple(range(1, len(value.items) + 1))
    added_shape = all(item.change_type != "added" or (item.right_address and not item.left_address and not item.changed_fields) for item in value.items)
    removed_shape = all(item.change_type != "removed" or (item.left_address and not item.right_address and not item.changed_fields) for item in value.items)
    changed_shape = all(item.change_type != "changed" or (item.left_address and item.right_address and item.changed_fields) for item in value.items)
    items_by_id = {(item.change_type, item.archive_id, item.entry_id) for item in value.items}
    checks = (
        _finding(1, "diff-address", diff_model.address_diff(value) == value.content_address, value.content_address, diff_model.address_diff(value), "diff address reproduces", value.content_address),
        _finding(2, "side-links", left_match and right_match, (value.left_registry_address, value.right_registry_address), "matching registry addresses", "diff sides link to declared registries", value.content_address),
        _finding(3, "item-order", item_order, tuple(item.ordinal for item in value.items), "contiguous ordinals", "diff item order is deterministic", value.content_address),
        _finding(4, "change-counts", sum(item.change_type == "added" for item in value.items) == value.added_count and sum(item.change_type == "removed" for item in value.items) == value.removed_count and sum(item.change_type == "changed" for item in value.items) == value.changed_count, (value.added_count, value.removed_count, value.changed_count), "item type totals", "change counters are conserved", value.content_address),
        _finding(5, "added-shape", added_shape, added_shape, True, "added items carry only right-side evidence", value.content_address),
        _finding(6, "removed-shape", removed_shape, removed_shape, True, "removed items carry only left-side evidence", value.content_address),
        _finding(7, "changed-shape", changed_shape, changed_shape, True, "changed items carry both sides", value.content_address),
        _finding(8, "changed-fields", all(item.change_type != "changed" or len(item.changed_fields) == len(set(item.changed_fields)) for item in value.items), True, True, "changed field lists are unique", value.content_address),
        _finding(9, "entry-identity", len(items_by_id) == len(value.items), len(items_by_id), len(value.items), "each archive identity has one change row", value.content_address),
        _finding(10, "public-boundary", _public(value.to_dict()), True, True, "diff output is public", value.content_address),
        _finding(11, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).to_dict() == value.to_dict(), True, True, "diff mapping reloads exactly", value.content_address),
        _finding(12, "bounded-diff", len(value.items) <= diff_model.MAX_ITEMS, len(value.items), diff_model.MAX_ITEMS, "diff remains bounded", value.content_address),
        _finding(13, "side-replay", left_match and right_match, (left_match, right_match), (True, True), "supplied registry sides replay when provided", value.content_address),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit(provisional.diff_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("diff audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    fields = ("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow({field: item.to_dict()[field] for field in fields})
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Archive Registry Diff Audit", "", f"- Diff: `{value.diff_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit.FIELDS), "properties": {"diff_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS), "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent diff verification", "change-shape checks", "side-link verification", "changed-field checks", "addressable findings", "path-free JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "FINDING_PREFIX",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAudit",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffAuditFinding",
    "VERSION",
    "address_audit",
    "address_finding",
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
