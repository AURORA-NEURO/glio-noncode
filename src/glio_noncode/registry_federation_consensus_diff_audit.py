"""Independent integrity audit for consensus transition diffs."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_diff as diff_model
from . import registry_federation_consensus as consensus_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = consensus_model.CONSENSUS_PREFIX + "-diff-audit"
CHECK_PREFIX = consensus_model.CONSENSUS_PREFIX + "-diff-audit-check"
MAX_CHECKS = len(diff_model.CHECK_IDS)
CHECK_IDS = ("exact-fields", "public-boundary", "input-addresses", "item-conservation", "category-conservation", "field-conservation", "item-addresses", "state-conservation", "acceptance-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 32768, *, required: bool = False) -> str:
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


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


class RegistryFederationConsensusDiffAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff audit finding ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("diff audit check ID is unsupported")
        self.passed = _bool(passed, "diff audit finding result")
        self.observed = _text(observed, "diff audit observed value")
        self.expected = _text(expected, "diff audit expected value")
        self.detail = _text(detail, "diff audit detail")
        self.content_address = _address(content_address, "diff audit finding content address", CHECK_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("diff audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "passed": self.passed, "observed": self.observed, "expected": self.expected, "detail": self.detail, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusDiffAuditFinding:
        value = _mapping(value, "diff audit finding")
        _strict(value, set(cls.FIELDS), "diff audit finding")
        return cls(value["ordinal"], value["check_id"], value["passed"], value["observed"], value["expected"], value["detail"], value["content_address"])


def address_finding(value: RegistryFederationConsensusDiffAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusDiffAuditFinding):
        raise ValidationError("diff audit finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusDiffAudit:
    FIELDS = ("diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, diff_address: str, checks: Sequence[RegistryFederationConsensusDiffAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_address = _address(diff_address, "audited diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(checks)
        self.check_count = _count(check_count, "diff audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "diff audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "diff audit failed count", self.check_count)
        self.accepted = _bool(accepted, "diff audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("diff audit counters are not conserved")
        self.content_address = _address(content_address, "diff audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("diff audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusDiffAudit:
        value = _mapping(value, "diff audit")
        _strict(value, set(cls.FIELDS), "diff audit")
        return cls(value["diff_address"], tuple(RegistryFederationConsensusDiffAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusDiffAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusDiffAudit):
        raise ValidationError("diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusDiffAuditFinding:
    provisional = RegistryFederationConsensusDiffAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusDiffAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_diff(value: diff_model.RegistryFederationConsensusDiff) -> RegistryFederationConsensusDiffAudit:
    value = diff_model.verify_diff(value)
    checks: list[RegistryFederationConsensusDiffAuditFinding] = []
    checks.append(_finding(1, "exact-fields", set(value.to_dict()) == set(diff_model.RegistryFederationConsensusDiff.FIELDS), tuple(sorted(value.to_dict())), diff_model.RegistryFederationConsensusDiff.FIELDS, "diff fields are exact"))
    checks.append(_finding(2, "public-boundary", _public(value.to_dict()), True, True, "diff contains only path-free public values"))
    checks.append(_finding(3, "input-addresses", value.left_consensus_address != value.right_consensus_address, (value.left_consensus_address, value.right_consensus_address), "distinct addressed inputs", "left and right receipts are distinguishable"))
    checks.append(_finding(4, "item-conservation", value.item_count == len(value.items) and value.item_count > 0, (value.item_count, len(value.items)), "equal positive counts", "item count matches ordered items"))
    category_passed = all(tuple(sum(item.category == category and item.change == change for item in value.items) for change in ("added", "removed", "changed")) == tuple(getattr(value, f"{change}_{category}_count") for change in ("added", "removed", "changed")) for category in ("package", "candidate", "action"))
    checks.append(_finding(5, "category-conservation", category_passed, "category counters", "item category counts", "package, candidate, and action counters replay"))
    fields_passed = all((item.change == "changed" and item.changed_fields) or (item.change != "changed" and not item.changed_fields) for item in value.items)
    checks.append(_finding(6, "field-conservation", fields_passed, tuple(item.changed_fields for item in value.items), "changed items have fields; added or removed items do not", "field-level attribution matches change kind"))
    checks.append(_finding(7, "item-addresses", all(diff_model.address_item(item) == item.content_address for item in value.items), "replayed item addresses", "stored item addresses", "every item address is independently replayable"))
    checks.append(_finding(8, "state-conservation", value.left_state in consensus_model.STATES and value.right_state in consensus_model.STATES and value.left_decision in consensus_model.DECISIONS and value.right_decision in consensus_model.DECISIONS, (value.left_state, value.right_state, value.left_decision, value.right_decision), "known states and decisions", "dispositions are from the consensus vocabulary"))
    checks.append(_finding(9, "acceptance-conservation", isinstance(value.left_accepted, bool) and isinstance(value.right_accepted, bool), (value.left_accepted, value.right_accepted), "boolean acceptance flags", "acceptance flags are typed"))
    checks.append(_finding(10, "content-address", diff_model.address_diff(value) == value.content_address, value.content_address, diff_model.address_diff(value), "diff address replays"))
    checks.append(_finding(11, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original mapping", "mapping conversion is lossless"))
    checks.append(_finding(12, "path-free", _public(value.to_dict()), True, True, "all emitted strings remain path-free"))
    provisional = RegistryFederationConsensusDiffAudit(value.content_address, tuple(checks), len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusDiffAudit(provisional.diff_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusDiffAudit:
    return verify_audit(RegistryFederationConsensusDiffAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusDiffAudit) -> RegistryFederationConsensusDiffAudit:
    if not isinstance(value, RegistryFederationConsensusDiffAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("diff audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusDiffAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusDiffAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for finding in value.checks:
        writer.writerow(finding.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Diff Audit", "", f"- Diff: `{value.diff_address}`", f"- Result: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{finding.check_id}` | `{finding.passed}` | {finding.detail} |" for finding in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusDiffAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusDiffAudit.FIELDS), "properties": {"diff_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "features": ("independent counter recomputation", "field-level transition validation", "content-address replay", "mapping round-trip verification", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "RegistryFederationConsensusDiffAudit", "RegistryFederationConsensusDiffAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_diff", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
