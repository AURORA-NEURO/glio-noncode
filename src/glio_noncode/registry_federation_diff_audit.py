"""Independent audit of federation transition diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_diff as diff_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = diff_model.DIFF_PREFIX + "-audit-check"
MAX_CHECKS = 24
CHECK_IDS = ("exact-fields", "public-boundary", "input-addresses", "item-conservation", "category-conservation", "change-conservation", "field-conservation", "item-addresses", "state-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field)
    if not value.startswith(prefix + ":"):
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


def _labels(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(values))


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_text(item, field) for item in _sequence(value, field, maximum))
    if len(set(values)) != len(values) or any("/" in value or "\\" in value for value in values):
        raise ValidationError(f"{field} must be unique and path-free")
    return tuple(sorted(values))


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationDiffAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("diff audit check ID is unsupported")
        self.passed = _bool(passed, "diff audit check result")
        self.detail = _text(detail, "diff audit check detail")
        self.evidence_addresses = _addresses(evidence_addresses, "diff audit evidence", 16)
        self.content_address = _address(content_address, "diff audit check address", CHECK_PREFIX)
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("diff audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationDiffAuditCheck:
        value = _mapping(value, "diff audit check")
        _strict(value, set(cls.FIELDS), "diff audit check")
        addresses = tuple(value["evidence_addresses"]) if isinstance(value["evidence_addresses"], list) else value["evidence_addresses"]
        return cls(value["ordinal"], value["check_id"], value["passed"], value["detail"], addresses, value["content_address"])


def address_check(value: RegistryFederationDiffAuditCheck) -> str:
    if not isinstance(value, RegistryFederationDiffAuditCheck):
        raise ValidationError("diff audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationDiffAudit:
    FIELDS = ("diff_id", "diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, diff_id: str, diff_address: str, checks: Sequence[RegistryFederationDiffAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "diff audit ID")
        self.diff_address = _address(diff_address, "diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(checks)
        self.check_count = _count(check_count, "diff audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "diff audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "diff audit failed count", self.check_count)
        self.accepted = _bool(accepted, "diff audit acceptance")
        self.content_address = _address(content_address, "diff audit address", AUDIT_PREFIX)
        if len(self.checks) != self.check_count or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks) or self.failed_count != sum(not check.passed for check in self.checks):
            raise ValidationError("diff audit counters are not conserved")
        if tuple(check.ordinal for check in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(check.check_id for check in self.checks) != CHECK_IDS:
            raise ValidationError("diff audit checks are not canonical")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("diff audit acceptance is not conserved")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("diff audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "diff_address": self.diff_address, "checks": tuple(check.to_dict() for check in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationDiffAudit:
        value = _mapping(value, "diff audit")
        _strict(value, set(cls.FIELDS), "diff audit")
        checks = tuple(value["checks"]) if isinstance(value["checks"], list) else value["checks"]
        return cls(value["diff_id"], value["diff_address"], tuple(RegistryFederationDiffAuditCheck.from_mapping(item) for item in checks), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationDiffAudit) -> str:
    if not isinstance(value, RegistryFederationDiffAudit):
        raise ValidationError("diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationDiffAuditCheck:
    provisional = RegistryFederationDiffAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationDiffAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def _audit_checks(value: diff_model.RegistryFederationDiff) -> tuple[RegistryFederationDiffAuditCheck, ...]:
    items = value.items
    evidence = (value.left_federation_address, value.right_federation_address)
    categories = {category: sum(item.category == category for item in items) for category in ("peer", "package", "conflict", "action")}
    checks = [
        _check(1, "exact-fields", set(value.to_dict()) == set(diff_model.RegistryFederationDiff.FIELDS), "diff exposes the exact public field set", evidence),
        _check(2, "public-boundary", _public(value.to_dict()), "diff projection is public and path-free", evidence),
        _check(3, "input-addresses", value.left_federation_address != value.right_federation_address or value.left_state == value.right_state, "left and right federation receipts are address-linked", evidence),
        _check(4, "item-conservation", value.item_count == len(items) and value.item_count <= diff_model.MAX_ITEMS, "item count agrees with the transition rows", evidence),
        _check(5, "category-conservation", value.changed_package_count == categories["package"] and value.changed_conflict_count == categories["conflict"] and value.changed_action_count == categories["action"], "category counters agree with transition rows", evidence),
        _check(6, "change-conservation", value.added_peer_count == sum(item.category == "peer" and item.change == "added" for item in items) and value.removed_peer_count == sum(item.category == "peer" and item.change == "removed" for item in items) and value.changed_peer_count == sum(item.category == "peer" and item.change == "changed" for item in items), "peer change counters agree with transition rows", evidence),
        _check(7, "field-conservation", all(item.change != "changed" or item.changed_fields for item in items), "changed rows identify changed fields", tuple(item.content_address for item in items) or evidence),
        _check(8, "item-addresses", all(diff_model.address_item(item) == item.content_address for item in items), "every transition row address replays", tuple(item.content_address for item in items) or evidence),
        _check(9, "state-conservation", value.left_state in federation_model.STATES and value.right_state in federation_model.STATES and value.left_decision in federation_model.DECISIONS and value.right_decision in federation_model.DECISIONS, "left and right dispositions are supported", evidence),
        _check(10, "content-address", diff_model.address_diff(value) == value.content_address, "diff content address replays", evidence),
        _check(11, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).content_address == value.content_address, "typed diff survives a mapping round trip", evidence),
        _check(12, "path-free", _public(value.to_dict()), "diff contains no filesystem paths or private execution text", evidence),
    ]
    return tuple(checks)


def audit_diff(value: diff_model.RegistryFederationDiff) -> RegistryFederationDiffAudit:
    value = diff_model.verify_diff(value)
    checks = _audit_checks(value)
    provisional = RegistryFederationDiffAudit(value.diff_id, value.content_address, checks, len(checks), sum(check.passed for check in checks), sum(not check.passed for check in checks), all(check.passed for check in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationDiffAudit(provisional.diff_id, provisional.diff_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationDiffAudit:
    return verify_audit(RegistryFederationDiffAudit.from_mapping(value))


def verify_audit(value: RegistryFederationDiffAudit) -> RegistryFederationDiffAudit:
    if not isinstance(value, RegistryFederationDiffAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("diff audit is not valid")
    return value


def audit_json(value: RegistryFederationDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationDiffAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address"), lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        row = check.to_dict()
        row["evidence_addresses"] = "|".join(check.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# Package Registry Federation Diff Audit", "", f"- Diff: `{value.diff_id}`", f"- Checks: `{value.passed_count}/{value.check_count}` passed", f"- Accepted: `{value.accepted}`", f"- Audit address: `{value.content_address}`", "", "| ordinal | check | result | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {check.ordinal} | `{check.check_id}` | `{check.passed}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationDiffAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationDiffAudit.FIELDS), "properties": {"diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 1}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "features": ("independent category conservation", "peer change conservation", "transition field validation", "item address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "RegistryFederationDiffAudit", "RegistryFederationDiffAuditCheck", "address_audit", "address_check", "audit_csv", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
