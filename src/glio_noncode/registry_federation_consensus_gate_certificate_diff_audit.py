"""Independent audit for certificate transition diffs."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_diff as diff_model
from . import registry_federation_consensus_gate_certificate as certificate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "left-link",
    "right-link",
    "field-vocabulary",
    "ordinal-conservation",
    "action-conservation",
    "counter-conservation",
    "direction-conservation",
    "acceptance-conservation",
    "item-addresses",
    "mapping-round-trip",
    "diff-address",
    "path-free",
)
MAX_TEXT = certificate_model.MAX_TEXT


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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


class RegistryFederationConsensusGateCertificateDiffAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate diff audit ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "certificate diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("certificate diff audit check ID is unsupported")
        self.passed = _bool(passed, "certificate diff audit result")
        self.observed = _text(observed, "certificate diff audit observed value")
        self.expected = _text(expected, "certificate diff audit expected value")
        self.detail = _text(detail, "certificate diff audit detail", required=True)
        self.content_address = _address(content_address, "certificate diff finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("certificate diff finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate diff finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateDiffAuditFinding:
        value = _mapping(value, "certificate diff audit finding")
        _strict(value, set(cls.FIELDS), "certificate diff audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateDiffAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateDiffAuditFinding):
        raise ValidationError("certificate diff finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateDiffAudit:
    FIELDS = ("diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, diff_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateDiffAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_address = _address(diff_address, "audited certificate diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateDiffAuditFinding) for item in self.checks):
            raise ValidationError("certificate diff findings must be typed")
        self.check_count = _count(check_count, "certificate diff audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "certificate diff audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "certificate diff audit failed count", self.check_count)
        self.accepted = _bool(accepted, "certificate diff audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("certificate diff audit check ordering is not conserved")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("certificate diff audit counters are not conserved")
        self.content_address = _address(content_address, "certificate diff audit address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("certificate diff audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate diff audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateDiffAudit:
        value = _mapping(value, "consensus gate certificate diff audit")
        _strict(value, set(cls.FIELDS), "consensus gate certificate diff audit")
        return cls(value["diff_address"], tuple(RegistryFederationConsensusGateCertificateDiffAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateDiffAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateDiffAudit):
        raise ValidationError("certificate diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateCertificateDiffAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateDiffAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateDiffAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_diff(value: diff_model.RegistryFederationConsensusGateCertificateDiff) -> RegistryFederationConsensusGateCertificateDiffAudit:
    """Recompute field vocabulary, counters, direction, and item addresses."""

    value = diff_model.verify_diff(value)
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(diff_model.RegistryFederationConsensusGateCertificateDiff.FIELDS), set(value.to_dict()), diff_model.RegistryFederationConsensusGateCertificateDiff.FIELDS, "diff fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "diff is public and path-free"),
        _finding(3, "left-link", value.left_address.startswith(certificate_model.CERTIFICATE_PREFIX + ":"), value.left_address, certificate_model.CERTIFICATE_PREFIX + ":", "left certificate address is valid"),
        _finding(4, "right-link", value.right_address.startswith(certificate_model.CERTIFICATE_PREFIX + ":"), value.right_address, certificate_model.CERTIFICATE_PREFIX + ":", "right certificate address is valid"),
        _finding(5, "field-vocabulary", tuple(item.field for item in value.items) == diff_model.FIELDS, tuple(item.field for item in value.items), diff_model.FIELDS, "diff fields are complete and ordered"),
        _finding(6, "ordinal-conservation", tuple(item.ordinal for item in value.items) == tuple(range(1, value.item_count + 1)), tuple(item.ordinal for item in value.items), tuple(range(1, value.item_count + 1)), "diff ordinals are contiguous"),
        _finding(7, "action-conservation", all(item.action == ("changed" if item.changed else "unchanged") for item in value.items), tuple(item.action for item in value.items), "changed or unchanged", "diff actions follow field values"),
        _finding(8, "counter-conservation", value.changed_count + value.unchanged_count == value.item_count and value.changed_count == sum(item.changed for item in value.items), (value.changed_count, value.unchanged_count), value.item_count, "diff counters replay"),
        _finding(9, "direction-conservation", value.direction in diff_model.DIFF_DIRECTIONS and (value.changed_count > 0 or value.direction == "unchanged"), value.direction, diff_model.DIFF_DIRECTIONS, "diff direction is conserved"),
        _finding(10, "acceptance-conservation", isinstance(value.left_accepted, bool) and isinstance(value.right_accepted, bool), (value.left_accepted, value.right_accepted), "boolean pair", "acceptance flags are explicit"),
        _finding(11, "item-addresses", all(diff_model.address_item(item) == item.content_address for item in value.items), "replayed item addresses", "stored item addresses", "every item address replays"),
        _finding(12, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original diff", "diff mapping is lossless"),
        _finding(13, "diff-address", diff_model.address_diff(value) == value.content_address, value.content_address, diff_model.address_diff(value), "diff content address replays"),
        _finding(14, "path-free", _public(value.to_dict()), True, True, "diff contains no private paths or attribution fields"),
    )
    provisional = RegistryFederationConsensusGateCertificateDiffAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateDiffAudit(provisional.diff_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateDiffAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateDiffAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateDiffAudit) -> RegistryFederationConsensusGateCertificateDiffAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateDiffAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("certificate diff audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateDiffAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateDiffAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Release Certificate Diff Audit", "", f"- Diff: `{value.diff_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | observed | expected |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.observed} | {item.expected} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateDiffAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateDiffAudit.FIELDS), "properties": {"diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent certificate diff checks", "field vocabulary and counter validation", "acceptance-aware transition review", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateDiffAudit", "RegistryFederationConsensusGateCertificateDiffAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
