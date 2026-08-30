"""Independent audit for archive-registry query pages."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.RESULT_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
CHECK_IDS = ("query-address", "registry-link", "resource-vocabulary", "row-ordinals", "filter-match", "result-counters", "page-boundary", "truncation", "row-addresses", "evidence", "public-boundary", "mapping-round-trip", "bounded-page", "registry-replay")


def _text(value: Any, field: str, maximum: int = 2048, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
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
    return registry_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "query audit finding ordinal", len(CHECK_IDS))
        if self.ordinal == 0 or check_id not in CHECK_IDS:
            raise ValidationError("query audit finding check ID is undeclared")
        self.check_id = check_id
        self.passed = _bool(passed, "query audit finding state")
        self.observed = _text(observed, "query audit observed value", 1024)
        self.expected = _text(expected, "query audit expected value", 1024)
        self.detail = _text(detail, "query audit finding detail", 2048)
        self.evidence_address = _address(evidence_address, "query audit evidence address")
        self.content_address = _address(content_address, "query audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("query audit finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding":
        value = _mapping(value, "query audit finding")
        _strict(value, set(cls.FIELDS), "query audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding):
        raise ValidationError("query audit finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit:
    FIELDS = ("query_address", "result_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, query_address: str, result_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "query audit query address", query_model.QUERY_PREFIX)
        self.result_address = _address(result_address, "query audit result address", query_model.RESULT_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding.from_mapping(item) for item in _sequence(checks, "query audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "query audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "query audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "query audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "query audit acceptance")
        self.content_address = _address(content_address, "query audit address", AUDIT_PREFIX)
        if self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("query audit checks are not canonical")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("query audit counters are not conserved")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("query audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("query audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "result_address": self.result_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("query_address", "result_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit":
        value = _mapping(value, "query audit")
        _strict(value, set(cls.FIELDS), "query audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding.from_mapping(item) for item in _sequence(value["checks"], "query audit checks", len(CHECK_IDS)))
        return cls(value["query_address"], value["result_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit):
        raise ValidationError("query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str, evidence: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding:
    observed_text = str(observed)
    expected_text = str(expected)
    if len(observed_text) > 1024:
        observed_text = observed_text[:1021] + "..."
    if len(expected_text) > 1024:
        expected_text = expected_text[:1021] + "..."
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding(ordinal, check_id, passed, observed_text, expected_text, detail, evidence, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding(ordinal, check_id, passed, provisional.observed, provisional.expected, detail, evidence, address_finding(provisional))


def _filter_match(row: query_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow, query: query_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery) -> bool:
    if query.package_id and row.package_id != query.package_id:
        return False
    if query.archive_id and row.archive_id != query.archive_id:
        return False
    if query.accepted is not None and row.accepted != query.accepted:
        return False
    if query.text:
        haystack = " ".join((row.row_id, row.entry_id, row.archive_id, row.package_id, row.archive_address, row.package_address)).lower()
        return query.text.lower() in haystack
    return True


def audit_query(value: query_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult, registry: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry | None = None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit:
    value = query_model.verify_query_result(value)
    query = query_model.verify_query(value.query)
    rows = value.rows
    registry_match = registry is None or registry_model.verify_registry(registry).content_address == query.registry_address
    expected_rows = rows if registry is None else query_model.query_registry(registry, query_id=query.query_id, resources=query.resources, package_id=query.package_id, archive_id=query.archive_id, accepted=query.accepted, text=query.text, offset=query.offset, limit=query.limit).rows
    checks = (
        _finding(1, "query-address", query_model.address_query(query) == query.content_address, query.content_address, query_model.address_query(query), "query address reproduces", query.content_address),
        _finding(2, "registry-link", registry_match, query.registry_address, "known registry address or matching registry", "query links to the requested registry", query.registry_address),
        _finding(3, "resource-vocabulary", all(item in query_model.RESOURCES for item in query.resources), query.resources, query_model.RESOURCES, "query resources are declared", query.content_address),
        _finding(4, "row-ordinals", tuple(item.ordinal for item in rows) == tuple(range(query.offset + 1, query.offset + len(rows) + 1)), tuple(item.ordinal for item in rows), "page ordinal range", "returned row ordinals are contiguous", value.content_address),
        _finding(5, "filter-match", all(_filter_match(item, query) for item in rows), True, True, "every returned row satisfies filters", value.content_address),
        _finding(6, "result-counters", value.returned_count == len(rows) and value.returned_count <= value.matched_count <= value.total_count, value.summary(), "conserved result counts", "result counts are conserved", value.content_address),
        _finding(7, "page-boundary", value.next_offset == query.offset + value.returned_count, value.next_offset, query.offset + value.returned_count, "next offset follows returned page", value.content_address),
        _finding(8, "truncation", value.truncated == (value.next_offset < query.offset + value.matched_count), value.truncated, value.next_offset < query.offset + value.matched_count, "truncation flag follows remaining rows", value.content_address),
        _finding(9, "row-addresses", all(query_model.address_row(item) == item.content_address for item in rows), True, True, "every row address replays", value.content_address),
        _finding(10, "evidence", all(item.evidence_addresses for item in rows), True, True, "every row retains evidence links", value.content_address),
        _finding(11, "public-boundary", _public(value.to_dict()), True, True, "query output is public", value.content_address),
        _finding(12, "mapping-round-trip", query_model.query_from_mapping(value.to_dict()).to_dict() == value.to_dict(), True, True, "query result mapping reloads exactly", value.content_address),
        _finding(13, "bounded-page", len(rows) <= query.limit <= query_model.MAX_LIMIT, len(rows), query.limit, "page is within query limits", value.content_address),
        _finding(14, "registry-replay", registry is None or tuple(item.to_dict() for item in expected_rows) == tuple(item.to_dict() for item in rows), registry_match, True, "page replays against the supplied registry", value.content_address),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit(query.content_address, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit(provisional.query_address, provisional.result_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("query audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    fields = ("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow({field: item.to_dict()[field] for field in fields})
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Archive Registry Query Audit", "", f"- Query: `{value.query_address}`", f"- Result: `{value.result_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit.FIELDS), "properties": {"query_address": {"type": "string"}, "result_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS), "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("query address replay", "filter and page validation", "row evidence validation", "registry-backed replay", "public-boundary checks", "addressable findings", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "FINDING_PREFIX",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAudit",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryAuditFinding",
    "VERSION",
    "address_audit",
    "address_finding",
    "audit_csv",
    "audit_from_mapping",
    "audit_json",
    "audit_query",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
