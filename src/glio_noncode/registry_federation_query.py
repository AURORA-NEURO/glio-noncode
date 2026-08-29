"""Deterministic, bounded queries over package-registry federation evidence.

The query layer is a projection rather than a second source of truth. Every
row is derived from an addressed federation and carries identity and evidence
information for reproducible CLI, HTTP, and Actions responses.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-query-v1"
BOUNDARY = federation_model.BOUNDARY + "_query"
QUERY_PREFIX = federation_model.FEDERATION_PREFIX + "-query"
RESULT_PREFIX = federation_model.FEDERATION_PREFIX + "-query-result"
ROW_PREFIX = federation_model.FEDERATION_PREFIX + "-query-row"
DEFAULT_QUERY_ID = "federation-observatory"
DEFAULT_RESOURCES = ("summary", "peers", "packages", "conflicts", "actions")
RESOURCES = federation_model.RESOURCES + ("all",)
MAX_RESOURCES = len(RESOURCES)
MAX_ROWS = federation_model.MAX_PACKAGES * federation_model.MAX_PEERS + federation_model.MAX_CONFLICTS + federation_model.MAX_ACTIONS + 64
MAX_TEXT = federation_model.MAX_TEXT
CHECK_IDS = ("exact-fields", "public-boundary", "resource-conservation", "row-conservation", "filter-conservation", "pagination-conservation", "row-addresses", "query-address", "result-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _optional_label(value: Any, field: str) -> str:
    return "" if value == "" else _label(value, field)


def _optional_text(value: Any, field: str) -> str:
    return "" if value == "" else _text(value, field)


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512)
    if not value.startswith(prefix + ":"):
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
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _labels(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    labels = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if len(set(labels)) != len(labels):
        raise ValidationError(f"{field} must not contain duplicates")
    return tuple(sorted(labels))


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    addresses = tuple(_text(item, field, 512) for item in _sequence(value, field, maximum))
    if len(set(addresses)) != len(addresses) or any("\\" in item or "/" in item for item in addresses):
        raise ValidationError(f"{field} must contain unique path-free addresses")
    return tuple(sorted(addresses))


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "\"" not in value and "\\" not in value and "/" not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery:
    """A replayable public query request over one federation address."""

    FIELDS = ("query_id", "federation_address", "resources", "peer_id", "package_id", "kind", "severity", "text", "offset", "limit", "content_address")

    def __init__(self, query_id: str, federation_address: str, resources: Sequence[str], peer_id: str, package_id: str, kind: str, severity: str, text: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "query ID")
        self.federation_address = _address(federation_address, "federation address", federation_model.FEDERATION_PREFIX)
        self.resources = _labels(resources, "query resources", MAX_RESOURCES)
        if not self.resources:
            raise ValidationError("query resources must not be empty")
        if "all" in self.resources and len(self.resources) != 1:
            raise ValidationError("all query resource cannot be combined with named resources")
        self.peer_id = _optional_label(peer_id, "query peer ID")
        self.package_id = _optional_label(package_id, "query package ID")
        self.kind = "" if kind == "" else _label(kind, "query kind")
        self.severity = "" if severity == "" else _label(severity, "query severity")
        if self.kind and self.kind not in {"peer", "package", "conflict", "action", "evidence", "summary", *federation_model.CONFLICT_KINDS, "quorum"}:
            raise ValidationError("query kind is unsupported")
        if self.severity and self.severity not in federation_model.SEVERITIES:
            raise ValidationError("query severity is unsupported")
        self.text = _optional_text(text, "query text")
        self.offset = _count(offset, "query offset", MAX_ROWS)
        self.limit = _count(limit, "query limit", MAX_ROWS, positive=True)
        self.content_address = _address(content_address, "query content address", QUERY_PREFIX)
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("query content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "federation_address": self.federation_address, "resources": self.resources, "peer_id": self.peer_id, "package_id": self.package_id, "kind": self.kind, "severity": self.severity, "text": self.text, "offset": self.offset, "limit": self.limit, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery:
        value = _mapping(value, "federation query")
        _strict(value, set(cls.FIELDS), "federation query")
        resources = tuple(value["resources"]) if isinstance(value["resources"], list) else value["resources"]
        return cls(value["query_id"], value["federation_address"], resources, value["peer_id"], value["package_id"], value["kind"], value["severity"], value["text"], value["offset"], value["limit"], value["content_address"])


def address_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery):
        raise ValidationError("query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow:
    """One deterministic projection row returned by a federation query."""

    FIELDS = ("ordinal", "resource", "row_id", "peer_id", "package_id", "kind", "severity", "state", "decision", "status", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, peer_id: str, package_id: str, kind: str, severity: str, state: str, decision: str, status: str, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "query row ordinal", MAX_ROWS, positive=True)
        self.resource = _label(resource, "query row resource")
        if self.resource not in RESOURCES or self.resource == "all":
            raise ValidationError("query row resource is unsupported")
        self.row_id = _label(row_id, "query row ID")
        self.peer_id = _optional_label(peer_id, "query row peer ID")
        self.package_id = _optional_label(package_id, "query row package ID")
        self.kind = _label(kind, "query row kind")
        self.severity = "" if severity == "" else _label(severity, "query row severity")
        self.state = "" if state == "" else _label(state, "query row state")
        self.decision = "" if decision == "" else _label(decision, "query row decision")
        self.status = _label(status, "query row status")
        self.detail = _text(detail, "query row detail")
        self.evidence_addresses = _addresses(evidence_addresses, "query row evidence addresses", 16)
        self.content_address = _address(content_address, "query row content address", ROW_PREFIX)
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("query row content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "resource": self.resource, "row_id": self.row_id, "peer_id": self.peer_id, "package_id": self.package_id, "kind": self.kind, "severity": self.severity, "state": self.state, "decision": self.decision, "status": self.status, "detail": self.detail, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow:
        value = _mapping(value, "federation query row")
        _strict(value, set(cls.FIELDS), "federation query row")
        evidence = tuple(value["evidence_addresses"]) if isinstance(value["evidence_addresses"], list) else value["evidence_addresses"]
        return cls(value["ordinal"], value["resource"], value["row_id"], value["peer_id"], value["package_id"], value["kind"], value["severity"], value["state"], value["decision"], value["status"], value["detail"], evidence, value["content_address"])


def address_row(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow):
        raise ValidationError("query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult:
    """A paginated, replayable query result envelope."""

    FIELDS = ("query", "federation_id", "federation_state", "federation_decision", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery, federation_id: str, federation_state: str, federation_decision: str, rows: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        if not isinstance(query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery):
            raise ValidationError("query result query must be typed")
        self.query = query
        self.federation_id = _label(federation_id, "result federation ID")
        self.federation_state = _label(federation_state, "result federation state")
        self.federation_decision = _label(federation_decision, "result federation decision")
        self.rows = tuple(rows)
        if len(self.rows) > query.limit or any(not isinstance(row, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow) for row in self.rows):
            raise ValidationError("query result rows exceed the requested page")
        self.total_count = _count(total_count, "result total count", MAX_ROWS)
        self.matched_count = _count(matched_count, "result matched count", self.total_count)
        self.returned_count = _count(returned_count, "result returned count", query.limit)
        self.next_offset = _count(next_offset, "result next offset", MAX_ROWS)
        self.truncated = _bool(truncated, "result truncated")
        if self.returned_count != len(self.rows) or self.matched_count < self.returned_count or self.next_offset != (query.offset + self.returned_count if self.truncated else 0):
            raise ValidationError("query pagination counters are not conserved")
        if self.truncated != (self.next_offset > 0):
            raise ValidationError("query truncation flag is not conserved")
        if tuple(row.ordinal for row in self.rows) != tuple(range(1, len(self.rows) + 1)):
            raise ValidationError("query result row ordinals are not canonical")
        self.content_address = _address(content_address, "query result content address", RESULT_PREFIX)
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("query result content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("query result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "federation_id": self.federation_id, "federation_state": self.federation_state, "federation_decision": self.federation_decision, "rows": tuple(row.to_dict() for row in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"query", "rows"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult:
        value = _mapping(value, "federation query result")
        _strict(value, set(cls.FIELDS), "federation query result")
        rows = tuple(value["rows"]) if isinstance(value["rows"], list) else value["rows"]
        return cls(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery.from_mapping(value["query"]), value["federation_id"], value["federation_state"], value["federation_decision"], tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow.from_mapping(item) for item in rows), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult):
        raise ValidationError("query result address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def build_query(federation: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = DEFAULT_RESOURCES, peer_id: str = "", package_id: str = "", kind: str = "", severity: str = "", text: str = "", offset: int = 0, limit: int = 100) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery:
    federation = federation_model.verify_federation(federation)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery(query_id, federation.content_address, resources, peer_id, package_id, kind, severity, text, offset, limit, QUERY_PREFIX + ":pending")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery(provisional.query_id, provisional.federation_address, provisional.resources, provisional.peer_id, provisional.package_id, provisional.kind, provisional.severity, provisional.text, provisional.offset, provisional.limit, address_query(provisional))


def _row(ordinal: int, resource: str, row_id: str, *, peer_id: str = "", package_id: str = "", kind: str, severity: str = "", state: str = "", decision: str = "", status: str, detail: str, evidence_addresses: Sequence[str] = ()) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow:
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow(ordinal, resource, row_id, peer_id, package_id, kind, severity, state, decision, status, detail, evidence_addresses, ROW_PREFIX + ":pending")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow(provisional.ordinal, provisional.resource, provisional.row_id, provisional.peer_id, provisional.package_id, provisional.kind, provisional.severity, provisional.state, provisional.decision, provisional.status, provisional.detail, provisional.evidence_addresses, address_row(provisional))


def _projection(value: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = [{"resource": "summary", "row_id": "federation-summary", "kind": "summary", "state": value.state, "decision": value.decision, "status": "accepted" if value.accepted else "held", "detail": f"{value.peer_count} peers, {value.package_count} packages, {value.conflict_count} conflicts, {value.action_count} actions", "evidence_addresses": (value.content_address,)}]
    for peer in value.peers:
        peer_row = {"resource": "peers", "row_id": f"peer-{peer.peer_id}", "peer_id": peer.peer_id, "kind": "peer", "state": peer.peer_state, "status": peer.audit_state, "detail": f"{peer.entry_count} registry entries; {peer.file_count} files", "evidence_addresses": (peer.content_address, peer.registry_address)}
        rows.append(peer_row)
        rows.append(peer_row | {"resource": "healthy" if peer.peer_state == "healthy" else "degraded"})
        for package_id, package_address in zip(peer.package_ids, peer.package_addresses, strict=True):
            rows.append({"resource": "packages", "row_id": f"package-{peer.peer_id}-{package_id}", "peer_id": peer.peer_id, "package_id": package_id, "kind": "package", "state": peer.peer_state, "status": "observed", "detail": f"observed at peer {peer.peer_id}", "evidence_addresses": (package_address, peer.content_address)})
    for conflict in value.reconciliation.conflicts:
        conflict_row = {"resource": "conflicts", "row_id": f"conflict-{conflict.package_id}", "package_id": conflict.package_id, "kind": conflict.kind, "severity": conflict.severity, "state": value.state, "decision": value.decision, "status": "open", "detail": conflict.detail, "evidence_addresses": (conflict.content_address, *conflict.addresses)}
        rows.append(conflict_row)
        rows.append(conflict_row | {"resource": conflict.kind})
    for action in value.actions:
        rows.append({"resource": "actions", "row_id": action.action_id, "package_id": action.package_id, "kind": action.kind, "severity": action.severity, "state": value.state, "decision": value.decision, "status": "required", "detail": action.detail, "evidence_addresses": (action.content_address, *action.evidence_addresses)})
    rows.extend({"resource": "evidence", "row_id": f"evidence-{index:04d}", "kind": "evidence", "status": "linked", "detail": address, "evidence_addresses": (address,)} for index, address in enumerate(sorted({address for row in rows for address in row["evidence_addresses"]}), start=1))
    return tuple(rows)


def _matches(row: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery) -> bool:
    resources = set(query.resources)
    if "all" not in resources and row["resource"] not in resources:
        return False
    if query.peer_id and row.get("peer_id", "") != query.peer_id:
        return False
    if query.package_id and row.get("package_id", "") != query.package_id:
        return False
    if query.kind and row.get("kind", "") != query.kind:
        return False
    if query.severity and row.get("severity", "") != query.severity:
        return False
    return not query.text or query.text.lower() in (row.get("detail", "") + " " + row.get("row_id", "")).lower()


def query_federation(value: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery | None = None, **query_kwargs: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult:
    value = federation_model.verify_federation(value)
    query = build_query(value, **query_kwargs) if query is None else RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery.from_mapping(query.to_dict())
    if query.federation_address != value.content_address:
        raise ValidationError("query federation address does not match the supplied federation")
    source = _projection(value)
    matched = tuple(row for row in source if _matches(row, query))
    page = matched[query.offset:query.offset + query.limit]
    typed_rows = tuple(_row(index, row["resource"], row["row_id"], peer_id=row.get("peer_id", ""), package_id=row.get("package_id", ""), kind=row["kind"], severity=row.get("severity", ""), state=row.get("state", ""), decision=row.get("decision", ""), status=row["status"], detail=row["detail"], evidence_addresses=row["evidence_addresses"]) for index, row in enumerate(page, start=1))
    truncated = query.offset + len(page) < len(matched)
    next_offset = query.offset + len(page) if truncated else 0
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult(query, value.federation_id, value.state, value.decision, typed_rows, len(source), len(matched), len(typed_rows), next_offset, truncated, RESULT_PREFIX + ":pending")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult(provisional.query, provisional.federation_id, provisional.federation_state, provisional.federation_decision, provisional.rows, provisional.total_count, provisional.matched_count, provisional.returned_count, provisional.next_offset, provisional.truncated, address_result(provisional))


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult:
    return verify_query_result(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult.from_mapping(value))


def verify_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("federation query is not valid")
    return value


def verify_query_result(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("federation query result is not valid")
    verify_query(value.query)
    return value


def query_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "resource", "row_id", "peer_id", "package_id", "kind", "severity", "state", "decision", "status", "detail", "evidence_addresses", "content_address"), lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        record = row.to_dict()
        record["evidence_addresses"] = "|".join(row.evidence_addresses)
        writer.writerow(record)
    return stream.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Package Registry Federation Query", "", f"- Federation: `{value.federation_id}`", f"- State: `{value.federation_state}`", f"- Decision: `{value.federation_decision}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Result address: `{value.content_address}`", "", "| ordinal | resource | row | peer | package | kind | severity | status |", "| ---: | --- | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.row_id}` | `{row.peer_id}` | `{row.package_id}` | `{row.kind}` | `{row.severity}` | `{row.status}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "federation_address": {"type": "string", "pattern": "^" + federation_model.FEDERATION_PREFIX + ":"}, "resources": {"type": "array", "items": {"type": "string"}}, "peer_id": {"type": "string"}, "package_id": {"type": "string"}, "kind": {"type": "string"}, "severity": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"type": "string"}, "row_id": {"type": "string"}, "peer_id": {"type": "string"}, "package_id": {"type": "string"}, "kind": {"type": "string"}, "severity": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "status": {"type": "string"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult.FIELDS), "properties": {"query": query_schema(), "federation_id": {"type": "string"}, "federation_state": {"type": "string"}, "federation_decision": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RESULT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "result_prefix": RESULT_PREFIX, "row_prefix": ROW_PREFIX, "resources": RESOURCES, "default_resources": DEFAULT_RESOURCES, "check_ids": CHECK_IDS, "limits": {"max_rows": MAX_ROWS, "max_text": MAX_TEXT}, "features": ("bounded resource projections", "peer and package filters", "conflict severity filters", "deterministic pagination", "address-linked evidence rows", "JSON CSV and Markdown exports"), "schemas": ("query", "row", "result")}


__all__ = ["BOUNDARY", "CHECK_IDS", "DEFAULT_QUERY_ID", "DEFAULT_RESOURCES", "MAX_ROWS", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "VERSION", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQuery", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryRow", "address_query", "address_result", "address_row", "build_query", "capabilities", "query_csv", "query_federation", "query_json", "query_result_from_mapping", "query_schema", "render_query_markdown", "result_schema", "row_schema", "verify_query", "verify_query_result"]
