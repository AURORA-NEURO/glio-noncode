"""Independent audit for bounded consensus gate certificate query results."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate as certificate_model
from . import registry_federation_consensus_gate_certificate_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = certificate_model.CERTIFICATE_PREFIX + "-query-audit"
CHECK_PREFIX = certificate_model.CERTIFICATE_PREFIX + "-query-audit-check"
CHECK_IDS = ("exact-fields", "public-boundary", "query-link", "resource-conservation", "filter-conservation", "row-conservation", "pagination-conservation", "address-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 32768, *, required: bool = False) -> str:
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


class RegistryFederationConsensusGateCertificateQueryAuditFinding:
    """One independent assertion about a filtered query result."""

    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate query audit finding ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "certificate query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("certificate query audit check ID is unsupported")
        self.passed = _bool(passed, "certificate query audit finding result")
        self.observed = _text(observed, "certificate query audit observed value")
        self.expected = _text(expected, "certificate query audit expected value")
        self.detail = _text(detail, "certificate query audit detail", required=True)
        self.content_address = _address(content_address, "certificate query audit finding address", CHECK_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("certificate query audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate query audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateQueryAuditFinding:
        value = _mapping(value, "certificate query audit finding")
        _strict(value, set(cls.FIELDS), "certificate query audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateQueryAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateQueryAuditFinding):
        raise ValidationError("certificate query audit finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateQueryAudit:
    """Addressed audit of one certificate query projection."""

    FIELDS = ("result_address", "query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, result_address: str, query_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateQueryAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.result_address = _address(result_address, "audited certificate query result address", query_model.RESULT_PREFIX)
        self.query_address = _address(query_address, "audited certificate query address", query_model.QUERY_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateQueryAuditFinding) for item in self.checks):
            raise ValidationError("certificate query audit checks must be typed")
        self.check_count = _count(check_count, "certificate query audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "certificate query audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "certificate query audit failed count", self.check_count)
        self.accepted = _bool(accepted, "certificate query audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("certificate query audit counters are not conserved")
        self.content_address = _address(content_address, "certificate query audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("certificate query audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate query audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"result_address": self.result_address, "query_address": self.query_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateQueryAudit:
        value = _mapping(value, "certificate query audit")
        _strict(value, set(cls.FIELDS), "certificate query audit")
        return cls(value["result_address"], value["query_address"], tuple(RegistryFederationConsensusGateCertificateQueryAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateQueryAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateQueryAudit):
        raise ValidationError("certificate query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateCertificateQueryAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateQueryAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateQueryAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_query(value: query_model.RegistryFederationConsensusGateCertificateQueryResult) -> RegistryFederationConsensusGateCertificateQueryAudit:
    """Recompute resource, filter, pagination, and address conservation."""

    value = query_model.verify_query_result(value)
    query = value.query
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(query_model.RegistryFederationConsensusGateCertificateQueryResult.FIELDS), tuple(sorted(value.to_dict())), query_model.RegistryFederationConsensusGateCertificateQueryResult.FIELDS, "query result fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "query result is public and path-free"),
        _finding(3, "query-link", query.certificate_address.startswith(certificate_model.CERTIFICATE_PREFIX + ":"), query.certificate_address, certificate_model.CERTIFICATE_PREFIX + ":", "query points to its certificate"),
        _finding(4, "resource-conservation", all(row.resource in query.resources for row in value.rows), tuple(row.resource for row in value.rows), query.resources, "returned rows belong to requested resources"),
        _finding(5, "filter-conservation", all((not query.check_id or row.check_id == query.check_id) and (query.passed is None or row.passed == query.passed) for row in value.rows), "returned row filters", query.to_dict(), "every returned row satisfies the query filters"),
        _finding(6, "row-conservation", value.returned_count == len(value.rows) and tuple(row.ordinal for row in value.rows) == tuple(range(query.offset + 1, query.offset + value.returned_count + 1)), (value.returned_count, len(value.rows)), "ordered returned rows", "row count and ordinals replay"),
        _finding(7, "pagination-conservation", value.next_offset == (query.offset + value.returned_count if value.truncated else 0) and value.truncated == (value.next_offset > 0), (value.next_offset, value.truncated), "next offset iff truncated", "pagination state is consistent"),
        _finding(8, "address-conservation", query_model.address_query(query) == query.content_address and all(query_model.address_row(row) == row.content_address for row in value.rows) and query_model.address_result(value) == value.content_address, "replayed query, row, and result addresses", "stored addresses", "all nested query addresses replay"),
        _finding(9, "content-address", query_model.address_result(value) == value.content_address, value.content_address, query_model.address_result(value), "result content address replays"),
        _finding(10, "mapping-round-trip", query_model.query_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original result", "mapping conversion is lossless"),
        _finding(11, "path-free", _public(value.to_dict()), True, True, "query output contains no local paths"),
    )
    provisional = RegistryFederationConsensusGateCertificateQueryAudit(value.content_address, query.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateQueryAudit(provisional.result_address, provisional.query_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateQueryAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateQueryAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateQueryAudit) -> RegistryFederationConsensusGateCertificateQueryAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateQueryAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("certificate query audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateQueryAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateQueryAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for finding in value.checks:
        writer.writerow(finding.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateQueryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Release Certificate Query Audit", "", f"- Result: `{value.result_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateQueryAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateQueryAudit.FIELDS), "properties": {"result_address": {"type": "string", "pattern": "^" + query_model.RESULT_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "features": ("independent query-result checks", "resource and filter conservation", "pagination verification", "nested address replay", "mapping round-trip verification", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "RegistryFederationConsensusGateCertificateQueryAudit", "RegistryFederationConsensusGateCertificateQueryAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
