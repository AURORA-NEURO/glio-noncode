"""Independent assurance for federation-archive transfer queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer as transfer_model
from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "transfer-linkage", "public-boundary", "mapping-round-trip")
MAX_CHECKS = len(CHECK_IDS)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("transfer_address", "query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
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


class TransferQueryAuditCheck:
    """One independently addressed transfer-query assertion."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "query audit ordinal", MAX_CHECKS, positive=True)
        if check_id not in CHECK_IDS or CHECK_IDS[self.ordinal - 1] != check_id:
            raise ValidationError("query audit check identity or order is invalid")
        self.check_id = check_id
        if not isinstance(passed, bool):
            raise ValidationError("query audit result must be boolean")
        self.passed = passed
        self.detail = _text(detail, "query audit detail", 4096)
        self.evidence_addresses = tuple(_address(item, "query audit evidence address") for item in _sequence(evidence_addresses, "query audit evidence", 16))
        if not self.evidence_addresses:
            raise ValidationError("query audit check needs evidence")
        self.content_address = _address(content_address, "query audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not transfer_model._public(self.to_dict()):
            raise ValidationError("query audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TransferQueryAuditCheck:
        value = _mapping(value, "transfer query audit check")
        _strict(value, set(cls.FIELDS), "transfer query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


class TransferQueryAudit:
    """The fixed-size receiving-side audit of a transfer query."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, transfer_address: str, query_address: str, checks: Sequence[TransferQueryAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.transfer_address = _address(transfer_address, "query audit transfer address", transfer_model.TRANSFER_PREFIX)
        self.query_address = _address(query_address, "query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, TransferQueryAuditCheck) else TransferQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "query audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "query audit failed count", MAX_CHECKS)
        if not isinstance(accepted, bool):
            raise ValidationError("query audit acceptance must be boolean")
        self.accepted = accepted
        self.content_address = _address(content_address, "query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("query audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("query audit counters do not replay")
        if any(self.transfer_address not in item.evidence_addresses for item in self.checks):
            raise ValidationError("query audit evidence does not retain the transfer address")
        if not transfer_model._public(self.to_dict()):
            raise ValidationError("query audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("query audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"transfer_address": self.transfer_address, "query_address": self.query_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TransferQueryAudit:
        value = _mapping(value, "transfer query audit")
        _strict(value, set(cls.FIELDS), "transfer query audit")
        return cls(value["transfer_address"], value["query_address"], tuple(TransferQueryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "query audit checks", MAX_CHECKS)), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_check(value: TransferQueryAuditCheck) -> str:
    if not isinstance(value, TransferQueryAuditCheck):
        raise ValidationError("query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: TransferQueryAudit) -> str:
    if not isinstance(value, TransferQueryAudit):
        raise ValidationError("query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> TransferQueryAuditCheck:
    provisional = TransferQueryAuditCheck(ordinal, check_id, bool(passed), detail, evidence, "pending:query-audit-check")
    return TransferQueryAuditCheck(ordinal, check_id, bool(passed), detail, evidence, address_check(provisional))


def audit_query(query: query_model.TransferQuery, transfer: transfer_model.ArchiveTransfer) -> TransferQueryAudit:
    if not isinstance(query, query_model.TransferQuery) or not isinstance(transfer, transfer_model.ArchiveTransfer):
        raise ValidationError("transfer query audit requires typed query and transfer")
    transfer_model.verify_transfer(transfer)
    expected = query_model.query_transfer(transfer, resources=query.resources, received_indices=query.received_indices, index=query.index_filter, chunk_offset=query.offset_filter, size=query.size_filter, chunk_address=query.chunk_address_filter, received=query.received_filter, text=query.text_filter, offset=query.offset, limit=query.limit)
    rows_equal = expected.to_dict()["rows"] == query.to_dict()["rows"]
    row_addresses = tuple(item.content_address for item in query.rows)
    evidence = (transfer.content_address, query.content_address, *row_addresses[:8])
    resource_semantics = all(item.resource in query.resources and (item.resource not in {"received", "missing"} or item.received is (item.resource == "received")) for item in query.rows)
    checks = (
        ("version", query_model.VERSION == transfer_model.VERSION + "-query-v1", "query version derives from the transfer contract"),
        ("boundary", query_model.BOUNDARY == transfer_model.BOUNDARY + "_query", "query boundary derives from the transfer contract"),
        ("resource-order", query.resources == tuple(sorted(query.resources, key=query_model.RESOURCES.index)), "query resources retain canonical order"),
        ("filter-replay", expected.total_count == query.total_count and expected.matched_count == query.matched_count and expected.received_indices == query.received_indices, "query filters and receiver partition replay"),
        ("count-replay", expected.returned_count == query.returned_count and query.returned_count == len(query.rows) and expected.truncated == query.truncated, "query pagination counts replay"),
        ("row-order", tuple(item.ordinal for item in query.rows) == tuple(range(1, query.returned_count + 1)), "query rows retain page order"),
        ("row-addresses", all(query_model.address_row(item) == item.content_address for item in query.rows) and len(set(row_addresses)) == len(row_addresses), "query row addresses replay uniquely"),
        ("row-membership", rows_equal, "query rows equal the independently recomputed page"),
        ("resource-semantics", resource_semantics, "query rows retain resource and received-state semantics"),
        ("transfer-linkage", query.transfer_address == transfer.content_address, "query links to the exact transfer"),
        ("public-boundary", transfer_model._public(query.to_dict()), "query is value-free and public"),
        ("mapping-round-trip", query_model.query_from_mapping(query.to_dict()).to_dict() == query.to_dict(), "query mapping round-trips"),
    )
    findings = tuple(_check(index, check_id, passed, detail, evidence) for index, (check_id, passed, detail) in enumerate(checks, 1))
    body = {"transfer_address": transfer.content_address, "query_address": query.content_address, "checks": findings, "check_count": MAX_CHECKS, "passed_count": sum(item.passed for item in findings), "failed_count": sum(not item.passed for item in findings), "accepted": all(item.passed for item in findings)}
    provisional = TransferQueryAudit(**body, content_address="pending:query-audit")
    return TransferQueryAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> TransferQueryAudit:
    return TransferQueryAudit.from_mapping(value)


def audit_json(value: TransferQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: TransferQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: TransferQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Runtime Registry Federation Archive Transfer Query Audit", "", f"- Transfer: `{value.transfer_address}`", f"- Query: `{value.query_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime registry federation archive transfer query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime registry federation archive transfer query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"transfer_address": {"type": "string", "pattern": "^" + transfer_model.TRANSFER_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_count": MAX_CHECKS, "checks": list(CHECK_IDS), "features": ["independent filter replay", "row address replay", "transfer linkage", "receiver-partition replay", "canonical JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "TransferQueryAudit", "TransferQueryAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
