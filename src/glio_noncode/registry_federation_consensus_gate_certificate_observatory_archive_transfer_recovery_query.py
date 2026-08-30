"""Bounded inspection queries for transfer recovery receipts."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery as recovery_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = recovery_model.VERSION + "-query-v1"
BOUNDARY = recovery_model.BOUNDARY + "_query"
QUERY_PREFIX = recovery_model.RECOVERY_PREFIX + "-query"
RESULT_PREFIX = QUERY_PREFIX + "-result"
RESOURCE_NAMES = ("summary", "actions", "missing", "evidence")
DEFAULT_RESOURCES = RESOURCE_NAMES
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_OFFSET = 100000
MAX_ITEMS = recovery_model.MAX_ACTIONS + 8


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded string")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field)
    if not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64:
        raise ValidationError(f"{field} has an invalid address")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} has undeclared or missing fields")


def _public(value: Any) -> bool:
    forbidden = ("agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user", "path", "directory", "filename")
    if isinstance(value, Mapping):
        return all(not any(word in str(key).lower() for word in forbidden) and _public(item) for key, item in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(item) for item in value)
    return True


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQuery:
    """A bounded resource selection for one recovery receipt."""

    FIELDS = ("resource", "text", "offset", "limit", "content_address")

    def __init__(self, resource: str = "summary", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, content_address: str = QUERY_PREFIX + ":pending") -> None:
        if resource not in RESOURCE_NAMES:
            raise ValidationError("recovery query resource is not declared")
        self.resource = resource
        self.text = _text(text, "recovery query text", 512)
        self.offset = _count(offset, "recovery query offset", MAX_OFFSET)
        self.limit = _count(limit, "recovery query limit", MAX_LIMIT, positive=True)
        self.content_address = _address(content_address, "recovery query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "recovery query address")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("recovery query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult:
    """An addressed, paginated recovery resource result."""

    FIELDS = ("query", "rows", "total", "matched", "returned", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQuery, rows: Sequence[Mapping[str, Any]], total: int, matched: int, returned: int, next_offset: int | None, truncated: bool, content_address: str = RESULT_PREFIX + ":pending") -> None:
        if not isinstance(query, RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQuery):
            raise ValidationError("recovery query result requires a typed query")
        self.query = query
        self.rows = tuple(dict(_mapping(row, "recovery query row")) for row in rows)
        self.total = _count(total, "recovery query total", MAX_ITEMS)
        self.matched = _count(matched, "recovery query matched", MAX_ITEMS)
        self.returned = _count(returned, "recovery query returned", MAX_LIMIT)
        self.next_offset = None if next_offset is None else _count(next_offset, "recovery query next offset", MAX_OFFSET)
        if not isinstance(truncated, bool) or self.returned != len(self.rows) or self.matched > self.total or self.returned > self.matched or self.returned > self.query.limit or self.truncated_expected(next_offset) != truncated:
            raise ValidationError("recovery query result counters are not conserved")
        self.truncated = truncated
        self.content_address = _address(content_address, "recovery result address", RESULT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "recovery result address")
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("recovery query result address does not replay")

    def truncated_expected(self, next_offset: int | None) -> bool:
        return next_offset is not None

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "rows": self.rows, "total": self.total, "matched": self.matched, "returned": self.returned, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("total", "matched", "returned", "next_offset", "truncated", "content_address")}


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _records(value: recovery_model.RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery, resource: str) -> tuple[Mapping[str, Any], ...]:
    if resource == "summary":
        return (value.summary() | {"resource": resource},)
    if resource == "actions":
        return tuple(item.to_dict() | {"resource": resource} for item in value.actions)
    if resource == "missing":
        return tuple({"resource": resource, "index": item.index, "offset": item.offset, "size": item.size, "content_address": item.content_address} for item in value.actions)
    return tuple({"resource": resource, "index": item.index, "chunk_address": item.content_address, "action_address": item.action_address, "transfer_address": value.transfer_address, "archive_address": value.archive_address} for item in value.actions)


def query_recovery(value: recovery_model.RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery, *, resource: str = "summary", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult:
    recovery_model.verify_recovery(value)
    pending = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQuery(resource, text, offset, limit)
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQuery(resource, text, offset, limit, address_query(pending))
    records = _records(value, query.resource)
    if len(records) > MAX_ITEMS:
        raise ValidationError("recovery query exceeds its bounded item limit")
    filtered = tuple(record for record in records if not query.text or query.text.lower() in canonical_json(record).lower())
    page = filtered[query.offset:query.offset + query.limit]
    next_offset = query.offset + len(page) if query.offset + len(page) < query.offset + len(filtered) else None
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult(query, page, len(records), len(filtered), len(page), next_offset, next_offset is not None)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult(query, page, len(records), len(filtered), len(page), next_offset, next_offset is not None, address_result(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult:
    value = _mapping(value, "recovery query result")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult.FIELDS), "recovery query result")
    query_value = _mapping(value["query"], "recovery query")
    _strict(query_value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQuery.FIELDS), "recovery query")
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQuery(query_value["resource"], query_value["text"], query_value["offset"], query_value["limit"], query_value["content_address"])
    return verify_result(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult(query, _sequence(value["rows"], "recovery query rows", MAX_LIMIT), value["total"], value["matched"], value["returned"], value["next_offset"], value["truncated"], value["content_address"]))


def verify_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("recovery query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult) -> str:
    return canonical_json(verify_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult) -> str:
    value = verify_result(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("resource", "payload"), lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow({"resource": row.get("resource", value.query.resource), "payload": canonical_json(row)})
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult) -> str:
    value = verify_result(value)
    lines = ["# Certificate Observatory Transfer Recovery Query", "", f"- Resource: `{value.query.resource}`", f"- Returned: `{value.returned}/{value.matched}`", f"- Address: `{value.content_address}`", "", "| resource | payload |", "| --- | --- |"]
    lines.extend(f"| `{row.get('resource', value.query.resource)}` | `{canonical_json(row)}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"title": "Certificate Observatory Transfer Recovery Query", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQuery.FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCE_NAMES)}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string"}}}


def result_schema() -> dict[str, Any]:
    return {"title": "Certificate Observatory Transfer Recovery Query Result", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult.FIELDS), "properties": {"query": {"type": "object"}, "rows": {"type": "array", "items": {"type": "object"}}, "total": {"type": "integer"}, "matched": {"type": "integer"}, "returned": {"type": "integer"}, "next_offset": {"type": ["integer", "null"]}, "truncated": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": RESOURCE_NAMES, "operations": ("query", "serialize", "verify"), "limits": {"max_limit": MAX_LIMIT, "max_items": MAX_ITEMS}, "public_fields": RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryQueryResult.FIELDS}
