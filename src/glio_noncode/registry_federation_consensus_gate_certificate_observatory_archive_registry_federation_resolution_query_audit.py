"""Independent audit contract for resolution query results."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.RESULT_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("query-address", "result-address", "row-order", "row-count", "pagination", "resource-bound", "filter-bound", "evidence", "row-addresses", "public-boundary")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return query_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "resolution query audit ordinal", MAX_CHECKS)
        self.check_id = _label(check_id, "resolution query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("resolution query audit check ID is unsupported")
        self.passed = _bool(passed, "resolution query audit result")
        self.detail = _text(detail, "resolution query audit detail", 4096)
        self.evidence_addresses = tuple(_text(item, "resolution query audit evidence address", 2048) for item in _sequence(evidence_addresses, "resolution query audit evidence", query_model.MAX_QUERY_ITEMS * 2 + 2))
        self.content_address = _address(content_address, "resolution query audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "resolution query audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("resolution query audit check evidence is not public")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("resolution query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck":
        value = _mapping(value, "resolution query audit check")
        _strict(value, set(cls.FIELDS), "resolution query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit:
    FIELDS = ("query_address", "result_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, query_address: str, result_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "resolution query audit query address", query_model.QUERY_PREFIX)
        self.result_address = _address(result_address, "resolution query audit result address", query_model.RESULT_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "resolution query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "resolution query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "resolution query audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "resolution query audit failed count", self.check_count)
        self.accepted = _bool(accepted, "resolution query audit acceptance")
        self.content_address = _address(content_address, "resolution query audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "resolution query audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("resolution query audit counters are not conserved")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("resolution query audit checks are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("resolution query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("resolution query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "result_address": self.result_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("query_address", "result_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit":
        value = _mapping(value, "resolution query audit")
        _strict(value, set(cls.FIELDS), "resolution query audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "resolution query audit checks", MAX_CHECKS))
        return cls(value["query_address"], value["result_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_query(value: query_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit:
    value = query_model.verify_query_result(value)
    query = value.query
    row_addresses = tuple(item.content_address for item in value.rows)
    checks = (
        _check(1, "query-address", query_model.address_query(query) == query.content_address, "query specification address replays", (query.content_address,)),
        _check(2, "result-address", query_model.address_result(value) == value.content_address, "query result address replays", (value.content_address,)),
        _check(3, "row-order", not value.rows or tuple(item.ordinal for item in value.rows) == tuple(range(query.offset + 1, query.offset + value.returned_count + 1)), "returned row ordinals are contiguous", row_addresses or (value.content_address,)),
        _check(4, "row-count", value.returned_count == len(value.rows) and value.returned_count <= value.matched_count <= value.total_count, "query row counters are conserved", (value.content_address,)),
        _check(5, "pagination", value.next_offset == query.offset + value.returned_count and value.truncated == (value.next_offset < query.offset + value.matched_count), "pagination metadata agrees with the result page", (value.content_address,)),
        _check(6, "resource-bound", all(item.resource in query_model.RESOURCES for item in value.rows), "rows use the declared resource vocabulary", row_addresses or (value.content_address,)),
        _check(7, "filter-bound", all((not query.entry_id or item.entry_id == query.entry_id) and (not query.state or item.state == query.state) and (not query.action or item.action == query.action) and (not query.package_id or item.package_id == query.package_id) for item in value.rows), "returned rows satisfy explicit filters", row_addresses or (value.content_address,)),
        _check(8, "evidence", all(item.evidence_addresses for item in value.rows), "every returned row carries evidence", row_addresses or (value.content_address,)),
        _check(9, "row-addresses", all(query_model.address_row(item) == item.content_address for item in value.rows), "row content addresses replay", row_addresses or (value.content_address,)),
        _check(10, "public-boundary", _public(value.to_dict()), "query projections contain no private fields", (value.content_address,)),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit(query.content_address, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit(provisional.query_address, provisional.result_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit):
        raise ValidationError("resolution query audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("resolution query audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Resolution Query Audit", "", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | result | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit.FIELDS), "properties": {"query_address": {"type": "string"}, "result_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "independent": True, "operations": ("audit_query", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
