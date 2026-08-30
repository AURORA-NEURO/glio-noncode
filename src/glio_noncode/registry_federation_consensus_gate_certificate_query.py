"""Bounded projections over consensus gate release certificates."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate as certificate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = certificate_model.VERSION + "-query-v1"
BOUNDARY = certificate_model.BOUNDARY + "_query"
QUERY_PREFIX = certificate_model.CERTIFICATE_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
MAX_TEXT = certificate_model.MAX_TEXT
RESOURCES = ("summary", "checks", "failures", "evidence", "policy")
DEFAULT_RESOURCES = RESOURCES
MAX_ROWS = certificate_model.MAX_CHECKS * (certificate_model.MAX_EVIDENCE + 2)
MAX_LIMIT = MAX_ROWS


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _resources(value: Any, field: str) -> tuple[str, ...]:
    selected = tuple(_label(item, field) for item in _sequence(value, field, len(RESOURCES)))
    if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected):
        raise ValidationError(f"{field} contains unsupported resources")
    return tuple(item for item in RESOURCES if item in selected)


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


class RegistryFederationConsensusGateCertificateQuery:
    """Immutable filter and page specification."""

    FIELDS = ("query_id", "certificate_address", "resources", "check_id", "passed", "state", "decision", "offset", "limit", "content_address")

    def __init__(self, query_id: str, certificate_address: str, resources: Sequence[str], check_id: str, passed: bool | None, state: str, decision: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "certificate query ID")
        self.certificate_address = _address(certificate_address, "queried certificate address", certificate_model.CERTIFICATE_PREFIX)
        self.resources = _resources(resources, "certificate query resources")
        self.check_id = _label(check_id, "certificate query check ID", required=False)
        if self.check_id and self.check_id not in certificate_model.CHECK_IDS:
            raise ValidationError("certificate query check ID is unsupported")
        if passed is not None and not isinstance(passed, bool):
            raise ValidationError("certificate query passed filter must be boolean or null")
        self.passed = passed
        self.state = _label(state, "certificate query state", required=False)
        self.decision = _label(decision, "certificate query decision", required=False)
        if self.state and self.state not in certificate_model.CERTIFICATE_STATES:
            raise ValidationError("certificate query state is unsupported")
        if self.decision and self.decision not in certificate_model.CERTIFICATE_DECISIONS:
            raise ValidationError("certificate query decision is unsupported")
        self.offset = _count(offset, "certificate query offset", MAX_ROWS)
        self.limit = _count(limit, "certificate query limit", MAX_LIMIT, positive=True)
        self.content_address = _address(content_address, "certificate query address", QUERY_PREFIX)
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("certificate query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateQuery:
        value = _mapping(value, "certificate query")
        _strict(value, set(cls.FIELDS), "certificate query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateCertificateQuery) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateQuery):
        raise ValidationError("certificate query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateCertificateQueryRow:
    """One bounded, path-free certificate projection row."""

    FIELDS = ("ordinal", "resource", "row_id", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate query row ordinal", MAX_ROWS, positive=True)
        self.resource = _label(resource, "certificate query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("certificate query row resource is unsupported")
        self.row_id = _label(row_id, "certificate query row ID")
        self.check_id = _label(check_id, "certificate query row check ID", required=False)
        if self.check_id and self.check_id not in certificate_model.CHECK_IDS:
            raise ValidationError("certificate query row check ID is unsupported")
        self.passed = _bool(passed, "certificate query row passed flag")
        self.detail = _text(detail, "certificate query row detail", required=True)
        self.evidence_addresses = tuple(_address(item, "certificate query evidence address") for item in _sequence(evidence_addresses, "certificate query evidence addresses", certificate_model.MAX_EVIDENCE))
        if not self.evidence_addresses:
            raise ValidationError("certificate query rows require evidence")
        self.content_address = _address(content_address, "certificate query row address", ROW_PREFIX)
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("certificate query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateQueryRow:
        value = _mapping(value, "certificate query row")
        _strict(value, set(cls.FIELDS), "certificate query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusGateCertificateQueryRow) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateQueryRow):
        raise ValidationError("certificate query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateCertificateQueryResult:
    """Addressed page of certificate rows with conserved pagination."""

    FIELDS = ("query", "certificate_id", "certificate_state", "certificate_decision", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateQuery, certificate_id: str, certificate_state: str, certificate_decision: str, rows: Sequence[RegistryFederationConsensusGateCertificateQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        if not isinstance(query, RegistryFederationConsensusGateCertificateQuery):
            raise ValidationError("certificate query result query must be typed")
        self.query = query
        self.certificate_id = _label(certificate_id, "certificate query result certificate ID")
        if certificate_state not in certificate_model.CERTIFICATE_STATES or certificate_decision not in certificate_model.CERTIFICATE_DECISIONS:
            raise ValidationError("certificate query result disposition is unsupported")
        self.certificate_state, self.certificate_decision = certificate_state, certificate_decision
        self.rows = tuple(rows)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateQueryRow) for item in self.rows) or len(self.rows) > MAX_ROWS:
            raise ValidationError("certificate query rows are outside the bound")
        self.total_count = _count(total_count, "certificate query total count", MAX_ROWS)
        self.matched_count = _count(matched_count, "certificate query matched count", self.total_count)
        self.returned_count = _count(returned_count, "certificate query returned count", self.matched_count)
        self.next_offset = _count(next_offset, "certificate query next offset", MAX_ROWS)
        self.truncated = _bool(truncated, "certificate query truncated flag")
        if self.matched_count < self.returned_count or len(self.rows) != self.returned_count or tuple(item.ordinal for item in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)):
            raise ValidationError("certificate query result pagination is not conserved")
        if self.truncated != (self.next_offset > 0) or (not self.truncated and self.next_offset != 0) or (self.truncated and self.next_offset <= self.query.offset):
            raise ValidationError("certificate query result next offset is not conserved")
        self.content_address = _address(content_address, "certificate query result address", RESULT_PREFIX)
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("certificate query result address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate query result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "certificate_id": self.certificate_id, "certificate_state": self.certificate_state, "certificate_decision": self.certificate_decision, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"query", "rows"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateQueryResult:
        value = _mapping(value, "certificate query result")
        _strict(value, set(cls.FIELDS), "certificate query result")
        return cls(RegistryFederationConsensusGateCertificateQuery.from_mapping(value["query"]), value["certificate_id"], value["certificate_state"], value["certificate_decision"], tuple(RegistryFederationConsensusGateCertificateQueryRow.from_mapping(item) for item in value["rows"]), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateCertificateQueryResult) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateQueryResult):
        raise ValidationError("certificate query result address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(ordinal: int, resource: str, row_id: str, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateQueryRow:
    provisional = RegistryFederationConsensusGateCertificateQueryRow(ordinal, resource, row_id, check_id, passed, detail, evidence, ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateQueryRow(provisional.ordinal, provisional.resource, provisional.row_id, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_row(provisional))


def _all_rows(value: certificate_model.RegistryFederationConsensusGateCertificate, resources: Sequence[str]) -> tuple[RegistryFederationConsensusGateCertificateQueryRow, ...]:
    rows: list[RegistryFederationConsensusGateCertificateQueryRow] = []
    if "summary" in resources:
        rows.append(_row(len(rows) + 1, "summary", "summary", "", value.accepted, f"{value.passed_count} of {value.check_count} certificate checks passed; state {value.certificate_state}; decision {value.certificate_decision}", (value.content_address,)))
    if "checks" in resources:
        for check in value.checks:
            rows.append(_row(len(rows) + 1, "checks", check.check_id, check.check_id, check.passed, check.detail, check.evidence_addresses))
    if "failures" in resources:
        for check in value.checks:
            if not check.passed:
                rows.append(_row(len(rows) + 1, "failures", check.check_id, check.check_id, check.passed, check.detail, check.evidence_addresses))
    if "evidence" in resources:
        for ordinal, address in enumerate(value.evidence_addresses, start=1):
            rows.append(_row(len(rows) + 1, "evidence", f"evidence-{ordinal}", "", value.accepted, f"certificate evidence: {address}", (address,)))
    if "policy" in resources:
        rows.append(_row(len(rows) + 1, "policy", value.policy.policy_id, "", value.accepted, f"policy requires {value.policy.minimum_passed_count} passed checks; package required: {value.policy.require_package}", (value.policy.content_address,)))
    return tuple(rows)


def build_query(value: certificate_model.RegistryFederationConsensusGateCertificate, *, query_id: str = "consensus-certificate-query", resources: Sequence[str] = DEFAULT_RESOURCES, check_id: str = "", passed: bool | None = None, state: str = "", decision: str = "", offset: int = 0, limit: int = 100) -> RegistryFederationConsensusGateCertificateQuery:
    value = certificate_model.verify_certificate(value)
    provisional = RegistryFederationConsensusGateCertificateQuery(query_id, value.content_address, resources, check_id, passed, state, decision, offset, limit, QUERY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateQuery(provisional.query_id, provisional.certificate_address, provisional.resources, provisional.check_id, provisional.passed, provisional.state, provisional.decision, provisional.offset, provisional.limit, address_query(provisional))


def query_certificate(value: certificate_model.RegistryFederationConsensusGateCertificate, *, query_id: str = "consensus-certificate-query", resources: Sequence[str] = DEFAULT_RESOURCES, check_id: str = "", passed: bool | None = None, state: str = "", decision: str = "", offset: int = 0, limit: int = 100) -> RegistryFederationConsensusGateCertificateQueryResult:
    value = certificate_model.verify_certificate(value)
    query = build_query(value, query_id=query_id, resources=resources, check_id=check_id, passed=passed, state=state, decision=decision, offset=offset, limit=limit)
    rows = _all_rows(value, query.resources)
    if query.state and query.state != value.certificate_state or query.decision and query.decision != value.certificate_decision:
        matched = ()
    else:
        matched = tuple(item for item in rows if (not query.check_id or item.check_id == query.check_id) and (query.passed is None or item.passed == query.passed))
    page = matched[query.offset:query.offset + query.limit]
    truncated = query.offset + len(page) < len(matched)
    next_offset = query.offset + len(page) if truncated else 0
    typed_rows = tuple(_row(query.offset + ordinal, item.resource, item.row_id, item.check_id, item.passed, item.detail, item.evidence_addresses) for ordinal, item in enumerate(page, start=1))
    provisional = RegistryFederationConsensusGateCertificateQueryResult(query, value.certificate_id, value.certificate_state, value.certificate_decision, typed_rows, len(rows), len(matched), len(typed_rows), next_offset, truncated, RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateQueryResult(provisional.query, provisional.certificate_id, provisional.certificate_state, provisional.certificate_decision, provisional.rows, provisional.total_count, provisional.matched_count, provisional.returned_count, provisional.next_offset, provisional.truncated, address_result(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateQueryResult:
    return verify_query_result(RegistryFederationConsensusGateCertificateQueryResult.from_mapping(value))


def verify_query(value: RegistryFederationConsensusGateCertificateQuery) -> RegistryFederationConsensusGateCertificateQuery:
    if not isinstance(value, RegistryFederationConsensusGateCertificateQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("certificate query is not valid")
    return value


def verify_query_result(value: RegistryFederationConsensusGateCertificateQueryResult) -> RegistryFederationConsensusGateCertificateQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("certificate query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateQueryRow.FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        item = row.to_dict()
        item["evidence_addresses"] = "|".join(row.evidence_addresses)
        writer.writerow(item)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Consensus Release Certificate Query", "", f"- Certificate: `{value.certificate_id}`", f"- State: `{value.certificate_state}`", f"- Decision: `{value.certificate_decision}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Result: `{value.content_address}`", "", "| resource | row | check | passed | detail |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{row.resource}` | `{row.row_id}` | `{row.check_id}` | `{row.passed}` | {row.detail} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "certificate_address": {"type": "string", "pattern": "^" + certificate_model.CERTIFICATE_PREFIX + ":"}, "resources": {"type": "array", "items": {"type": "string"}}, "check_id": {"type": "string"}, "passed": {"type": ["boolean", "null"]}, "state": {"type": "string"}, "decision": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"type": "string"}, "row_id": {"type": "string"}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateQueryResult.FIELDS), "properties": {"query": query_schema(), "certificate_id": {"type": "string"}, "certificate_state": {"type": "string"}, "certificate_decision": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer"}, "matched_count": {"type": "integer"}, "returned_count": {"type": "integer"}, "next_offset": {"type": "integer"}, "truncated": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RESULT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "result_prefix": RESULT_PREFIX, "resources": RESOURCES, "default_resources": DEFAULT_RESOURCES, "features": ("certificate summary projection", "check and failure filters", "evidence and policy projections", "state and decision filters", "bounded deterministic pagination", "JSON CSV and Markdown exports"), "limits": {"max_rows": MAX_ROWS, "max_limit": MAX_LIMIT}, "schemas": ("query", "row", "result")}


__all__ = ["BOUNDARY", "DEFAULT_RESOURCES", "MAX_LIMIT", "MAX_ROWS", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "RegistryFederationConsensusGateCertificateQuery", "RegistryFederationConsensusGateCertificateQueryResult", "RegistryFederationConsensusGateCertificateQueryRow", "VERSION", "address_query", "address_result", "address_row", "build_query", "capabilities", "query_certificate", "query_csv", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "result_schema", "row_schema", "verify_query", "verify_query_result"]
