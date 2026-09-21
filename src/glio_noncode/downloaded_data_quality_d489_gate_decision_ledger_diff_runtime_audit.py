"""Independent replay audit for D489 ledger-diff runtimes."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import downloaded_data_quality_d488_gate_decision_ledger_diff as diff_model
from . import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime as runtime_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = runtime_model.VERSION + "-audit-v1"
BOUNDARY = runtime_model.BOUNDARY + "_audit"
AUDIT_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("typed_runtime", "diff_link", "check_sequence", "counter_replay", "policy_replay", "summary_replay", "manifest_replay", "disposition_replay", "direction_link", "transition_link", "comparison_link", "check_addresses", "address_integrity", "public_boundary", "canonical_runtime")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("runtime_id", "diff_id", "runtime_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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
    return diff_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger diff runtime audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "ledger diff runtime audit check ID")
        self.passed = _bool(passed, "ledger diff runtime audit result")
        self.actual = _text(actual, "ledger diff runtime audit actual", 32768)
        self.expected = _text(expected, "ledger diff runtime audit expected", 32768)
        self.detail = _text(detail, "ledger diff runtime audit detail", 4096)
        self.content_address = _address(content_address, "ledger diff runtime audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("ledger diff runtime audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "ledger diff runtime audit check")
        _strict(value, set(cls.FIELDS), "ledger diff runtime audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("ledger diff runtime audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class RuntimeAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, runtime_id: str, diff_id: str, runtime_address: str, checks: Any, check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "ledger diff runtime audit runtime ID")
        self.diff_id = _label(diff_id, "ledger diff runtime audit diff ID")
        self.runtime_address = _address(runtime_address, "ledger diff runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "ledger diff runtime audit check")) for item in _sequence(checks, "ledger diff runtime audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "ledger diff runtime audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "ledger diff runtime audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "ledger diff runtime audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "ledger diff runtime audit acceptance")
        self.content_address = _address(content_address, "ledger diff runtime audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("ledger diff runtime audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("ledger diff runtime audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "diff_id": self.diff_id, "runtime_address": self.runtime_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeAudit":
        value = _mapping(value, "ledger diff runtime audit")
        _strict(value, set(cls.FIELDS), "ledger diff runtime audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: RuntimeAudit) -> str:
    if not isinstance(value, RuntimeAudit):
        raise ValidationError("ledger diff runtime audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_runtime(value: runtime_model.LedgerDiffRuntime, diff: diff_model.LedgerDiff | None = None) -> RuntimeAudit:
    runtime_model.verify_runtime(value, diff)
    checks = (
        _finding(1, "typed_runtime", isinstance(value, runtime_model.LedgerDiffRuntime), type(value).__name__, "LedgerDiffRuntime", "the audited value must use the typed runtime model"),
        _finding(2, "diff_link", diff is None or (value.diff_id == diff.diff_id and value.diff_address == diff.content_address), (value.diff_id, value.diff_address), "supplied diff identity", "runtime must retain its evaluated diff"),
        _finding(3, "check_sequence", tuple(item.check_id for item in value.checks) == runtime_model.CHECK_IDS and tuple(item.ordinal for item in value.checks) == tuple(range(1, runtime_model.MAX_CHECKS + 1)), True, runtime_model.CHECK_IDS, "runtime checks must be complete and ordered"),
        _finding(4, "counter_replay", (value.passed_count, value.failed_count) == (sum(item.passed for item in value.checks), sum(not item.passed for item in value.checks)), (value.passed_count, value.failed_count), "replayed check counters", "check counters must derive from checks"),
        _finding(5, "policy_replay", value.policy.content_address == runtime_model.address_policy(value.policy), value.policy.content_address, runtime_model.address_policy(value.policy), "policy address must replay"),
        _finding(6, "summary_replay", value.summary.content_address == runtime_model.address_summary(value.summary), value.summary.content_address, runtime_model.address_summary(value.summary), "summary address must replay"),
        _finding(7, "manifest_replay", value.manifest.content_address == runtime_model.address_manifest(value.manifest), value.manifest.content_address, runtime_model.address_manifest(value.manifest), "manifest address must replay"),
        _finding(8, "disposition_replay", value.release_ready == (value.state == "ready") and value.release_ready == all(item.passed for item in value.checks) and value.accepted == (diff.accepted if diff is not None else value.accepted), (value.state, value.release_ready, value.accepted), "replayed disposition", "state and acceptance must follow checks and upstream diff"),
        _finding(9, "direction_link", diff is None or value.direction == diff.direction, value.direction, diff.direction if diff is not None else value.direction, "direction must link to the diff"),
        _finding(10, "transition_link", diff is None or value.state_transition == diff.state_transition, value.state_transition, diff.state_transition if diff is not None else value.state_transition, "transition must link to the diff"),
        _finding(11, "comparison_link", diff is None or (value.item_count, value.added_count, value.removed_count, value.changed_count, value.unchanged_count) == (diff.item_count, diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count), value.item_count, diff.item_count if diff is not None else value.item_count, "comparison counts must link to the diff"),
        _finding(12, "check_addresses", all(runtime_model.address_check(item) == item.content_address for item in value.checks) and runtime_model.address_checks(value.checks) == value.manifest.artifact_addresses[0], True, "replayed check addresses", "check addresses must be canonical"),
        _finding(13, "address_integrity", value.summary.diff_address == value.diff_address and value.policy.diff_id == value.diff_id, True, "linked addresses", "runtime lineage addresses must be retained"),
        _finding(14, "public_boundary", _public(value.to_dict()), True, "public value", "runtime must contain no source paths or private records"),
        _finding(15, "canonical_runtime", canonical_json(value.to_dict()) == canonical_json(runtime_model.runtime_from_mapping(_strict_json_loads(runtime_model.runtime_json(value))).to_dict()), True, "canonical round-trip", "runtime serialization must be deterministic"),
    )
    provisional = RuntimeAudit(value.runtime_id, value.diff_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), f"pending:{AUDIT_PREFIX}")
    return _seal(provisional, address_audit)


def verify_audit(value: RuntimeAudit) -> RuntimeAudit:
    if not isinstance(value, RuntimeAudit):
        raise ValidationError("ledger diff runtime audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> RuntimeAudit:
    return RuntimeAudit.from_mapping(value)


def audit_json(value: RuntimeAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RuntimeAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: RuntimeAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Ledger diff runtime audit {value.runtime_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent D488 ledger diff runtime replay", "policy and lineage verification", "canonical check-address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "RuntimeAudit", "address_check", "address_audit", "audit_runtime", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
