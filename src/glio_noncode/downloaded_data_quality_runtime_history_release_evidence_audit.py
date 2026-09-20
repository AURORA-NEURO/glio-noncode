"""Independent replay audit for a downloaded-data quality release evidence package."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_runtime_history_release_evidence as evidence_model
from . import downloaded_data_quality_runtime_history_release_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = evidence_model.VERSION + "-audit-v1"
BOUNDARY = evidence_model.BOUNDARY + "_audit"
AUDIT_PREFIX = evidence_model.EVIDENCE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "gate_link",
    "gate_audit_link",
    "query_link",
    "query_audit_link",
    "gate_readiness",
    "gate_audit_acceptance",
    "query_completeness",
    "query_audit_acceptance",
    "summary_replay",
    "manifest_replay",
    "artifact_addresses",
    "public_boundary",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("evidence_id", "gate_id", "history_id", "evidence_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


def _public(value: Any) -> bool:
    return gate_model.history_model._public(value)


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "evidence audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "evidence audit check ID")
        self.passed = _bool(passed, "evidence audit check result")
        self.actual = _text(actual, "evidence audit actual", 32768)
        self.expected = _text(expected, "evidence audit expected", 32768)
        self.detail = _text(detail, "evidence audit detail", 4096)
        self.content_address = _address(content_address, "evidence audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.ordinal < 1 or self.check_id not in CHECK_IDS:
            raise ValidationError("evidence audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("evidence audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "evidence audit check")
        _strict(value, set(cls.FIELDS), "evidence audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("evidence audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class EvidenceAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, evidence_id: str, gate_id: str, history_id: str, evidence_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.evidence_id = _label(evidence_id, "evidence audit ID")
        self.gate_id = _label(gate_id, "evidence audit gate ID")
        self.history_id = _label(history_id, "evidence audit history ID")
        self.evidence_address = _address(evidence_address, "evidence audit evidence address", evidence_model.EVIDENCE_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "evidence audit check")) for item in _sequence(checks, "evidence audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "evidence audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "evidence audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "evidence audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "evidence audit acceptance")
        self.content_address = _address(content_address, "evidence audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("evidence audit checks are incomplete or out of order")
        if (self.passed_count, self.failed_count) != (sum(item.passed for item in self.checks), sum(not item.passed for item in self.checks)):
            raise ValidationError("evidence audit counters do not replay")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("evidence audit acceptance does not replay")
        if any(item.content_address != address_check(item) for item in self.checks):
            raise ValidationError("evidence audit check address does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("evidence audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceAudit":
        value = _mapping(value, "evidence audit")
        _strict(value, set(cls.FIELDS), "evidence audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: EvidenceAudit) -> str:
    if not isinstance(value, EvidenceAudit):
        raise ValidationError("evidence audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    return AuditCheck(ordinal, check_id, passed, canonical_json(actual), canonical_json(expected), detail, f"pending:{CHECK_PREFIX}")


def audit_evidence(value: evidence_model.ReleaseEvidence) -> EvidenceAudit:
    if not isinstance(value, evidence_model.ReleaseEvidence):
        raise ValidationError("evidence audit requires a typed evidence package")
    evidence_model.verify_evidence(value)
    expected_manifest = (
        value.evidence_id,
        value.gate_id,
        value.history_id,
        evidence_model.VERSION,
        evidence_model.BOUNDARY,
        evidence_model.FILES,
        (value.gate.content_address, value.gate_audit.content_address, value.query.content_address, value.query_audit.content_address, value.summary.content_address),
    )
    actual_manifest = (value.manifest.evidence_id, value.manifest.gate_id, value.manifest.history_id, value.manifest.version, value.manifest.boundary, value.manifest.files, value.manifest.artifact_addresses)
    checks = (
        _finding(1, "gate_link", (value.gate_id, value.history_id, value.gate_address) == (value.gate.gate_id, value.gate.history_id, value.gate.content_address), (value.gate_id, value.history_id, value.gate_address), (value.gate.gate_id, value.gate.history_id, value.gate.content_address), "evidence must link the supplied gate"),
        _finding(2, "gate_audit_link", (value.gate_audit.gate_id, value.gate_audit.history_id, value.gate_audit.gate_address) == (value.gate.gate_id, value.gate.history_id, value.gate.content_address), (value.gate_audit.gate_id, value.gate_audit.history_id, value.gate_audit.gate_address), (value.gate.gate_id, value.gate.history_id, value.gate.content_address), "evidence must link the gate audit"),
        _finding(3, "query_link", (value.query.gate_id, value.query.history_id, value.query.content_address) == (value.gate.gate_id, value.gate.history_id, value.query_address), (value.query.gate_id, value.query.history_id, value.query.content_address), (value.gate.gate_id, value.gate.history_id, value.query_address), "evidence must link the complete query"),
        _finding(4, "query_audit_link", (value.query_audit.query_id, value.query_audit.gate_id, value.query_audit.query_address) == (value.query.query_id, value.gate.gate_id, value.query.content_address), (value.query_audit.query_id, value.query_audit.gate_id, value.query_audit.query_address), (value.query.query_id, value.gate.gate_id, value.query.content_address), "evidence must link the query audit"),
        _finding(5, "gate_readiness", value.summary.release_ready == value.gate.release_ready and value.summary.gate_state == value.gate.state, (value.summary.release_ready, value.summary.gate_state), (value.gate.release_ready, value.gate.state), "summary must replay gate readiness"),
        _finding(6, "gate_audit_acceptance", value.summary.gate_audit_accepted == value.gate_audit.accepted, value.summary.gate_audit_accepted, value.gate_audit.accepted, "summary must replay gate audit acceptance"),
        _finding(7, "query_completeness", value.summary.query_complete == (not value.query.truncated and value.query.returned_count == value.query.total_count), value.summary.query_complete, not value.query.truncated and value.query.returned_count == value.query.total_count, "summary must replay query completeness"),
        _finding(8, "query_audit_acceptance", value.summary.query_audit_accepted == value.query_audit.accepted, value.summary.query_audit_accepted, value.query_audit.accepted, "summary must replay query audit acceptance"),
        _finding(9, "summary_replay", value.summary.content_address == evidence_model.address_summary(value.summary) and tuple(getattr(value.summary, field) for field in evidence_model.SUMMARY_FIELDS[:-1]) == (value.evidence_id, value.gate_id, value.history_id, value.gate.state, value.gate.release_ready, value.gate_audit.accepted, value.query_audit.accepted, not value.query.truncated and value.query.returned_count == value.query.total_count, value.summary.evidence_ready, value.gate.check_count, value.gate.passed_count, value.query.returned_count, value.query.total_count, len(value.query.resources)), value.summary.content_address, evidence_model.address_summary(value.summary), "summary fields and address must replay"),
        _finding(10, "manifest_replay", actual_manifest == expected_manifest, actual_manifest, expected_manifest, "manifest must replay all package files"),
        _finding(11, "artifact_addresses", (value.gate_address, value.gate_audit_address, value.query_address, value.query_audit_address) == (value.gate.content_address, value.gate_audit.content_address, value.query.content_address, value.query_audit.content_address), (value.gate_address, value.gate_audit_address, value.query_address, value.query_audit_address), (value.gate.content_address, value.gate_audit.content_address, value.query.content_address, value.query_audit.content_address), "artifact addresses must be canonical"),
        _finding(12, "public_boundary", _public(value.to_dict()), True, True, "evidence output must remain value-only and path-free"),
    )
    checks = tuple(_seal(item, address_check) for item in checks)
    passed = sum(item.passed for item in checks)
    result = EvidenceAudit(value.evidence_id, value.gate_id, value.history_id, value.content_address, checks, len(checks), passed, len(checks) - passed, passed == len(checks), f"pending:{AUDIT_PREFIX}")
    return _seal(result, address_audit)


def verify_audit(value: EvidenceAudit) -> EvidenceAudit:
    if not isinstance(value, EvidenceAudit):
        raise ValidationError("evidence audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> EvidenceAudit:
    return EvidenceAudit.from_mapping(value)


def audit_json(value: EvidenceAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: EvidenceAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: EvidenceAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Downloaded-data quality release evidence audit {value.evidence_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "actual": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent evidence identity replay", "cross-artifact link audit", "summary and manifest replay", "canonical JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "EvidenceAudit", "address_check", "address_audit", "audit_evidence", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
