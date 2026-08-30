"""Independent audit for certificate-observatory transition diffs."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory as observatory_model
from . import registry_federation_consensus_gate_certificate_observatory_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
FINDING_PREFIX = diff_model.DIFF_PREFIX + "-audit-finding"
CHECK_IDS = ("exact-fields", "public-boundary", "item-conservation", "ordinal-conservation", "action-conservation", "observation-counts", "accepted-counts", "withheld-counts", "failure-counts", "delta-conservation", "address-vocabulary", "key-vocabulary", "direction-conservation", "mapping-round-trip", "content-address", "path-free")


def _text(value: Any, field: str, maximum: int = diff_model.MAX_TEXT, *, required: bool = False) -> str:
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


class RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observatory diff audit finding ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "observatory diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("observatory diff audit check ID is unsupported")
        self.passed, self.observed, self.expected, self.detail = _bool(passed, "observatory diff audit result"), _text(observed, "observatory diff audit observed"), _text(expected, "observatory diff audit expected"), _text(detail, "observatory diff audit detail", required=True)
        self.content_address = _address(content_address, "observatory diff audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("observatory diff audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding:
        value = _mapping(value, "observatory diff audit finding")
        _strict(value, set(cls.FIELDS), "observatory diff audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryDiffAudit:
    FIELDS = ("diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, diff_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_address = _address(diff_address, "audited observatory diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding) for item in self.checks):
            raise ValidationError("observatory diff audit checks must be typed")
        self.check_count, self.passed_count, self.failed_count = _count(check_count, "observatory diff audit check count", len(CHECK_IDS), positive=True), _count(passed_count, "observatory diff audit passed count", check_count), _count(failed_count, "observatory diff audit failed count", check_count)
        self.accepted = _bool(accepted, "observatory diff audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("observatory diff audit counters are not conserved")
        self.content_address = _address(content_address, "observatory diff audit address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("observatory diff audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryDiffAudit:
        value = _mapping(value, "observatory diff audit")
        _strict(value, set(cls.FIELDS), "observatory diff audit")
        return cls(value["diff_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryDiffAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_diff(value: diff_model.RegistryFederationConsensusGateCertificateObservatoryDiff) -> RegistryFederationConsensusGateCertificateObservatoryDiffAudit:
    value = diff_model.verify_diff(value)
    items = value.items
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(diff_model.RegistryFederationConsensusGateCertificateObservatoryDiff.FIELDS), tuple(sorted(value.to_dict())), diff_model.RegistryFederationConsensusGateCertificateObservatoryDiff.FIELDS, "diff fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "diff is public and path-free"),
        _finding(3, "item-conservation", len(items) == value.item_count, (len(items), value.item_count), "item count", "items match count"),
        _finding(4, "ordinal-conservation", tuple(item.ordinal for item in items) == tuple(range(1, value.item_count + 1)), tuple(item.ordinal for item in items), tuple(range(1, value.item_count + 1)), "item ordinals are contiguous"),
        _finding(5, "action-conservation", value.added_count == sum(item.action == "added" for item in items) and value.removed_count == sum(item.action == "removed" for item in items) and value.changed_count == sum(item.action == "changed" for item in items) and value.unchanged_count == sum(item.action == "unchanged" for item in items), (value.added_count, value.removed_count, value.changed_count, value.unchanged_count), "action counters", "action counters replay"),
        _finding(6, "observation-counts", value.left_observation_count <= observatory_model.MAX_OBSERVATIONS and value.right_observation_count <= observatory_model.MAX_OBSERVATIONS, (value.left_observation_count, value.right_observation_count), observatory_model.MAX_OBSERVATIONS, "observation counts are bounded"),
        _finding(7, "accepted-counts", value.left_accepted_count <= value.left_observation_count and value.right_accepted_count <= value.right_observation_count, (value.left_accepted_count, value.right_accepted_count), "observation counts", "accepted counts are bounded"),
        _finding(8, "withheld-counts", value.left_withheld_count <= value.left_observation_count and value.right_withheld_count <= value.right_observation_count, (value.left_withheld_count, value.right_withheld_count), "observation counts", "withheld counts are bounded"),
        _finding(9, "failure-counts", value.left_failed_count >= 0 and value.right_failed_count >= 0, (value.left_failed_count, value.right_failed_count), "non-negative", "failure totals are bounded"),
        _finding(10, "delta-conservation", value.accepted_delta == value.right_accepted_count - value.left_accepted_count and value.withheld_delta == value.right_withheld_count - value.left_withheld_count and value.failed_delta == value.right_failed_count - value.left_failed_count, (value.accepted_delta, value.withheld_delta, value.failed_delta), "replayed deltas", "metric deltas replay"),
        _finding(11, "address-vocabulary", value.left_address.startswith(diff_model.observatory_model.OBSERVATORY_PREFIX + ":") and value.right_address.startswith(diff_model.observatory_model.OBSERVATORY_PREFIX + ":") and all((not item.left_observation_address or item.left_observation_address.startswith(observatory_model.OBSERVATION_PREFIX + ":")) and (not item.right_observation_address or item.right_observation_address.startswith(observatory_model.OBSERVATION_PREFIX + ":")) for item in items), "observatory and observation addresses", "address prefixes", "address vocabulary is fixed"),
        _finding(12, "key-vocabulary", len({item.observation_key for item in items}) == value.item_count, "unique keys", value.item_count, "logical keys are unique"),
        _finding(13, "direction-conservation", value.direction in diff_model.DIFF_DIRECTIONS and (value.direction == "unchanged" or value.direction in diff_model.DIFF_DIRECTIONS), value.direction, diff_model.DIFF_DIRECTIONS, "direction uses fixed vocabulary"),
        _finding(14, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original diff", "mapping conversion is lossless"),
        _finding(15, "content-address", diff_model.address_diff(value) == value.content_address, value.content_address, diff_model.address_diff(value), "diff address replays"),
        _finding(16, "path-free", _public(value.to_dict()), True, True, "diff has no local paths or attribution metadata"),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryDiffAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryDiffAudit(provisional.diff_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryDiffAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryDiffAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryDiffAudit) -> RegistryFederationConsensusGateCertificateObservatoryDiffAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryDiffAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("observatory diff audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryDiffAudit) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in verify_audit(value).checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Diff Audit", "", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding.FIELDS), "properties": {field: {"type": "integer"} if field == "ordinal" else {"type": "boolean"} if field == "passed" else {"type": "string"} for field in RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding.FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryDiffAudit.FIELDS), "properties": {"diff_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent observatory transition checks", "action and metric conservation", "address vocabulary validation", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryDiffAudit", "RegistryFederationConsensusGateCertificateObservatoryDiffAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
