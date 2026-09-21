"""Independent replay audit for runtime registry history diff runtimes."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d287_history_diff as diff_model
from . import downloaded_data_quality_d288_history_diff_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-audit-v1"
BOUNDARY = runtime_model.BOUNDARY + "_audit"
AUDIT_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("runtime_identity", "policy_identity", "check_sequence", "check_addresses", "counters", "disposition", "comparison_counts", "direction_policy", "transition_shape", "summary_replay", "manifest_replay", "diff_link", "policy_address", "runtime_address", "public_boundary")
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
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
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
    return diff_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff runtime audit check ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "history diff runtime audit check ID")
        self.passed = _bool(passed, "history diff runtime audit check result")
        self.actual = _text(canonical_json(actual), "history diff runtime audit actual", 16384)
        self.expected = _text(canonical_json(expected), "history diff runtime audit expected", 16384)
        self.detail = _text(detail, "history diff runtime audit detail", 4096)
        self.content_address = _address(content_address, "history diff runtime audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or (not self.passed and not self.detail):
            raise ValidationError("history diff runtime audit check is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("history diff runtime audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff runtime audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "history diff runtime audit check"); _strict(value, set(cls.FIELDS), "history diff runtime audit check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("history diff runtime audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class RuntimeAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, runtime_id: str, diff_id: str, runtime_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history diff runtime audit runtime ID")
        self.diff_id = _label(diff_id, "history diff runtime audit diff ID")
        self.runtime_address = _address(runtime_address, "history diff runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "history diff runtime audit check")) for item in _sequence(checks, "history diff runtime audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "history diff runtime audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "history diff runtime audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "history diff runtime audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "history diff runtime audit acceptance")
        self.content_address = _address(content_address, "history diff runtime audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("history diff runtime audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("history diff runtime audit check order does not replay")
        if any(item.content_address != address_check(item) for item in self.checks):
            raise ValidationError("history diff runtime audit check addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("history diff runtime audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff runtime audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeAudit":
        value = _mapping(value, "history diff runtime audit"); _strict(value, set(cls.FIELDS), "history diff runtime audit"); return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: RuntimeAudit) -> str:
    if not isinstance(value, RuntimeAudit):
        raise ValidationError("history diff runtime audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    return AuditCheck(ordinal, check_id, passed, actual, expected, detail, f"pending:{CHECK_PREFIX}")


def audit_runtime(value: runtime_model.DiffRuntime, diff: diff_model.HistoryDiff | None = None) -> RuntimeAudit:
    runtime_model.verify_runtime(value, diff)
    checks = value.checks
    transition_parts = value.state_transition.split("->")
    checks_out = (
        _finding(1, "runtime_identity", value.runtime_id == value.summary.runtime_id and value.diff_id == value.summary.diff_id, (value.runtime_id, value.diff_id), (value.summary.runtime_id, value.summary.diff_id), "runtime identity must replay"),
        _finding(2, "policy_identity", value.policy.diff_id == value.diff_id, value.policy.diff_id, value.diff_id, "policy must bind to the diff"),
        _finding(3, "check_sequence", tuple(item.check_id for item in checks) == runtime_model.CHECK_IDS and tuple(item.ordinal for item in checks) == tuple(range(1, runtime_model.MAX_CHECKS + 1)), tuple(item.check_id for item in checks), runtime_model.CHECK_IDS, "runtime checks must be complete and ordered"),
        _finding(4, "check_addresses", all(item.content_address == runtime_model.address_check(item) for item in checks), "replayed", "canonical", "runtime check addresses must replay"),
        _finding(5, "counters", (value.passed_count, value.failed_count) == (sum(item.passed for item in checks), sum(not item.passed for item in checks)), (value.passed_count, value.failed_count), (sum(item.passed for item in checks), sum(not item.passed for item in checks)), "runtime counters must replay"),
        _finding(6, "disposition", (value.release_ready, value.state) == (value.failed_count == 0, "ready" if value.failed_count == 0 else "blocked"), (value.release_ready, value.state), (value.failed_count == 0, "ready" if value.failed_count == 0 else "blocked"), "runtime disposition must replay"),
        _finding(7, "comparison_counts", value.added_count + value.removed_count + value.changed_count <= value.item_count, (value.added_count, value.removed_count, value.changed_count, value.item_count), "counts within item count", "comparison counts must be bounded"),
        _finding(8, "direction_policy", value.direction in runtime_model.diff_model.DIRECTIONS and value.direction in value.policy.allowed_directions, value.direction, value.policy.allowed_directions, "direction must satisfy policy"),
        _finding(9, "transition_shape", len(transition_parts) == 2 and all(part in runtime_model.diff_model.history_model.STATES for part in transition_parts), value.state_transition, "state->state", "state transition must be explicit"),
        _finding(10, "summary_replay", tuple(getattr(value.summary, field) for field in runtime_model.SUMMARY_FIELDS[:-1]) == (value.runtime_id, value.diff_id, value.diff_address, runtime_model.address_policy(value.policy), value.check_count, value.passed_count, value.failed_count, value.release_ready, value.state, value.direction, value.state_transition, value.item_count, value.added_count, value.removed_count, value.changed_count, value.accepted) and value.summary.content_address == runtime_model.address_summary(value.summary), "replayed", "canonical", "summary must replay runtime"),
        _finding(11, "manifest_replay", tuple(getattr(value.manifest, field) for field in runtime_model.MANIFEST_FIELDS[:-1]) == (value.runtime_id, value.diff_id, runtime_model.VERSION, runtime_model.BOUNDARY, runtime_model.FILES, (runtime_model.address_checks(checks), value.summary.content_address)) and value.manifest.content_address == runtime_model.address_manifest(value.manifest), "replayed", "canonical", "manifest must replay runtime"),
        _finding(12, "diff_link", value.diff_address.startswith(runtime_model.diff_model.DIFF_PREFIX + ":") and (diff is None or diff.content_address == value.diff_address), value.diff_address, runtime_model.diff_model.DIFF_PREFIX, "diff link must use the canonical namespace"),
        _finding(13, "policy_address", value.policy.content_address == runtime_model.address_policy(value.policy), value.policy.content_address, runtime_model.address_policy(value.policy), "policy address must replay"),
        _finding(14, "runtime_address", value.content_address == runtime_model.address_runtime(value), value.content_address, runtime_model.address_runtime(value), "runtime address must replay"),
        _finding(15, "public_boundary", _public(value.to_dict()), True, True, "runtime audit must remain value-only and path-free"),
    )
    sealed = tuple(_seal(item, address_check) for item in checks_out); passed = sum(item.passed for item in sealed)
    return _seal(RuntimeAudit(value.runtime_id, value.diff_id, value.content_address, sealed, len(sealed), passed, len(sealed) - passed, passed == len(sealed), f"pending:{AUDIT_PREFIX}"), address_audit)


def verify_audit(value: RuntimeAudit) -> RuntimeAudit:
    if not isinstance(value, RuntimeAudit):
        raise ValidationError("history diff runtime audit verification requires a typed audit")
    value._validate(); return value


def audit_from_mapping(value: Mapping[str, Any]) -> RuntimeAudit:
    return RuntimeAudit.from_mapping(value)


def audit_json(value: RuntimeAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RuntimeAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_audit(value).checks); return output.getvalue()


def render_audit_markdown(value: RuntimeAudit) -> str:
    value = verify_audit(value); lines = [f"# Runtime registry history diff runtime audit {value.runtime_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks); return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffRuntimeAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffRuntimeAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent diff runtime replay", "policy and disposition verification", "canonical check-address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "RuntimeAudit", "address_check", "address_audit", "audit_runtime", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]















