"""Independent audit for filtered certificate-observatory diff results."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-query-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_query_audit"
AUDIT_PREFIX = diff_model.QUERY_PREFIX + "-audit"
FINDING_PREFIX = diff_model.QUERY_PREFIX + "-audit-finding"
CHECK_IDS = ("exact-fields", "public-boundary", "diff-link", "resource-conservation", "filter-conservation", "row-conservation", "pagination-conservation", "item-ordinal-conservation", "row-addresses", "content-address", "mapping-round-trip", "deterministic-resources", "path-free")


def _text(value: Any, field: str, maximum: int = diff_model.MAX_TEXT, *, required: bool = False) -> str:
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


class RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observatory diff query audit finding ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "observatory diff query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("observatory diff query audit check ID is unsupported")
        self.passed, self.observed, self.expected, self.detail = _bool(passed, "observatory diff query audit result"), _text(observed, "observatory diff query audit observed"), _text(expected, "observatory diff query audit expected"), _text(detail, "observatory diff query audit detail", required=True)
        self.content_address = _address(content_address, "observatory diff query audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("observatory diff query audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff query audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding:
        value = _mapping(value, "observatory diff query audit finding")
        _strict(value, set(cls.FIELDS), "observatory diff query audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit:
    FIELDS = ("result_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, result_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.result_address = _address(result_address, "audited observatory diff result address", diff_model.RESULT_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding) for item in self.checks):
            raise ValidationError("observatory diff query audit checks must be typed")
        self.check_count, self.passed_count, self.failed_count = _count(check_count, "observatory diff query audit check count", len(CHECK_IDS), positive=True), _count(passed_count, "observatory diff query audit passed count", check_count), _count(failed_count, "observatory diff query audit failed count", check_count)
        self.accepted = _bool(accepted, "observatory diff query audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("observatory diff query audit counters are not conserved")
        self.content_address = _address(content_address, "observatory diff query audit address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("observatory diff query audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff query audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"result_address": self.result_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit:
        value = _mapping(value, "observatory diff query audit")
        _strict(value, set(cls.FIELDS), "observatory diff query audit")
        return cls(value["result_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_query(value: diff_model.RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit:
    value = diff_model.verify_query_result(value)
    query, rows = value.query, value.rows
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(diff_model.RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult.FIELDS), tuple(sorted(value.to_dict())), diff_model.RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult.FIELDS, "result fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "result is public and path-free"),
        _finding(3, "diff-link", query.diff_address.startswith(diff_model.DIFF_PREFIX + ":"), query.diff_address, diff_model.DIFF_PREFIX + ":address", "result links to a diff"),
        _finding(4, "resource-conservation", all(row.resource in diff_model.RESOURCES for row in rows), tuple(row.resource for row in rows), diff_model.RESOURCES, "rows use requested resources"),
        _finding(5, "filter-conservation", all((not query.observation_key or row.observation_key == query.observation_key) and (not query.action or row.action == query.action) and (query.accepted_change is None or row.accepted_change == query.accepted_change) for row in rows), "returned rows", query.to_dict(), "filters are conserved"),
        _finding(6, "row-conservation", len(rows) == value.returned_count and value.returned_count <= value.matched_count <= value.total_count, (len(rows), value.returned_count, value.matched_count, value.total_count), "returned <= matched <= total", "row counts are conserved"),
        _finding(7, "pagination-conservation", tuple(row.ordinal for row in rows) == tuple(range(query.offset + 1, query.offset + value.returned_count + 1)) and value.truncated == (value.next_offset > 0) and ((not value.truncated and value.next_offset == 0) or (value.truncated and value.next_offset > query.offset)), (query.offset, value.next_offset, value.truncated), "bounded page", "pagination is conserved"),
        _finding(8, "item-ordinal-conservation", all(1 <= row.item_ordinal <= diff_model.MAX_ITEMS for row in rows), tuple(row.item_ordinal for row in rows), diff_model.MAX_ITEMS, "row item ordinals are bounded"),
        _finding(9, "row-addresses", all(row.content_address.startswith(diff_model.ROW_PREFIX + ":") for row in rows), "row address vocabulary", diff_model.ROW_PREFIX + ":", "row addresses are addressed"),
        _finding(10, "content-address", diff_model.address_result(value) == value.content_address, value.content_address, diff_model.address_result(value), "result address replays"),
        _finding(11, "mapping-round-trip", diff_model.query_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original result", "mapping conversion is lossless"),
        _finding(12, "deterministic-resources", query.resources == tuple(item for item in diff_model.RESOURCES if item in query.resources), query.resources, diff_model.RESOURCES, "resource order is deterministic"),
        _finding(13, "path-free", _public(value.to_dict()), True, True, "result has no local paths or attribution metadata"),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit(provisional.result_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit) -> RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("observatory diff query audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in verify_audit(value).checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Diff Query Audit", "", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding.FIELDS), "properties": {field: {"type": "integer"} if field == "ordinal" else {"type": "boolean"} if field == "passed" else {"type": "string"} for field in RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding.FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit.FIELDS), "properties": {"result_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent diff query checks", "filter and pagination conservation", "row address validation", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryDiffQueryAudit", "RegistryFederationConsensusGateCertificateObservatoryDiffQueryAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
