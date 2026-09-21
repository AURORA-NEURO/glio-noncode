"""Independent replay audit for D490 runtime registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime as runtime_model
from . import downloaded_data_quality_d490_ledger_diff_runtime_registry as registry_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = registry_model.VERSION + "-audit-v1"
BOUNDARY = registry_model.BOUNDARY + "_audit"
AUDIT_PREFIX = registry_model.REGISTRY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("typed_registry", "registry_identity", "entry_sequence", "check_sequence", "counter_replay", "summary_replay", "manifest_replay", "policy_replay", "unique_runtime_ids", "unique_runtime_addresses", "runtime_links", "audit_requirement", "lineage_replay", "entry_addresses", "public_boundary", "canonical_registry")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("registry_id", "audit_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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
    if isinstance(value, (str, bytes)) or not hasattr(value, "__len__") or not hasattr(value, "__iter__") or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return registry_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger diff runtime registry audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "ledger diff runtime registry audit check ID")
        self.passed = _bool(passed, "ledger diff runtime registry audit result")
        self.actual = _text(actual, "ledger diff runtime registry audit actual", 32768)
        self.expected = _text(expected, "ledger diff runtime registry audit expected", 32768)
        self.detail = _text(detail, "ledger diff runtime registry audit detail", 4096)
        self.content_address = _address(content_address, "ledger diff runtime registry audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("ledger diff runtime registry audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime registry audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "ledger diff runtime registry audit check")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("ledger diff runtime registry audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class RegistryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, registry_id: str, audit_address: str, checks: Any, check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.registry_id = _label(registry_id, "ledger diff runtime registry audit registry ID")
        self.audit_address = _address(audit_address, "ledger diff runtime registry audit address", registry_model.REGISTRY_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "ledger diff runtime registry audit check")) for item in _sequence(checks, "ledger diff runtime registry audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "ledger diff runtime registry audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "ledger diff runtime registry audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "ledger diff runtime registry audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "ledger diff runtime registry audit acceptance")
        self.content_address = _address(content_address, "ledger diff runtime registry audit content address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("ledger diff runtime registry audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("ledger diff runtime registry audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime registry audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "audit_address": self.audit_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryAudit":
        value = _mapping(value, "ledger diff runtime registry audit")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: RegistryAudit) -> str:
    if not isinstance(value, RegistryAudit):
        raise ValidationError("ledger diff runtime registry audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_registry(value: registry_model.RuntimeRegistry, runtimes: Sequence[runtime_model.LedgerDiffRuntime] | None = None) -> RegistryAudit:
    registry_model.verify_registry(value)
    supplied = None if runtimes is None else tuple(runtimes)
    if supplied is not None:
        if len(supplied) != value.entry_count:
            raise ValidationError("ledger diff runtime registry audit inputs do not match entry count")
        for item in supplied:
            runtime_model.verify_runtime(item)
    identity = supplied is None or tuple((item.runtime_id, item.content_address) for item in supplied) == tuple((entry.runtime_id, entry.runtime_address) for entry in value.entries)
    links = supplied is None or all(item.diff_id == entry.diff_id and item.diff_address == entry.diff_address and item.policy.content_address == entry.policy_address for item, entry in zip(supplied, value.entries, strict=True))
    lineage = supplied is None or all(item.direction == entry.direction and item.state == entry.state and item.release_ready == entry.release_ready and item.accepted == entry.accepted and item.item_count == entry.item_count for item, entry in zip(supplied, value.entries, strict=True))
    checks = (
        _finding(1, "typed_registry", isinstance(value, registry_model.RuntimeRegistry), type(value).__name__, "RuntimeRegistry", "the audited value must use the typed registry model"),
        _finding(2, "registry_identity", identity, value.registry_id, "supplied runtime identity sequence", "registry entries must retain runtime identity and address"),
        _finding(3, "entry_sequence", tuple(item.ordinal for item in value.entries) == tuple(range(1, value.entry_count + 1)), [item.ordinal for item in value.entries], "contiguous entry ordinals", "entries must preserve canonical order"),
        _finding(4, "check_sequence", tuple(item.ordinal for item in value.checks) == tuple(range(1, registry_model.MAX_CHECKS + 1)) and tuple(item.check_id for item in value.checks) == registry_model.CHECK_IDS, [item.check_id for item in value.checks], registry_model.CHECK_IDS, "registry checks must be complete and ordered"),
        _finding(5, "counter_replay", (value.entry_count, value.ready_count, value.blocked_count, value.audited_count, value.accepted_count) == (len(value.entries), sum(item.state == "ready" for item in value.entries), sum(item.state == "blocked" for item in value.entries), sum(bool(item.audit_address) for item in value.entries), sum(item.accepted for item in value.entries)), value.to_dict(), "replayed registry counters", "aggregate counters must derive from entries"),
        _finding(6, "summary_replay", value.summary.content_address == registry_model.address_summary(value.summary), value.summary.content_address, registry_model.address_summary(value.summary), "summary address must replay"),
        _finding(7, "manifest_replay", value.manifest.content_address == registry_model.address_manifest(value.manifest) and value.manifest.artifact_addresses == (value.policy.content_address, registry_model.address_entries(value.entries), registry_model.address_checks(value.checks), value.summary.content_address), value.manifest.to_dict(), "replayed manifest components", "manifest must retain artifact addresses"),
        _finding(8, "policy_replay", value.policy.content_address == registry_model.address_policy(value.policy), value.policy.content_address, registry_model.address_policy(value.policy), "policy address must replay"),
        _finding(9, "unique_runtime_ids", len({item.runtime_id for item in value.entries}) == value.entry_count, [item.runtime_id for item in value.entries], "unique runtime IDs", "runtime identities must remain unique"),
        _finding(10, "unique_runtime_addresses", len({item.runtime_address for item in value.entries}) == value.entry_count, [item.runtime_address for item in value.entries], "unique runtime addresses", "runtime addresses must remain unique"),
        _finding(11, "runtime_links", links, True, "linked runtime lineage", "supplied runtimes must match retained diff and policy links"),
        _finding(12, "audit_requirement", (not value.policy.require_audited) or value.audited_count == value.entry_count, value.audited_count, value.entry_count, "required audit evidence must be linked"),
        _finding(13, "lineage_replay", lineage, True, "replayed runtime dispositions", "supplied runtimes must match retained state and readiness"),
        _finding(14, "entry_addresses", all(registry_model.address_entry(item) == item.content_address for item in value.entries), True, "replayed entry addresses", "entry addresses must replay"),
        _finding(15, "public_boundary", _public(value.to_dict()), True, "public value", "registry artifacts must contain no private records"),
        _finding(16, "canonical_registry", canonical_json(value.to_dict()) == canonical_json(registry_model.registry_from_mapping(_strict_json_loads(registry_model.registry_json(value))).to_dict()), True, "canonical round-trip", "registry serialization must be deterministic"),
    )
    provisional = RegistryAudit(value.registry_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), f"pending:{AUDIT_PREFIX}")
    return _seal(provisional, address_audit)


def verify_audit(value: RegistryAudit) -> RegistryAudit:
    if not isinstance(value, RegistryAudit):
        raise ValidationError("ledger diff runtime registry audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryAudit:
    return RegistryAudit.from_mapping(value)


def audit_json(value: RegistryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: RegistryAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Ledger diff runtime registry audit {value.registry_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent D490 registry replay", "runtime lineage and evidence verification", "canonical address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "RegistryAudit", "address_check", "address_audit", "audit_registry", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
