"""Independent replay audit for release evidence query projections."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_runtime_history_release_evidence as evidence_model
from . import downloaded_data_quality_runtime_history_release_evidence_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = evidence_model.VERSION + "-query-audit-v1"
BOUNDARY = evidence_model.BOUNDARY + "_query_audit"
AUDIT_PREFIX = evidence_model.EVIDENCE_PREFIX + "-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("identity_link", "evidence_link", "resource_set", "filter_replay", "total_count", "returned_count", "pagination", "row_order", "row_addresses", "query_address", "complete_projection", "public_boundary")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("query_id", "evidence_id", "gate_id", "history_id", "query_address", "evidence_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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


def _public(value: Any) -> bool:
    return evidence_model.gate_model.history_model._public(value)


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "evidence query audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "evidence query audit check ID")
        self.passed = _bool(passed, "evidence query audit check result")
        self.actual = _text(actual, "evidence query audit actual", 32768)
        self.expected = _text(expected, "evidence query audit expected", 32768)
        self.detail = _text(detail, "evidence query audit detail", 4096)
        self.content_address = _address(content_address, "evidence query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("evidence query audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("evidence query audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence query audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "evidence query audit check")
        _strict(value, set(cls.FIELDS), "evidence query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("evidence query audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class EvidenceQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_id: str, evidence_id: str, gate_id: str, history_id: str, query_address: str, evidence_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_id = _label(query_id, "evidence query audit query ID")
        self.evidence_id = _label(evidence_id, "evidence query audit evidence ID")
        self.gate_id = _label(gate_id, "evidence query audit gate ID")
        self.history_id = _label(history_id, "evidence query audit history ID")
        self.query_address = _address(query_address, "evidence query audit query address", query_model.QUERY_PREFIX)
        self.evidence_address = _address(evidence_address, "evidence query audit evidence address", evidence_model.EVIDENCE_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "evidence query audit check")) for item in _sequence(checks, "evidence query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "evidence query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "evidence query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "evidence query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "evidence query audit acceptance")
        self.content_address = _address(content_address, "evidence query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("evidence query audit checks are incomplete or out of order")
        if (self.passed_count, self.failed_count) != (sum(item.passed for item in self.checks), sum(not item.passed for item in self.checks)):
            raise ValidationError("evidence query audit counters do not replay")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("evidence query audit acceptance does not replay")
        if any(item.content_address != address_check(item) for item in self.checks):
            raise ValidationError("evidence query audit check address does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("evidence query audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence query audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceQueryAudit":
        value = _mapping(value, "evidence query audit")
        _strict(value, set(cls.FIELDS), "evidence query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: EvidenceQueryAudit) -> str:
    if not isinstance(value, EvidenceQueryAudit):
        raise ValidationError("evidence query audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    return AuditCheck(ordinal, check_id, passed, canonical_json(actual), canonical_json(expected), detail, f"pending:{CHECK_PREFIX}")


def audit_query(query: query_model.EvidenceQuery, evidence: evidence_model.ReleaseEvidence) -> EvidenceQueryAudit:
    if not isinstance(query, query_model.EvidenceQuery) or not isinstance(evidence, evidence_model.ReleaseEvidence):
        raise ValidationError("evidence query audit requires typed query and evidence")
    evidence_model.verify_evidence(evidence)
    query._validate()
    replay = query_model.query_evidence(evidence, query_id=query.query_id, resources=query.resources, state_filter=query.state_filter, passed_filter=query.passed_filter, severity_filter=query.severity_filter, text_filter=query.text_filter, offset=query.offset, limit=query.limit)
    checks = (
        _finding(1, "identity_link", (query.query_id, query.evidence_id, query.gate_id, query.history_id) == (replay.query_id, evidence.evidence_id, evidence.gate_id, evidence.history_id), (query.query_id, query.evidence_id, query.gate_id, query.history_id), (replay.query_id, evidence.evidence_id, evidence.gate_id, evidence.history_id), "query identity must link evidence"),
        _finding(2, "evidence_link", query.evidence_id == evidence.evidence_id, query.evidence_id, evidence.evidence_id, "query must identify its evidence package"),
        _finding(3, "resource_set", query.resources == replay.resources, query.resources, replay.resources, "query resource selection must replay"),
        _finding(4, "filter_replay", (query.state_filter, query.passed_filter, query.severity_filter, query.text_filter) == (replay.state_filter, replay.passed_filter, replay.severity_filter, replay.text_filter), (query.state_filter, query.passed_filter, query.severity_filter, query.text_filter), (replay.state_filter, replay.passed_filter, replay.severity_filter, replay.text_filter), "query filters must replay"),
        _finding(5, "total_count", query.total_count == replay.total_count, query.total_count, replay.total_count, "total row count must replay"),
        _finding(6, "returned_count", query.returned_count == replay.returned_count, query.returned_count, replay.returned_count, "returned row count must replay"),
        _finding(7, "pagination", (query.offset, query.limit, query.truncated) == (replay.offset, replay.limit, replay.truncated), (query.offset, query.limit, query.truncated), (replay.offset, replay.limit, replay.truncated), "pagination must replay"),
        _finding(8, "row_order", tuple(item.ordinal for item in query.rows) == tuple(item.ordinal for item in replay.rows), tuple(item.ordinal for item in query.rows), tuple(item.ordinal for item in replay.rows), "row ordinals must replay"),
        _finding(9, "row_addresses", tuple(item.content_address for item in query.rows) == tuple(item.content_address for item in replay.rows), tuple(item.content_address for item in query.rows), tuple(item.content_address for item in replay.rows), "row addresses must replay"),
        _finding(10, "query_address", query.content_address == query_model.address_query(query), query.content_address, query_model.address_query(query), "query address must replay"),
        _finding(11, "complete_projection", query.to_dict() == replay.to_dict(), (query.content_address, query.returned_count, query.total_count), (replay.content_address, replay.returned_count, replay.total_count), "query projection must be deterministic"),
        _finding(12, "public_boundary", _public(query.to_dict()) and _public(evidence.to_dict()), True, True, "query audit output must remain value-only and path-free"),
    )
    checks = tuple(item for item in checks)
    checks = tuple(type(item)(item.ordinal, item.check_id, item.passed, item.actual, item.expected, item.detail, address_check(item)) for item in checks)
    passed = sum(item.passed for item in checks)
    result = EvidenceQueryAudit(query.query_id, evidence.evidence_id, evidence.gate_id, evidence.history_id, query.content_address, evidence.content_address, checks, len(checks), passed, len(checks) - passed, passed == len(checks), f"pending:{AUDIT_PREFIX}")
    result.content_address = address_audit(result)
    result._validate()
    return result


def verify_audit(value: EvidenceQueryAudit) -> EvidenceQueryAudit:
    if not isinstance(value, EvidenceQueryAudit):
        raise ValidationError("evidence query audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> EvidenceQueryAudit:
    return EvidenceQueryAudit.from_mapping(value)


def audit_json(value: EvidenceQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: EvidenceQueryAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: EvidenceQueryAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Downloaded-data quality release evidence query audit {value.query_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "actual": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("deterministic query replay", "pagination and filter audit", "row address audit", "canonical JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "EvidenceQueryAudit", "address_check", "address_audit", "audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
