"""Independent assurance for runtime registry federations."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-audit-v1"
BOUNDARY = federation_model.BOUNDARY + "_audit"
AUDIT_PREFIX = federation_model.FEDERATION_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
MAX_CHECKS = 18
CHECK_IDS = ("version", "boundary", "federation-address", "member-count", "member-order", "member-addresses", "member-identity", "member-state-replay", "runtime-count", "runtime-order", "runtime-addresses", "runtime-identity", "source-linkage", "summary-linkage", "manifest-linkage", "state-acceptance", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("federation_address", "federation_id", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum or not value.strip() or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValidationError(f"{field} must be a string-keyed object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("path", "payload", "agent", "language")) or not _public(item):
                return False
    elif isinstance(value, (tuple, list)):
        return all(_public(item) for item in value)
    return not isinstance(value, (bytes, bytearray))


class RecoveryExecutionRuntimeRegistryFederationAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry federation audit check ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "runtime registry federation audit check ID")
        self.passed = _bool(passed, "runtime registry federation audit check result")
        self.detail = _text(detail, "runtime registry federation audit check detail", 1024)
        self.evidence_addresses = tuple(_address(item, "runtime registry federation audit evidence address") for item in _sequence(evidence_addresses, "runtime registry federation audit evidence", 16))
        self.content_address = _address(content_address, "runtime registry federation audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or not _public(self.to_dict()):
            raise ValidationError("runtime registry federation audit check is invalid")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("runtime registry federation audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationAuditCheck":
        value = _mapping(value, "runtime registry federation audit check")
        _strict(value, set(cls.FIELDS), "runtime registry federation audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RecoveryExecutionRuntimeRegistryFederationAuditCheck) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationAuditCheck):
        raise ValidationError("runtime registry federation audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RecoveryExecutionRuntimeRegistryFederationAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, federation_address: str, federation_id: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[RecoveryExecutionRuntimeRegistryFederationAuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.federation_address = _address(federation_address, "runtime registry federation audit federation address", federation_model.FEDERATION_PREFIX)
        self.federation_id = _label(federation_id, "runtime registry federation audit federation ID")
        self.version = _text(version, "runtime registry federation audit version", 1024)
        self.boundary = _text(boundary, "runtime registry federation audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, RecoveryExecutionRuntimeRegistryFederationAuditCheck) else RecoveryExecutionRuntimeRegistryFederationAuditCheck.from_mapping(item) for item in _sequence(checks, "runtime registry federation audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "runtime registry federation audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry federation audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry federation audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry federation audit acceptance")
        self.content_address = _address(content_address, "runtime registry federation audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        expected_passed = sum(item.passed for item in self.checks)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("runtime registry federation audit version or boundary is not current")
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count != expected_passed or self.failed_count != self.check_count - expected_passed:
            raise ValidationError("runtime registry federation audit counts do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime registry federation audit checks are not ordered")
        if self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("runtime registry federation audit acceptance or public boundary is invalid")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime registry federation audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationAudit":
        value = _mapping(value, "runtime registry federation audit")
        _strict(value, set(cls.FIELDS), "runtime registry federation audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: RecoveryExecutionRuntimeRegistryFederationAudit) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationAudit):
        raise ValidationError("runtime registry federation audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def audit_federation(value: federation_model.RecoveryExecutionRuntimeRegistryFederation) -> RecoveryExecutionRuntimeRegistryFederationAudit:
    if not isinstance(value, federation_model.RecoveryExecutionRuntimeRegistryFederation):
        raise ValidationError("runtime registry federation audit requires a typed federation")
    checks: list[RecoveryExecutionRuntimeRegistryFederationAuditCheck] = []

    def add(check_id: str, passed: bool, detail: str, evidence: Sequence[str] = ()) -> None:
        provisional = RecoveryExecutionRuntimeRegistryFederationAuditCheck(len(checks) + 1, check_id, bool(passed), detail, tuple(evidence)[:16], CHECK_PREFIX + ":pending")
        checks.append(RecoveryExecutionRuntimeRegistryFederationAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional)))

    add("version", value.version == federation_model.VERSION, "federation version matches the current contract", (value.content_address,))
    add("boundary", value.boundary == federation_model.BOUNDARY, "federation boundary matches the current contract", (value.content_address,))
    add("federation-address", federation_model.address_federation(value) == value.content_address, "federation address replays from its public projection", (value.content_address,))
    add("member-count", value.member_count == len(value.members) == value.summary.member_count, "member count is conserved across federation and summary", (value.summary.content_address,))
    add("member-order", tuple(item.ordinal for item in value.members) == tuple(range(1, value.member_count + 1)), "member ordinals are contiguous and deterministic", tuple(item.content_address for item in value.members))
    add("member-addresses", federation_model.address_members(value.members) == value.manifest.artifact_addresses[0], "member collection address replays", (value.manifest.content_address,))
    add("member-identity", len({(item.registry_id, item.registry_address) for item in value.members}) == value.member_count, "source registry identities are unique", tuple(item.registry_address for item in value.members))
    add("member-state-replay", all(item.state == ("empty" if item.entry_count == 0 else "blocked" if item.blocked_count else "ready") and item.accepted == (item.blocked_count == 0) for item in value.members), "member state and acceptance replay from member counts", tuple(item.content_address for item in value.members))
    add("runtime-count", value.runtime_entry_count == len(value.entries) == value.summary.runtime_entry_count and value.accepted_runtime_entry_count == sum(item.accepted for item in value.entries) and value.ready_runtime_entry_count == sum(item.state == "ready" for item in value.entries) and value.blocked_runtime_entry_count == sum(item.state == "blocked" for item in value.entries), "flattened runtime counts are conserved", (value.summary.content_address,))
    add("runtime-order", tuple(item.ordinal for item in value.entries) == tuple(range(1, value.runtime_entry_count + 1)), "runtime entry ordinals are contiguous and deterministic", tuple(item.content_address for item in value.entries))
    add("runtime-addresses", federation_model.address_entries(value.entries) == value.manifest.artifact_addresses[1], "runtime entry collection address replays", (value.manifest.content_address,))
    add("runtime-identity", len({(item.registry_id, item.registry_address, item.runtime_id, item.runtime_address) for item in value.entries}) == value.runtime_entry_count, "source-scoped runtime identities are unique", tuple(item.runtime_address for item in value.entries))
    add("source-linkage", all(1 <= item.member_ordinal <= value.member_count and (item.registry_id, item.registry_address) == (value.members[item.member_ordinal - 1].registry_id, value.members[item.member_ordinal - 1].registry_address) for item in value.entries), "every runtime entry links to its admitted member", tuple(item.content_address for item in value.entries))
    expected_summary = {field: getattr(value, field) for field in federation_model.SUMMARY_FIELDS if field != "content_address"} | {"content_address": value.summary.content_address}
    add("summary-linkage", value.summary.to_dict() == expected_summary and federation_model.address_summary(value.summary) == value.summary.content_address, "summary projection and address replay", (value.summary.content_address,))
    add("manifest-linkage", value.manifest.federation_id == value.federation_id and value.manifest.version == value.version and value.manifest.boundary == value.boundary and value.manifest.files == federation_model.FILES and tuple(value.manifest.artifact_addresses) == (federation_model.address_members(value.members), federation_model.address_entries(value.entries), value.summary.content_address) and federation_model.address_manifest(value.manifest) == value.manifest.content_address, "manifest links the exact federation artifacts", (value.manifest.content_address,))
    expected_state = federation_model.STATES[0] if value.member_count == 0 else "blocked" if value.blocked_member_count else "ready" if value.ready_member_count == value.member_count else "mixed"
    add("state-acceptance", value.state == expected_state and value.accepted == (value.blocked_member_count == 0), "federation state and acceptance fold member states", (value.content_address,))
    add("public-boundary", _public(value.to_dict()), "federation projection contains only public bounded fields", (value.content_address,))
    try:
        round_trip = federation_model.federation_from_mapping(json.loads(federation_model.federation_json(value))).content_address == value.content_address
    except (TypeError, ValueError, ValidationError):
        round_trip = False
    add("mapping-round-trip", round_trip, "canonical federation mapping preserves its address", (value.content_address,))
    checks = tuple(checks)
    provisional = RecoveryExecutionRuntimeRegistryFederationAudit(value.content_address, value.federation_id, VERSION, BOUNDARY, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), checks, AUDIT_PREFIX + ":pending")
    return RecoveryExecutionRuntimeRegistryFederationAudit(provisional.federation_address, provisional.federation_id, provisional.version, provisional.boundary, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, provisional.checks, address_audit(provisional))


def verify_audit(value: RecoveryExecutionRuntimeRegistryFederationAudit) -> RecoveryExecutionRuntimeRegistryFederationAudit:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationAudit):
        raise ValidationError("runtime registry federation audit verification requires a typed audit")
    return RecoveryExecutionRuntimeRegistryFederationAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryFederationAudit:
    return RecoveryExecutionRuntimeRegistryFederationAudit.from_mapping(value)


def audit_json(value: RecoveryExecutionRuntimeRegistryFederationAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RecoveryExecutionRuntimeRegistryFederationAudit) -> str:
    value = verify_audit(value)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "check_id", "passed", "detail", "evidence_count", "content_address"))
    for item in value.checks:
        writer.writerow((item.ordinal, item.check_id, item.passed, item.detail, len(item.evidence_addresses), item.content_address))
    return output.getvalue()


def render_audit_markdown(value: RecoveryExecutionRuntimeRegistryFederationAudit) -> str:
    value = verify_audit(value)
    lines = ["# Recovery Execution Runtime Registry Federation Audit", "", f"- Federation: `{value.federation_id}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| ordinal | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryFederationAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "maxItems": 16, "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryFederationAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"federation_address": {"type": "string"}, "federation_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_count": MAX_CHECKS, "check_ids": list(CHECK_IDS), "operations": ["audit_federation", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"], "privacy": {"values": False, "source_paths": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "MAX_CHECKS", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "RecoveryExecutionRuntimeRegistryFederationAuditCheck", "RecoveryExecutionRuntimeRegistryFederationAudit", "address_check", "address_audit", "audit_federation", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
