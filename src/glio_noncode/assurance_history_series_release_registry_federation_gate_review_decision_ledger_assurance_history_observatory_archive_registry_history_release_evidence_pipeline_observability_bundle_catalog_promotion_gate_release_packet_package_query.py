"""Bounded queries over persisted catalog promotion release packages."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate as gate_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet as packet_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package as package_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = package_model.VERSION + "-query-v1"
BOUNDARY = package_model.BOUNDARY + "_query"
QUERY_PREFIX = package_model.PACKAGE_PREFIX + "-query"
RESOURCES = ("summary", "manifest", "gate", "audit", "packet", "actions", "evidence", "files")
DEFAULT_LIMIT = min(50, package_model.MAX_ARTIFACTS + packet_model.MAX_ACTIONS)
MAX_LIMIT = package_model.MAX_ARTIFACTS + packet_model.MAX_ACTIONS
MAX_QUERY_ITEMS = MAX_LIMIT + len(RESOURCES)
MAX_TEXT = 4096


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not value.strip() and maximum != 0):
        raise ValidationError(f"{field} must be a bounded string")
    return value


def _optional_text(value: Any, field: str, maximum: int = 512) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum)


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _freeze(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _public(value: Any) -> bool:
    return package_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery:
    """A bounded, path-free filter over one persisted package."""

    FIELDS = ("resource", "source", "severity", "check_id", "text", "offset", "limit")

    def __init__(self, resource: str = "summary", source: str | None = None, severity: str | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        if resource not in RESOURCES:
            raise ValidationError("observability bundle catalog promotion package query resource is unsupported")
        self.resource = resource
        self.source = _optional_text(source, "observability bundle catalog promotion package query source", 32)
        if self.source is not None and self.source not in packet_model.SOURCES:
            raise ValidationError("observability bundle catalog promotion package query source is unsupported")
        self.severity = _optional_text(severity, "observability bundle catalog promotion package query severity", 32)
        if self.severity is not None and self.severity not in gate_model.SEVERITIES:
            raise ValidationError("observability bundle catalog promotion package query severity is unsupported")
        self.check_id = _optional_text(check_id, "observability bundle catalog promotion package query check ID", 128)
        self.text = _optional_text(text, "observability bundle catalog promotion package query text", MAX_TEXT)
        self.offset = _count(offset, "observability bundle catalog promotion package query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "observability bundle catalog promotion package query limit", MAX_LIMIT, positive=True)
        if not _public(self.to_dict()):
            raise ValidationError("observability bundle catalog promotion package query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery:
        value = _mapping(value, "observability bundle catalog promotion package query")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion package query")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion package query is missing fields: {missing}")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult:
    """A deterministic bounded page over package projections."""

    FIELDS = ("package_address", "query", "total_count", "returned_count", "records", "content_address")

    def __init__(self, package_address: str, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery, total_count: int, returned_count: int, records: tuple[Mapping[str, Any], ...], content_address: str) -> None:
        self.package_address = package_model._address(package_address, "observability bundle catalog promotion package query package address", package_model.PACKAGE_PREFIX)
        if not isinstance(query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery):
            raise ValidationError("observability bundle catalog promotion package query result query must be typed")
        self.query = query
        self.total_count = _count(total_count, "observability bundle catalog promotion package query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "observability bundle catalog promotion package query returned count", MAX_QUERY_ITEMS)
        if len(records) != self.returned_count:
            raise ValidationError("observability bundle catalog promotion package query returned count does not match records")
        self.records = tuple(_freeze(_mapping(record, "observability bundle catalog promotion package query record")) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.returned_count > self.query.limit or self.query.offset > self.total_count + MAX_QUERY_ITEMS:
            raise ValidationError("observability bundle catalog promotion package query page is outside its bound")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion package query content address")
        else:
            package_model._address(self.content_address, "observability bundle catalog promotion package query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion package query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"package_address": self.package_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult:
        value = _mapping(value, "observability bundle catalog promotion package query result")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion package query result")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion package query result is missing fields: {missing}")
        records = value["records"]
        if not isinstance(records, (list, tuple)):
            raise ValidationError("observability bundle catalog promotion package query result records must be a sequence")
        return cls(value["package_address"], RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery.from_mapping(value["query"]), value["total_count"], value["returned_count"], tuple(_mapping(record, "observability bundle catalog promotion package query record") for record in records), value["content_address"])


def address_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult):
        raise ValidationError("observability bundle catalog promotion package query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery) -> bool:
    if query.source is not None and record.get("source") != query.source:
        return False
    if query.severity is not None and record.get("severity") != query.severity:
        return False
    if query.check_id is not None and record.get("check_id") != query.check_id:
        return False
    return query.text is None or query.text.casefold() in canonical_json(record).casefold()


def _records(value: package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        candidates: tuple[Mapping[str, Any], ...] = (value.summary(),)
    elif query.resource == "manifest":
        candidates = (value.manifest,)
    elif query.resource == "gate":
        candidates = (value.gate.summary(),)
    elif query.resource == "audit":
        candidates = (value.gate_audit.summary(),)
    elif query.resource == "packet":
        candidates = (value.packet.summary(),)
    elif query.resource == "actions":
        candidates = tuple(action.to_dict() for action in value.packet.actions)
    elif query.resource == "evidence":
        candidates = tuple({"source": action.source, "check_id": action.check_id, "severity": action.severity, "evidence_address": action.evidence_address, "action_address": action.content_address} for action in value.packet.actions)
    else:
        candidates = tuple(_mapping(item, "observability bundle catalog promotion package artifact") for item in value.manifest["artifacts"])
    return tuple(record for record in candidates if _matches(record, query))


def query_package(value: package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery | None = None, *, resource: str = "summary", source: str | None = None, severity: str | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult:
    if not isinstance(value, package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage):
        raise ValidationError("observability bundle catalog promotion package query requires a typed package")
    package_model.verify_package(value)
    selected = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery(resource, source, severity, check_id, text, offset, limit) if query is None else query
    if not isinstance(selected, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery):
        raise ValidationError("observability bundle catalog promotion package query requires a typed query")
    records = _records(value, selected)
    window = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult(value.content_address, selected, len(records), len(window), tuple(window), "pending:observability-bundle-catalog-promotion-package-query")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult(value.content_address, selected, provisional.total_count, provisional.returned_count, provisional.records, address_query(provisional))


def query_from_mapping(value: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult:
    return query_package(package_model.package_from_mapping(value), query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult):
        raise ValidationError("observability bundle catalog promotion package query verification requires a typed result")
    value._validate()
    if address_query(value) != value.content_address:
        raise ValidationError("observability bundle catalog promotion package query content address does not replay")
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult:
    return verify_query(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult.from_mapping(value))


def query_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult) -> str:
    value = verify_query(value)
    fields = sorted({str(key) for record in value.records for key in record}) or ["content_address"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in value.records:
        writer.writerow({field: canonical_json(record[field]) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult) -> str:
    value = verify_query(value)
    lines = ["# Assurance History Observatory Catalog Promotion Release Package Query", "", f"- Resource: `{value.query.resource}`", f"- Source filter: `{value.query.source}`", f"- Severity filter: `{value.query.severity}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- Package: `{value.package_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records:
        fields = sorted({str(key) for record in value.records for key in record})
        lines.append("| " + " | ".join(fields) + " |")
        lines.append("| " + " | ".join("---" for _ in fields) + " |")
        lines.extend("| " + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields) + " |" for record in value.records)
    else:
        lines.append("No matching records.")
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery.FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "source": {"type": ["string", "null"], "enum": [*packet_model.SOURCES, None]}, "severity": {"type": ["string", "null"], "enum": [*gate_model.SEVERITIES, None]}, "check_id": {"type": ["string", "null"]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult.FIELDS), "properties": {"package_address": {"type": "string", "pattern": "^" + package_model.PACKAGE_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "resources": RESOURCES, "sources": packet_model.SOURCES, "severities": gate_model.SEVERITIES, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS}, "features": ("persisted package summary inspection", "nested gate audit packet views", "action and evidence filtering", "manifest artifact inspection", "source severity and check filters", "deterministic pagination", "content-addressed result replay", "raw package mapping query", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY", "DEFAULT_LIMIT", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_PREFIX", "RESOURCES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult",
    "address_query", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_package", "query_result_from_mapping", "query_result_schema", "query_schema", "render_query_markdown", "verify_query",
]
