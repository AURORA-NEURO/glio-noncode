"""Bounded queries over quorum-safe federation consensus receipts."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus as consensus_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = consensus_model.VERSION + "-query-v1"
BOUNDARY = consensus_model.BOUNDARY + "_query"
QUERY_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus-query"
ROW_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus-query-row"
RESULT_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus-query-result"
RESOURCES = ("summary", "packages", "candidates", "actions", "evidence", "selected", "unresolved", "all")
DEFAULT_RESOURCES = ("summary", "packages", "candidates", "actions")
MAX_ROWS = consensus_model.MAX_PACKAGES * (consensus_model.MAX_CANDIDATES + 2) + consensus_model.MAX_ACTIONS + consensus_model.MAX_PEERS * 4
MAX_TEXT = consensus_model.MAX_TEXT
CHECK_IDS = ("exact-fields", "public-boundary", "resource-conservation", "row-conservation", "filter-conservation", "pagination-conservation", "candidate-conservation", "action-conservation", "row-addresses", "query-address", "result-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _required_text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    value = _text(value, field, maximum)
    if not value:
        raise ValidationError(f"{field} must not be empty")
    return value


def _label(value: Any, field: str) -> str:
    value = _required_text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _optional_label(value: Any, field: str) -> str:
    return "" if value == "" else _label(value, field)


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _required_text(value, field, 512)
    if "/" in value or "\\" in value or '"' in value or prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must not contain duplicate addresses")
    return tuple(sorted(values))


def _labels(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must not contain duplicate labels")
    return tuple(sorted(values))


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
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusQuery:
    """A replayable resource and filter selection."""

    FIELDS = ("query_id", "consensus_address", "resources", "package_id", "resolution", "severity", "kind", "offset", "limit", "content_address")

    def __init__(self, query_id: str, consensus_address: str, resources: Sequence[str], package_id: str, resolution: str, severity: str, kind: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "consensus query ID")
        self.consensus_address = _address(consensus_address, "consensus query receipt address", consensus_model.CONSENSUS_PREFIX)
        self.resources = tuple(dict.fromkeys(_label(resource, "consensus query resource") for resource in _sequence(resources, "consensus query resources", len(RESOURCES))))
        if not self.resources or any(resource not in RESOURCES for resource in self.resources):
            raise ValidationError("consensus query resource is unsupported")
        self.package_id = _optional_label(package_id, "consensus query package ID")
        self.resolution = "" if resolution == "" else resolution
        if self.resolution and self.resolution not in consensus_model.RESOLUTIONS:
            raise ValidationError("consensus query resolution is unsupported")
        self.severity = "" if severity == "" else severity
        if self.severity and self.severity not in consensus_model.SEVERITIES:
            raise ValidationError("consensus query severity is unsupported")
        self.kind = "" if kind == "" else kind
        if self.kind and self.kind not in consensus_model.ACTION_KINDS:
            raise ValidationError("consensus query action kind is unsupported")
        self.offset = _count(offset, "consensus query offset", MAX_ROWS)
        self.limit = _count(limit, "consensus query limit", max(100, MAX_ROWS), positive=True)
        self.content_address = _address(content_address, "consensus query content address", QUERY_PREFIX)
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("consensus query content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusQuery:
        value = _mapping(value, "consensus query")
        _strict(value, set(cls.FIELDS), "consensus query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusQuery) -> str:
    if not isinstance(value, RegistryFederationConsensusQuery):
        raise ValidationError("consensus query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusQueryRow:
    """A typed public row derived from package, candidate, action, or evidence data."""

    FIELDS = ("ordinal", "resource", "row_id", "package_id", "address", "peer_ids", "resolution", "severity", "kind", "status", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, package_id: str, address: str, peer_ids: Sequence[str], resolution: str, severity: str, kind: str, status: str, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "consensus query row ordinal", MAX_ROWS, positive=True)
        self.resource = _label(resource, "consensus query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("consensus query row resource is unsupported")
        self.row_id = _label(row_id, "consensus query row ID")
        self.package_id = "" if package_id == "" else _label(package_id, "consensus query row package ID")
        self.address = "" if address == "" else _address(address, "consensus query row address")
        self.peer_ids = _labels(peer_ids, "consensus query row peer IDs", consensus_model.MAX_PEERS)
        self.resolution = "" if resolution == "" else resolution
        if self.resolution and self.resolution not in consensus_model.RESOLUTIONS:
            raise ValidationError("consensus query row resolution is unsupported")
        self.severity = "" if severity == "" else severity
        if self.severity and self.severity not in consensus_model.SEVERITIES:
            raise ValidationError("consensus query row severity is unsupported")
        self.kind = "" if kind == "" else kind
        if self.kind and self.kind not in consensus_model.ACTION_KINDS:
            raise ValidationError("consensus query row kind is unsupported")
        self.status = _required_text(status, "consensus query row status", 64)
        self.detail = _required_text(detail, "consensus query row detail")
        self.evidence_addresses = _addresses(evidence_addresses, "consensus query row evidence", consensus_model.MAX_PEERS * (consensus_model.MAX_CANDIDATES + 2))
        self.content_address = _address(content_address, "consensus query row content address", ROW_PREFIX)
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("consensus query row content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusQueryRow:
        value = _mapping(value, "consensus query row")
        _strict(value, set(cls.FIELDS), "consensus query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusQueryRow) -> str:
    if not isinstance(value, RegistryFederationConsensusQueryRow):
        raise ValidationError("consensus query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusQueryResult:
    """A deterministic page over a consensus projection."""

    FIELDS = ("query", "consensus_id", "consensus_state", "consensus_decision", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusQuery, consensus_id: str, consensus_state: str, consensus_decision: str, rows: Sequence[RegistryFederationConsensusQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        if not isinstance(query, RegistryFederationConsensusQuery):
            raise ValidationError("consensus result query must be typed")
        self.query = query
        self.consensus_id = _label(consensus_id, "consensus result ID")
        if consensus_state not in consensus_model.STATES or consensus_decision not in consensus_model.DECISIONS:
            raise ValidationError("consensus result disposition is unsupported")
        self.consensus_state = consensus_state
        self.consensus_decision = consensus_decision
        self.rows = tuple(rows)
        if len(self.rows) > query.limit or any(not isinstance(row, RegistryFederationConsensusQueryRow) for row in self.rows):
            raise ValidationError("consensus result rows exceed requested page")
        self.total_count = _count(total_count, "consensus result total count", MAX_ROWS)
        self.matched_count = _count(matched_count, "consensus result matched count", self.total_count)
        self.returned_count = _count(returned_count, "consensus result returned count", query.limit)
        self.next_offset = _count(next_offset, "consensus result next offset", MAX_ROWS)
        self.truncated = _bool(truncated, "consensus result truncated flag")
        if self.returned_count != len(self.rows) or self.matched_count < self.returned_count or self.next_offset != (query.offset + self.returned_count if self.truncated else 0) or self.truncated != (self.next_offset > 0) or tuple(row.ordinal for row in self.rows) != tuple(range(1, len(self.rows) + 1)):
            raise ValidationError("consensus result pagination is not conserved")
        self.content_address = _address(content_address, "consensus result content address", RESULT_PREFIX)
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("consensus result content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "consensus_id": self.consensus_id, "consensus_state": self.consensus_state, "consensus_decision": self.consensus_decision, "rows": tuple(row.to_dict() for row in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"query", "rows"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusQueryResult:
        value = _mapping(value, "consensus query result")
        _strict(value, set(cls.FIELDS), "consensus query result")
        rows = tuple(value["rows"]) if isinstance(value["rows"], list) else value["rows"]
        return cls(RegistryFederationConsensusQuery.from_mapping(value["query"]), value["consensus_id"], value["consensus_state"], value["consensus_decision"], tuple(RegistryFederationConsensusQueryRow.from_mapping(item) for item in rows), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusQueryResult) -> str:
    if not isinstance(value, RegistryFederationConsensusQueryResult):
        raise ValidationError("consensus result address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def build_query(value: consensus_model.RegistryFederationConsensus, *, query_id: str = "consensus-query", resources: Sequence[str] = DEFAULT_RESOURCES, package_id: str = "", resolution: str = "", severity: str = "", kind: str = "", offset: int = 0, limit: int = 100) -> RegistryFederationConsensusQuery:
    value = consensus_model.verify_consensus(value)
    provisional = RegistryFederationConsensusQuery(query_id, value.content_address, resources, package_id, resolution, severity, kind, offset, limit, QUERY_PREFIX + ":pending")
    return RegistryFederationConsensusQuery(provisional.query_id, provisional.consensus_address, provisional.resources, provisional.package_id, provisional.resolution, provisional.severity, provisional.kind, provisional.offset, provisional.limit, address_query(provisional))


def _row(ordinal: int, resource: str, row_id: str, *, package_id: str = "", address: str = "", peer_ids: Sequence[str] = (), resolution: str = "", severity: str = "", kind: str = "", status: str, detail: str, evidence_addresses: Sequence[str] = ()) -> RegistryFederationConsensusQueryRow:
    provisional = RegistryFederationConsensusQueryRow(ordinal, resource, row_id, package_id, address, peer_ids, resolution, severity, kind, status, detail, evidence_addresses, ROW_PREFIX + ":pending")
    return RegistryFederationConsensusQueryRow(provisional.ordinal, provisional.resource, provisional.row_id, provisional.package_id, provisional.address, provisional.peer_ids, provisional.resolution, provisional.severity, provisional.kind, provisional.status, provisional.detail, provisional.evidence_addresses, address_row(provisional))


def _projection(value: consensus_model.RegistryFederationConsensus) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = [{"resource": "summary", "row_id": "consensus-summary", "status": "accepted" if value.accepted else "held", "detail": f"{value.selected_count} selected of {value.package_count} packages; {value.action_count} actions", "evidence_addresses": (value.content_address,)}]
    for package in value.packages:
        package_row = {"resource": "packages", "row_id": f"package-{package.package_id}", "package_id": package.package_id, "address": package.selected_address, "resolution": package.resolution, "severity": package.severity, "status": package.resolution, "detail": package.detail, "evidence_addresses": (package.content_address, *package.evidence_addresses)}
        rows.append(package_row)
        rows.append(package_row | {"resource": package.resolution})
        for candidate in package.candidates:
            rows.append({"resource": "candidates", "row_id": f"candidate-{package.package_id}-{candidate.ordinal}", "package_id": package.package_id, "address": candidate.address, "peer_ids": candidate.peer_ids, "resolution": package.resolution, "status": "selected" if candidate.selected else "dissenting", "detail": f"{candidate.support_count} of {candidate.expected_peer_count} peers support candidate", "evidence_addresses": (candidate.content_address,)})
    for action in value.actions:
        rows.append({"resource": "actions", "row_id": action.action_id, "package_id": action.package_id, "kind": action.kind, "severity": action.severity, "status": "required", "detail": action.detail, "peer_ids": action.peer_ids, "evidence_addresses": (action.content_address, *action.evidence_addresses)})
    evidence = sorted({address for row in rows for address in row["evidence_addresses"]})
    rows.extend({"resource": "evidence", "row_id": f"evidence-{index:04d}", "address": address, "status": "linked", "detail": address, "evidence_addresses": (address,)} for index, address in enumerate(evidence, start=1))
    return tuple(rows)


def _matches(row: Mapping[str, Any], query: RegistryFederationConsensusQuery) -> bool:
    resources = set(query.resources)
    if "all" not in resources and row["resource"] not in resources:
        return False
    if query.package_id and row.get("package_id", "") != query.package_id:
        return False
    if query.resolution and row.get("resolution", "") != query.resolution:
        return False
    if query.severity and row.get("severity", "") != query.severity:
        return False
    return not query.kind or row.get("kind", "") == query.kind


def query_consensus(value: consensus_model.RegistryFederationConsensus, query: RegistryFederationConsensusQuery | None = None, **query_kwargs: Any) -> RegistryFederationConsensusQueryResult:
    value = consensus_model.verify_consensus(value)
    query = build_query(value, **query_kwargs) if query is None else RegistryFederationConsensusQuery.from_mapping(query.to_dict())
    if query.consensus_address != value.content_address:
        raise ValidationError("consensus query address does not match receipt")
    source = _projection(value)
    matched = tuple(row for row in source if _matches(row, query))
    page = matched[query.offset:query.offset + query.limit]
    rows = tuple(_row(index, row["resource"], row["row_id"], package_id=row.get("package_id", ""), address=row.get("address", ""), peer_ids=row.get("peer_ids", ()), resolution=row.get("resolution", ""), severity=row.get("severity", ""), kind=row.get("kind", ""), status=row["status"], detail=row["detail"], evidence_addresses=row["evidence_addresses"]) for index, row in enumerate(page, start=1))
    truncated = query.offset + len(page) < len(matched)
    next_offset = query.offset + len(page) if truncated else 0
    provisional = RegistryFederationConsensusQueryResult(query, value.consensus_id, value.state, value.decision, rows, len(source), len(matched), len(rows), next_offset, truncated, RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusQueryResult(provisional.query, provisional.consensus_id, provisional.consensus_state, provisional.consensus_decision, provisional.rows, provisional.total_count, provisional.matched_count, provisional.returned_count, provisional.next_offset, provisional.truncated, address_result(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusQueryResult:
    return verify_query_result(RegistryFederationConsensusQueryResult.from_mapping(value))


def verify_query(value: RegistryFederationConsensusQuery) -> RegistryFederationConsensusQuery:
    if not isinstance(value, RegistryFederationConsensusQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("consensus query is not valid")
    return value


def verify_query_result(value: RegistryFederationConsensusQueryResult) -> RegistryFederationConsensusQueryResult:
    if not isinstance(value, RegistryFederationConsensusQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("consensus query result is not valid")
    verify_query(value.query)
    return value


def query_json(value: RegistryFederationConsensusQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    fields = ("ordinal", "resource", "row_id", "package_id", "address", "peer_ids", "resolution", "severity", "kind", "status", "detail", "evidence_addresses", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        record = row.to_dict()
        record["peer_ids"] = "|".join(row.peer_ids)
        record["evidence_addresses"] = "|".join(row.evidence_addresses)
        writer.writerow(record)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Package Registry Federation Consensus Query", "", f"- Consensus: `{value.consensus_id}`", f"- State: `{value.consensus_state}`", f"- Decision: `{value.consensus_decision}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Result address: `{value.content_address}`", "", "| resource | row | package | resolution | severity | kind | status |", "| --- | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{row.resource}` | `{row.row_id}` | `{row.package_id}` | `{row.resolution}` | `{row.severity}` | `{row.kind}` | `{row.status}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "consensus_address": {"type": "string", "pattern": "^" + consensus_model.CONSENSUS_PREFIX + ":"}, "resources": {"type": "array", "items": {"type": "string"}}, "package_id": {"type": "string"}, "resolution": {"type": "string"}, "severity": {"type": "string"}, "kind": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"type": "string"}, "row_id": {"type": "string"}, "package_id": {"type": "string"}, "address": {"type": "string"}, "peer_ids": {"type": "array"}, "resolution": {"type": "string"}, "severity": {"type": "string"}, "kind": {"type": "string"}, "status": {"type": "string"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusQueryResult.FIELDS), "properties": {"query": query_schema(), "consensus_id": {"type": "string"}, "consensus_state": {"type": "string"}, "consensus_decision": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer"}, "matched_count": {"type": "integer"}, "returned_count": {"type": "integer"}, "next_offset": {"type": "integer"}, "truncated": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RESULT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "result_prefix": RESULT_PREFIX, "resources": RESOURCES, "default_resources": DEFAULT_RESOURCES, "check_ids": CHECK_IDS, "limits": {"max_rows": MAX_ROWS, "max_text": MAX_TEXT}, "features": ("package resolution filters", "candidate and dissent projections", "action-kind and severity filters", "evidence projections", "deterministic pagination", "JSON CSV and Markdown exports"), "schemas": ("query", "row", "result")}


__all__ = ["BOUNDARY", "CHECK_IDS", "DEFAULT_RESOURCES", "MAX_ROWS", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "RegistryFederationConsensusQuery", "RegistryFederationConsensusQueryResult", "RegistryFederationConsensusQueryRow", "VERSION", "address_query", "address_result", "address_row", "build_query", "capabilities", "query_consensus", "query_csv", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "result_schema", "row_schema", "verify_query", "verify_query_result"]
