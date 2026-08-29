"""Independent audit for consensus release-gate transition diffs."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from . import registry_federation_consensus_gate_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
FINDING_PREFIX = diff_model.DIFF_PREFIX + "-audit-finding"
CHECK_IDS = ("exact-fields", "public-boundary", "left-right-gates", "item-conservation", "counter-conservation", "resource-vocabulary", "change-vocabulary", "value-conservation", "item-addresses", "disposition-conservation", "mapping-round-trip", "content-address", "path-free")


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
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateDiffAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate diff audit finding ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "gate diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("gate diff audit check ID is unsupported")
        self.passed = _bool(passed, "gate diff audit finding result")
        self.observed = _text(observed, "gate diff audit observed value")
        self.expected = _text(expected, "gate diff audit expected value")
        self.detail = _text(detail, "gate diff audit detail", required=True)
        self.content_address = _address(content_address, "gate diff audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("gate diff audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate diff audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateDiffAuditFinding:
        value = _mapping(value, "gate diff audit finding")
        _strict(value, set(cls.FIELDS), "gate diff audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateDiffAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateDiffAuditFinding):
        raise ValidationError("gate diff audit finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateDiffAudit:
    FIELDS = ("diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, diff_address: str, checks: Sequence[RegistryFederationConsensusGateDiffAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_address = _address(diff_address, "audited gate diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateDiffAuditFinding) for item in self.checks):
            raise ValidationError("gate diff audit checks must be typed")
        self.check_count = _count(check_count, "gate diff audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "gate diff audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "gate diff audit failed count", self.check_count)
        self.accepted = _bool(accepted, "gate diff audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("gate diff audit counters are not conserved")
        self.content_address = _address(content_address, "gate diff audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("gate diff audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate diff audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateDiffAudit:
        value = _mapping(value, "consensus gate diff audit")
        _strict(value, set(cls.FIELDS), "consensus gate diff audit")
        return cls(value["diff_address"], tuple(RegistryFederationConsensusGateDiffAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateDiffAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateDiffAudit):
        raise ValidationError("gate diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateDiffAuditFinding:
    provisional = RegistryFederationConsensusGateDiffAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateDiffAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_diff(value: diff_model.RegistryFederationConsensusGateDiff) -> RegistryFederationConsensusGateDiffAudit:
    value = diff_model.verify_diff(value)
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(diff_model.RegistryFederationConsensusGateDiff.FIELDS), tuple(sorted(value.to_dict())), diff_model.RegistryFederationConsensusGateDiff.FIELDS, "diff fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "diff is public and path-free"),
        _finding(3, "left-right-gates", isinstance(value.left, gate_model.RegistryFederationConsensusGate) and isinstance(value.right, gate_model.RegistryFederationConsensusGate), "typed left and right gates", "two typed gates", "both endpoints are retained"),
        _finding(4, "item-conservation", len(value.items) == value.item_count and tuple(item.ordinal for item in value.items) == tuple(range(1, value.item_count + 1)), (len(value.items), value.item_count), "ordered item count", "diff items are contiguous"),
        _finding(5, "counter-conservation", value.added_count + value.removed_count + value.changed_count == value.item_count and value.added_count == sum(item.change == "added" for item in value.items) and value.removed_count == sum(item.change == "removed" for item in value.items) and value.changed_count == sum(item.change == "changed" for item in value.items), (value.added_count, value.removed_count, value.changed_count), value.item_count, "change counters replay"),
        _finding(6, "resource-vocabulary", all(item.resource in diff_model.RESOURCES for item in value.items), tuple(sorted({item.resource for item in value.items})), diff_model.RESOURCES, "diff resources use the fixed vocabulary"),
        _finding(7, "change-vocabulary", all(item.change in diff_model.CHANGES for item in value.items), tuple(sorted({item.change for item in value.items})), diff_model.CHANGES, "diff changes use the fixed vocabulary"),
        _finding(8, "value-conservation", all((item.change != "added" or (not item.left_value and item.right_value)) and (item.change != "removed" or (item.left_value and not item.right_value)) and (item.change != "changed" or (item.left_value and item.right_value and item.left_value != item.right_value)) for item in value.items), "value semantics", "added removed and changed rules", "item values conserve change semantics"),
        _finding(9, "item-addresses", all(diff_model.address_item(item) == item.content_address for item in value.items), "replayed item addresses", "stored item addresses", "every diff item address replays"),
        _finding(10, "disposition-conservation", (value.left_state, value.left_decision, value.left_accepted) == (value.left.state, value.left.decision, value.left.accepted) and (value.right_state, value.right_decision, value.right_accepted) == (value.right.state, value.right.decision, value.right.accepted), "left and right dispositions", "nested gate dispositions", "endpoint dispositions are conserved"),
        _finding(11, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original diff", "mapping conversion is lossless"),
        _finding(12, "content-address", diff_model.address_diff(value) == value.content_address, value.content_address, diff_model.address_diff(value), "diff content address replays"),
        _finding(13, "path-free", _public(value.to_dict()), True, True, "diff contains no local paths or private execution text"),
    )
    provisional = RegistryFederationConsensusGateDiffAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateDiffAudit(provisional.diff_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateDiffAudit:
    return verify_audit(RegistryFederationConsensusGateDiffAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateDiffAudit) -> RegistryFederationConsensusGateDiffAudit:
    if not isinstance(value, RegistryFederationConsensusGateDiffAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("consensus gate diff audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateDiffAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateDiffAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for finding in value.checks:
        writer.writerow(finding.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Release Gate Diff Audit", "", f"- Diff: `{value.diff_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |", *[f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks]]
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateDiffAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateDiffAudit.FIELDS), "properties": {"diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent diff structure checks", "change-counter conservation", "endpoint disposition verification", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateDiffAudit", "RegistryFederationConsensusGateDiffAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
