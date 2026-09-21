"""Independent audit projections for D477 release batches."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d477_release_batch as batch_model
from . import downloaded_data_quality_d476_history_diff_runtime as runtime_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = batch_model.VERSION + "-audit-v1"
BOUNDARY = batch_model.BOUNDARY + "_audit"
AUDIT_PREFIX = batch_model.BATCH_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("typed_batch", "batch_address", "item_sequence", "check_sequence", "counter_replay", "summary_replay", "manifest_replay", "policy_replay", "unique_runtime_ids", "unique_runtime_addresses", "item_addresses", "runtime_links", "audit_requirement", "threshold_replay", "disposition_replay", "canonical_public")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("batch_id", "batch_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)
MAX_BYTES = 16 * 1024 * 1024


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
    return runtime_model.diff_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release batch audit check ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "release batch audit check ID")
        self.passed = _bool(passed, "release batch audit result")
        self.actual = _text(actual, "release batch audit actual", 32768)
        self.expected = _text(expected, "release batch audit expected", 32768)
        self.detail = _text(detail, "release batch audit detail", 4096)
        self.content_address = _address(content_address, "release batch audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("release batch audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("release batch audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "release batch audit check")
        _strict(value, set(cls.FIELDS), "release batch audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("release batch audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class BatchAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, batch_id: str, batch_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.batch_id = _label(batch_id, "release batch audit batch ID")
        self.batch_address = _address(batch_address, "release batch audit batch address", batch_model.BATCH_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "release batch audit check")) for item in _sequence(checks, "release batch audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "release batch audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "release batch audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "release batch audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "release batch audit acceptance")
        self.content_address = _address(content_address, "release batch audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("release batch audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("release batch audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("release batch audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"batch_id": self.batch_id, "batch_address": self.batch_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchAudit":
        value = _mapping(value, "release batch audit")
        _strict(value, set(cls.FIELDS), "release batch audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: BatchAudit) -> str:
    if not isinstance(value, BatchAudit):
        raise ValidationError("release batch audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_batch(value: batch_model.ReleaseBatch, runtimes: Sequence[runtime_model.DiffRuntime] | None = None) -> BatchAudit:
    typed = tuple(runtimes or ())
    for runtime in typed:
        runtime_model.verify_runtime(runtime)
    batch_model.verify_batch(value)
    items = value.items
    runtime_by_id = {runtime.runtime_id: runtime for runtime in typed}
    links = not typed or (len(runtime_by_id) == len(items) and all(runtime_by_id.get(item.runtime_id) is not None and runtime_by_id[item.runtime_id].content_address == item.runtime_address for item in items))
    thresholds = value.item_count >= value.policy.minimum_runtimes and value.ready_count >= value.policy.minimum_ready and value.blocked_count <= value.policy.maximum_blocked
    checks = (
        _finding(1, "typed_batch", isinstance(value, batch_model.ReleaseBatch), type(value).__name__, "ReleaseBatch", "the audited value must use the typed release batch model"),
        _finding(2, "batch_address", batch_model.address_batch(value) == value.content_address, value.content_address, batch_model.address_batch(value), "the root content address must replay"),
        _finding(3, "item_sequence", tuple(item.ordinal for item in items) == tuple(range(1, len(items) + 1)), [item.ordinal for item in items], "contiguous ordinals", "items must preserve deterministic order"),
        _finding(4, "check_sequence", tuple(item.check_id for item in value.checks) == batch_model.CHECK_IDS, [item.check_id for item in value.checks], batch_model.CHECK_IDS, "all aggregate checks must be present in order"),
        _finding(5, "counter_replay", (value.ready_count, value.blocked_count, value.audited_count, value.accepted_count) == (sum(item.state == "ready" for item in items), sum(item.state == "blocked" for item in items), sum(bool(item.audit_address) for item in items), sum(item.accepted for item in items)), value.summary.to_dict(), "replayed counters", "summary counters must derive from items"),
        _finding(6, "summary_replay", value.summary.content_address == batch_model.address_summary(value.summary), value.summary.content_address, batch_model.address_summary(value.summary), "summary address and fields must replay"),
        _finding(7, "manifest_replay", value.manifest.content_address == batch_model.address_manifest(value.manifest), value.manifest.content_address, batch_model.address_manifest(value.manifest), "manifest address and file contract must replay"),
        _finding(8, "policy_replay", value.policy.content_address == batch_model.address_policy(value.policy), value.policy.content_address, batch_model.address_policy(value.policy), "policy address must replay"),
        _finding(9, "unique_runtime_ids", len({item.runtime_id for item in items}) == len(items), [item.runtime_id for item in items], "unique IDs", "runtime IDs must be unique"),
        _finding(10, "unique_runtime_addresses", len({item.runtime_address for item in items}) == len(items), [item.runtime_address for item in items], "unique addresses", "runtime addresses must be unique"),
        _finding(11, "item_addresses", all(batch_model.address_item(item) == item.content_address for item in items), True, "replayed item addresses", "every item address must replay independently"),
        _finding(12, "runtime_links", links, len(runtime_by_id), len(items), "linked runtime evidence must agree with item identities when supplied"),
        _finding(13, "audit_requirement", (not value.policy.require_audited) or value.audited_count == value.item_count, value.audited_count, value.item_count, "required audit evidence must be present"),
        _finding(14, "threshold_replay", thresholds, (value.item_count, value.ready_count, value.blocked_count), (value.policy.minimum_runtimes, value.policy.minimum_ready, value.policy.maximum_blocked), "policy thresholds must explain the aggregate disposition"),
        _finding(15, "disposition_replay", value.release_ready == (value.accepted and value.item_count > 0) and value.state == ("empty" if value.item_count == 0 else "ready" if value.release_ready else "blocked"), (value.accepted, value.release_ready, value.state), "replayed disposition", "state must follow checks and readiness"),
        _finding(16, "canonical_public", _public(value.to_dict()) and canonical_json(value.to_dict()) == canonical_json(batch_model.batch_from_mapping(_strict_json_loads(batch_model.batch_json(value))).to_dict()), True, "canonical public value", "the complete batch must round-trip without private fields",),
    )
    provisional = BatchAudit(value.batch_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), f"pending:{AUDIT_PREFIX}")
    return _seal(provisional, address_audit)


def verify_audit(value: BatchAudit) -> BatchAudit:
    if not isinstance(value, BatchAudit):
        raise ValidationError("release batch audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> BatchAudit:
    return BatchAudit.from_mapping(value)


def audit_json(value: BatchAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: BatchAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: BatchAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Release batch audit {value.batch_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}, "$defs": {"check": check_schema()}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent release batch replay", "runtime identity and address verification", "policy threshold verification", "canonical evidence round-trip", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "MAX_BYTES", "AuditCheck", "BatchAudit", "address_check", "address_audit", "audit_batch", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
