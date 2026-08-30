"""Independent checks for archive query pages.

A query audit is intentionally independent from the query builder.  It checks
the delivered page, not merely the source archive: declared resources, name
and text filters, row ordinals, pagination conservation, nested row addresses,
mapping replay, and public-boundary safety.  A downstream reviewer can retain
this small receipt beside a page exported from a larger archive.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.RESULT_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
CHECK_IDS = ("query-address", "resource-vocabulary", "filter-shape", "filter-compliance", "row-count", "ordinal-order", "pagination", "row-addresses", "result-address", "mapping-round-trip", "public-boundary", "path-free", "bounded-page")


def _text(value: Any, field: str, maximum: int = 2048) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if ":" not in value or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
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
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return archive_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_address: str, content_address: str) -> None:
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1 or ordinal > len(CHECK_IDS) or check_id not in CHECK_IDS:
            raise ValidationError("query audit finding identity is invalid")
        self.ordinal = ordinal
        self.check_id = check_id
        self.passed = _bool(passed, "query finding pass state")
        self.detail = _text(detail, "query finding detail")
        self.evidence_address = _address(evidence_address, "query finding evidence")
        self.content_address = _address(content_address, "query finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("query finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAuditFinding":
        value = _mapping(value, "query audit finding")
        _strict(value, set(cls.FIELDS), "query audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


class RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit:
    FIELDS = ("result_address", "query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, result_address: str, query_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.result_address = _address(result_address, "query audit result address", query_model.RESULT_PREFIX)
        self.query_address = _address(query_address, "query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(checks)
        self.check_count = _count(check_count, "query audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "query audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "query audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "query audit acceptance")
        self.content_address = _address(content_address, "query audit address", AUDIT_PREFIX)
        if self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("query audit check order is invalid")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("query audit counters are not conserved")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("query audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("query audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"result_address": self.result_address, "query_address": self.query_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("result_address", "query_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAuditFinding):
        raise ValidationError("query finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit):
        raise ValidationError("query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, detail: str, evidence: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAuditFinding(ordinal, check_id, passed, detail, evidence, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAuditFinding(ordinal, check_id, passed, detail, evidence, address_finding(provisional))


def audit_query(value: query_model.RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit:
    if not isinstance(value, query_model.RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult):
        raise ValidationError("archive query audit requires a typed result")
    query_model.verify_result(value)
    rows = value.rows
    resources_ok = bool(value.query.resources) and all(row.resource in query_model.RESOURCE_NAMES for row in rows)
    filter_shape_ok = not value.query.name or len(value.query.name) <= query_model.MAX_TEXT
    filter_ok = all((not value.query.name or row.payload.get("name") == value.query.name) and (not value.query.text or value.query.text.lower() in canonical_json(row.payload).lower()) for row in rows)
    ordinals_ok = tuple(row.ordinal for row in rows) == tuple(range(value.query.offset, value.query.offset + len(rows)))
    pagination_ok = value.returned == len(rows) and value.truncated == (value.next_offset is not None) and (value.next_offset is None or value.next_offset == value.query.offset + value.returned)
    row_addresses_ok = all(query_model.address_row(row) == row.content_address for row in rows)
    mapping_ok = query_model.query_from_mapping(value.to_dict()).to_dict() == value.to_dict()
    checks = (
        _finding(1, "query-address", query_model.address_query(value.query) == value.query.content_address, "query request address reproduces", value.query.content_address),
        _finding(2, "resource-vocabulary", resources_ok, "resources and returned row labels use the declared vocabulary", value.content_address),
        _finding(3, "filter-shape", filter_shape_ok, "filter values stay within their bounded contract", value.query.content_address),
        _finding(4, "filter-compliance", filter_ok, "every returned row satisfies every requested filter", value.content_address),
        _finding(5, "row-count", value.returned == len(rows) and value.returned <= value.query.limit, "returned counter equals the delivered bounded page", value.content_address),
        _finding(6, "ordinal-order", ordinals_ok, "row ordinals preserve the requested page offset", value.content_address),
        _finding(7, "pagination", pagination_ok, "next offset and truncation conserve page progress", value.content_address),
        _finding(8, "row-addresses", row_addresses_ok, "every row address replays from its public projection", value.content_address),
        _finding(9, "result-address", query_model.address_result(value) == value.content_address, "query result address reproduces", value.content_address),
        _finding(10, "mapping-round-trip", mapping_ok, "the delivered result replays through its mapping form", value.content_address),
        _finding(11, "public-boundary", _public(value.to_dict()), "result contains only public values", value.content_address),
        _finding(12, "path-free", _public(value.to_dict()), "result contains no local filesystem markers", value.content_address),
        _finding(13, "bounded-page", value.returned <= query_model.MAX_LIMIT and value.matched <= query_model.MAX_QUERY_ITEMS, "page and match counters stay bounded", value.content_address),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit(value.content_address, value.query.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit(provisional.result_address, provisional.query_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit:
    value = _mapping(value, "archive query audit")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit.FIELDS), "archive query audit")
    checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAuditFinding.from_mapping(item) for item in _sequence(value["checks"], "query audit checks", len(CHECK_IDS)))
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit(value["result_address"], value["query_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"]))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("archive query audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address"), lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow({key: item.to_dict()[key] for key in writer.fieldnames})
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Archive Query Audit", "", f"- Result: `{value.result_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit.FIELDS), "properties": {"result_address": {"type": "string", "pattern": "^" + query_model.RESULT_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent page validation", "filter and pagination conservation", "row address replay", "bounded public projection checks", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveQueryAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "audit_query", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
