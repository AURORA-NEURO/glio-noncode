"""Independent audit for bounded certificate observatory query results."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory as observatory_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = observatory_model.VERSION + "-query-audit-v1"
BOUNDARY = observatory_model.BOUNDARY + "_query_audit"
AUDIT_PREFIX = observatory_model.RESULT_PREFIX + "-audit"
FINDING_PREFIX = observatory_model.RESULT_PREFIX + "-audit-finding"
CHECK_IDS = ("exact-fields", "public-boundary", "query-link", "resource-conservation", "filter-conservation", "row-conservation", "pagination-conservation", "source-ordinal-conservation", "row-addresses", "content-address", "mapping-round-trip", "deterministic-resources", "path-free")


def _text(value: Any, field: str, maximum: int = observatory_model.MAX_TEXT, *, required: bool = False) -> str:
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.lower() not in forbidden and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return all(marker not in lowered for marker in ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\"))
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate observatory query audit finding ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "certificate observatory query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("certificate observatory query audit check ID is unsupported")
        self.passed = _bool(passed, "certificate observatory query audit finding result")
        self.observed = _text(observed, "certificate observatory query audit observed value")
        self.expected = _text(expected, "certificate observatory query audit expected value")
        self.detail = _text(detail, "certificate observatory query audit detail", required=True)
        self.content_address = _address(content_address, "certificate observatory query audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("certificate observatory query audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory query audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding:
        value = _mapping(value, "certificate observatory query audit finding")
        _strict(value, set(cls.FIELDS), "certificate observatory query audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding):
        raise ValidationError("certificate observatory query finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryQueryAudit:
    FIELDS = ("query_address", "result_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, query_address: str, result_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "audited certificate observatory query address", observatory_model.QUERY_PREFIX)
        self.result_address = _address(result_address, "audited certificate observatory result address", observatory_model.RESULT_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding) for item in self.checks):
            raise ValidationError("certificate observatory query audit checks must be typed")
        self.check_count = _count(check_count, "certificate observatory query audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "certificate observatory query audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "certificate observatory query audit failed count", self.check_count)
        self.accepted = _bool(accepted, "certificate observatory query audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("certificate observatory query audit counters are not conserved")
        self.content_address = _address(content_address, "certificate observatory query audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("certificate observatory query audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory query audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "result_address": self.result_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryQueryAudit:
        value = _mapping(value, "certificate observatory query audit")
        _strict(value, set(cls.FIELDS), "certificate observatory query audit")
        return cls(value["query_address"], value["result_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryQueryAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryQueryAudit):
        raise ValidationError("certificate observatory query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_query(value: observatory_model.RegistryFederationConsensusGateCertificateObservatoryQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryQueryAudit:
    """Recompute filter, resource, ordinal, pagination, and row-address invariants."""

    value = observatory_model.verify_query_result(value)
    query = value.query
    rows = value.rows
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(observatory_model.RegistryFederationConsensusGateCertificateObservatoryQueryResult.FIELDS), tuple(sorted(value.to_dict())), observatory_model.RegistryFederationConsensusGateCertificateObservatoryQueryResult.FIELDS, "query result fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "query result is public and path-free"),
        _finding(3, "query-link", query.content_address.startswith(observatory_model.QUERY_PREFIX + ":") and value.content_address.startswith(observatory_model.RESULT_PREFIX + ":"), (query.content_address, value.content_address), "address namespaces", "query and result namespaces are conserved"),
        _finding(4, "resource-conservation", all(item.resource in observatory_model.RESOURCES for item in rows) and tuple(query.resources) == tuple(item for item in observatory_model.RESOURCES if item in query.resources), query.resources, observatory_model.RESOURCES, "resources use the fixed order and vocabulary"),
        _finding(5, "filter-conservation", all((not query.history_id or item.history_id == query.history_id) and (not query.certificate_id or item.certificate_id == query.certificate_id) and (not query.state or item.state == query.state) and (not query.decision or item.decision == query.decision) and (query.accepted is None or item.accepted == query.accepted) for item in rows), "returned rows", query.to_dict(), "every returned row satisfies every filter"),
        _finding(6, "row-conservation", len(rows) == value.returned_count and value.returned_count <= value.matched_count <= value.total_count, (len(rows), value.returned_count, value.matched_count, value.total_count), "returned <= matched <= total", "row counters are conserved"),
        _finding(7, "pagination-conservation", tuple(item.ordinal for item in rows) == tuple(range(query.offset + 1, query.offset + value.returned_count + 1)) and value.truncated == (value.next_offset > 0) and ((not value.truncated and value.next_offset == 0) or (value.truncated and value.next_offset > query.offset)), (query.offset, value.returned_count, value.next_offset, value.truncated), "page ordinal and next-offset rules", "pagination is conserved"),
        _finding(8, "source-ordinal-conservation", all(1 <= item.observation_ordinal <= observatory_model.MAX_OBSERVATIONS and item.entry_ordinal >= 1 for item in rows), "bounded source ordinals", observatory_model.MAX_OBSERVATIONS, "source observation references remain bounded"),
        _finding(9, "row-addresses", all(observatory_model.address_row(item) == item.content_address for item in rows), "replayed row addresses", "stored row addresses", "every query row address replays"),
        _finding(10, "content-address", observatory_model.address_result(value) == value.content_address, value.content_address, observatory_model.address_result(value), "query result address replays"),
        _finding(11, "mapping-round-trip", observatory_model.query_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original query result", "mapping conversion is lossless"),
        _finding(12, "deterministic-resources", tuple(sorted(set(query.resources), key=observatory_model.RESOURCES.index)) == query.resources, query.resources, "fixed resource order", "resource order is deterministic"),
        _finding(13, "path-free", _public(value.to_dict()), True, True, "query result contains no local paths or attribution metadata"),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryQueryAudit(query.content_address, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryQueryAudit(provisional.query_address, provisional.result_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryQueryAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryQueryAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryQueryAudit) -> RegistryFederationConsensusGateCertificateObservatoryQueryAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryQueryAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("certificate observatory query audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryQueryAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryQueryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Release Certificate Observatory Query Audit", "", f"- Query: `{value.query_address}`", f"- Result: `{value.result_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryQueryAudit.FIELDS), "properties": {"query_address": {"type": "string", "pattern": "^" + observatory_model.QUERY_PREFIX + ":"}, "result_address": {"type": "string", "pattern": "^" + observatory_model.RESULT_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent observatory query checks", "resource and filter conservation", "pagination and source ordinal validation", "row address replay", "content-address verification", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryQueryAudit", "RegistryFederationConsensusGateCertificateObservatoryQueryAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
