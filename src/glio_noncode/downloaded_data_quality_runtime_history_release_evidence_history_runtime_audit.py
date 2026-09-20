"""Independent replay audit for policy-driven history runtimes."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_runtime_history_release_evidence_history as history_model
from . import downloaded_data_quality_runtime_history_release_evidence_history_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-audit-v1"
BOUNDARY = runtime_model.BOUNDARY + "_audit"
AUDIT_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("runtime_identity", "policy_identity", "check_sequence", "check_addresses", "counters", "disposition", "latest_projection", "summary_replay", "manifest_replay", "history_link", "runtime_address", "policy_address", "artifact_addresses", "public_boundary")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("runtime_id", "history_id", "history_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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
    return history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "runtime audit check ID")
        self.passed = _bool(passed, "runtime audit check result")
        self.actual = _text(actual, "runtime audit actual", 32768)
        self.expected = _text(expected, "runtime audit expected", 32768)
        self.detail = _text(detail, "runtime audit detail", 4096)
        self.content_address = _address(content_address, "runtime audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("runtime audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("runtime audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "runtime audit check")
        _strict(value, set(cls.FIELDS), "runtime audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("runtime audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class RuntimeAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, runtime_id: str, history_id: str, history_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "runtime audit runtime ID")
        self.history_id = _label(history_id, "runtime audit history ID")
        self.history_address = _address(history_address, "runtime audit history address", history_model.HISTORY_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "runtime audit check")) for item in _sequence(checks, "runtime audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "runtime audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime audit acceptance")
        self.content_address = _address(content_address, "runtime audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime audit checks are incomplete or out of order")
        if (self.passed_count, self.failed_count) != (sum(item.passed for item in self.checks), sum(not item.passed for item in self.checks)):
            raise ValidationError("runtime audit counters do not replay")
        if self.accepted != (self.failed_count == 0) or any(item.content_address != address_check(item) for item in self.checks):
            raise ValidationError("runtime audit acceptance or check addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("runtime audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeAudit":
        value = _mapping(value, "runtime audit")
        _strict(value, set(cls.FIELDS), "runtime audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: RuntimeAudit) -> str:
    if not isinstance(value, RuntimeAudit):
        raise ValidationError("runtime audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    return AuditCheck(ordinal, check_id, passed, canonical_json(actual), canonical_json(expected), detail, f"pending:{CHECK_PREFIX}")


def audit_runtime(value: runtime_model.HistoryRuntime, history: history_model.EvidenceHistory | None = None) -> RuntimeAudit:
    runtime_model.verify_runtime(value, history)
    checks = value.checks
    expected_summary = (value.runtime_id, value.history_id, value.history_address, runtime_model.address_policy(value.policy), value.check_count, value.passed_count, value.failed_count, value.release_ready, value.state, value.latest_state, value.latest_ready, value.entry_count, value.regressed_count, value.blocked_count)
    actual_summary = tuple(getattr(value.summary, field) for field in runtime_model.SUMMARY_FIELDS[:-1])
    expected_manifest = (value.runtime_id, value.history_id, runtime_model.VERSION, runtime_model.BOUNDARY, runtime_model.FILES, (runtime_model.address_checks(checks), value.summary.content_address))
    actual_manifest = (value.manifest.runtime_id, value.manifest.history_id, value.manifest.version, value.manifest.boundary, value.manifest.files, value.manifest.artifact_addresses)
    findings = (
        _finding(1, "runtime_identity", value.runtime_id == value.summary.runtime_id == value.manifest.runtime_id and value.history_id == value.summary.history_id == value.manifest.history_id, value.runtime_id, value.summary.runtime_id, "runtime identity must agree across projections"),
        _finding(2, "policy_identity", value.policy.history_id == value.history_id and value.summary.policy_address == runtime_model.address_policy(value.policy), value.policy.history_id, value.history_id, "policy must target the runtime history"),
        _finding(3, "check_sequence", tuple(item.check_id for item in checks) == runtime_model.CHECK_IDS and tuple(item.ordinal for item in checks) == tuple(range(1, runtime_model.MAX_CHECKS + 1)), tuple(item.check_id for item in checks), runtime_model.CHECK_IDS, "runtime checks must be complete and ordered"),
        _finding(4, "check_addresses", all(item.content_address == runtime_model.address_check(item) for item in checks), "replayed", "canonical", "runtime check addresses must replay"),
        _finding(5, "counters", (value.passed_count, value.failed_count) == (sum(item.passed for item in checks), sum(not item.passed for item in checks)), (value.passed_count, value.failed_count), (sum(item.passed for item in checks), sum(not item.passed for item in checks)), "runtime counters must replay"),
        _finding(6, "disposition", (value.release_ready, value.state) == (value.failed_count == 0, "ready" if value.failed_count == 0 else "blocked"), (value.release_ready, value.state), (value.failed_count == 0, "ready" if value.failed_count == 0 else "blocked"), "release disposition must replay"),
        _finding(7, "latest_projection", (value.latest_state, value.latest_ready) == (value.summary.latest_state, value.summary.latest_ready), (value.latest_state, value.latest_ready), (value.summary.latest_state, value.summary.latest_ready), "latest history projection must replay"),
        _finding(8, "summary_replay", actual_summary == expected_summary and value.summary.content_address == runtime_model.address_summary(value.summary), actual_summary, expected_summary, "summary fields and address must replay"),
        _finding(9, "manifest_replay", actual_manifest == expected_manifest and value.manifest.content_address == runtime_model.address_manifest(value.manifest), actual_manifest, expected_manifest, "manifest fields and address must replay"),
        _finding(10, "history_link", history is None or (history.content_address == value.history_address and history.history_id == value.history_id), value.history_address, history.content_address if history else "not-supplied", "history link must agree when source history is supplied"),
        _finding(11, "runtime_address", value.content_address == runtime_model.address_runtime(value), value.content_address, runtime_model.address_runtime(value), "runtime address must replay"),
        _finding(12, "policy_address", value.policy.content_address == runtime_model.address_policy(value.policy), value.policy.content_address, runtime_model.address_policy(value.policy), "policy address must replay"),
        _finding(13, "artifact_addresses", value.manifest.artifact_addresses == (runtime_model.address_checks(checks), value.summary.content_address), value.manifest.artifact_addresses, (runtime_model.address_checks(checks), value.summary.content_address), "artifact addresses must replay"),
        _finding(14, "public_boundary", _public(value.to_dict()), True, True, "runtime audit output must remain value-only and path-free"),
    )
    sealed = tuple(_seal(item, address_check) for item in findings)
    passed = sum(item.passed for item in sealed)
    return _seal(RuntimeAudit(value.runtime_id, value.history_id, value.history_address, sealed, len(sealed), passed, len(sealed) - passed, passed == len(sealed), f"pending:{AUDIT_PREFIX}"), address_audit)


def verify_audit(value: RuntimeAudit) -> RuntimeAudit:
    if not isinstance(value, RuntimeAudit):
        raise ValidationError("runtime audit verification requires a typed audit")
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
    lines = [f"# Runtime audit {value.runtime_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent runtime replay", "optional source-history link verification", "canonical check addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "RuntimeAudit", "address_check", "address_audit", "audit_runtime", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
