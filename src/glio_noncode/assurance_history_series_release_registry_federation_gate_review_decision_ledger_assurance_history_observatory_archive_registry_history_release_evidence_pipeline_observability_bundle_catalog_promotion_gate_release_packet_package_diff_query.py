"""Bounded queries over persisted promotion-package evolution diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-query-v1"
BOUNDARY = diff_model.BOUNDARY + "_query"
QUERY_PREFIX = diff_model.DIFF_PREFIX + "-query"
RESOURCES = ("summary", "items", "added-actions", "removed-actions", "changed-actions", "fields", "decisions", "evidence")
DEFAULT_LIMIT = min(50, diff_model.MAX_ITEMS)
MAX_LIMIT = diff_model.MAX_ITEMS
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
    return diff_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery:
    """A bounded filter over package-diff projections."""

    FIELDS = ("resource", "action_id", "field", "text", "offset", "limit")

    def __init__(self, resource: str = "summary", action_id: str | None = None, field: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        if resource not in RESOURCES:
            raise ValidationError("observability bundle catalog promotion package diff query resource is unsupported")
        self.resource = resource
        self.action_id = _optional_text(action_id, "observability bundle catalog promotion package diff query action ID", 128)
        self.field = _optional_text(field, "observability bundle catalog promotion package diff query field", 128)
        self.text = _optional_text(text, "observability bundle catalog promotion package diff query text", MAX_TEXT)
        self.offset = _count(offset, "observability bundle catalog promotion package diff query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "observability bundle catalog promotion package diff query limit", MAX_LIMIT, positive=True)
        if not _public(self.to_dict()):
            raise ValidationError("observability bundle catalog promotion package diff query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery:
        value = _mapping(value, "observability bundle catalog promotion package diff query")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion package diff query")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion package diff query is missing fields: {missing}")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult:
    """A deterministic bounded page over package-diff records."""

    FIELDS = ("diff_address", "query", "total_count", "returned_count", "records", "content_address")

    def __init__(self, diff_address: str, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery, total_count: int, returned_count: int, records: tuple[Mapping[str, Any], ...], content_address: str) -> None:
        self.diff_address = diff_model._address(diff_address, "observability bundle catalog promotion package diff query diff address", diff_model.DIFF_PREFIX)
        if not isinstance(query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery):
            raise ValidationError("observability bundle catalog promotion package diff query result query must be typed")
        self.query = query
        self.total_count = _count(total_count, "observability bundle catalog promotion package diff query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "observability bundle catalog promotion package diff query returned count", MAX_QUERY_ITEMS)
        if len(records) != self.returned_count:
            raise ValidationError("observability bundle catalog promotion package diff query returned count does not match records")
        self.records = tuple(_freeze(_mapping(record, "observability bundle catalog promotion package diff query record")) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.returned_count > self.query.limit or self.query.offset > self.total_count + MAX_QUERY_ITEMS:
            raise ValidationError("observability bundle catalog promotion package diff query page is outside its bound")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion package diff query content address")
        else:
            diff_model._address(self.content_address, "observability bundle catalog promotion package diff query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion package diff query is not public or addressed")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult:
        value = _mapping(value, "observability bundle catalog promotion package diff query result")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion package diff query result")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion package diff query result is missing fields: {missing}")
        records = value["records"]
        if not isinstance(records, (list, tuple)):
            raise ValidationError("observability bundle catalog promotion package diff query result records must be a sequence")
        return cls(value["diff_address"], RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery.from_mapping(value["query"]), value["total_count"], value["returned_count"], tuple(_mapping(record, "observability bundle catalog promotion package diff query record") for record in records), value["content_address"])


def address_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult):
        raise ValidationError("observability bundle catalog promotion package diff query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery) -> bool:
    if query.action_id is not None and record.get("action_id") != query.action_id and record.get("check_id") != query.action_id:
        return False
    if query.field is not None and record.get("field") != query.field:
        return False
    return query.text is None or query.text.casefold() in canonical_json(record).casefold()


def _records(value: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        candidates: tuple[Mapping[str, Any], ...] = (value.summary(),)
    elif query.resource == "items":
        candidates = tuple(item.to_dict() for item in value.items)
    elif query.resource == "fields":
        candidates = tuple({"field": field, "ordinal": ordinal + 1, "item_address": value.items[ordinal].content_address} for ordinal, field in enumerate(value.changed_fields))
    elif query.resource == "decisions":
        candidates = ({"before": value.left_decision, "after": value.right_decision, "left_decision": value.left_decision, "right_decision": value.right_decision, "left_packet_address": value.left_packet_address, "right_packet_address": value.right_packet_address},)
    elif query.resource == "evidence":
        candidates = tuple({"field": item.field, "item_address": item.content_address} for item in value.items)
    elif query.resource == "added-actions":
        candidates = tuple({"action_id": action_id, "change": "added"} for action_id in value.action_added_ids)
    elif query.resource == "removed-actions":
        candidates = tuple({"action_id": action_id, "change": "removed"} for action_id in value.action_removed_ids)
    else:
        candidates = tuple({"action_id": action_id, "change": "changed"} for action_id in value.action_changed_ids)
    return tuple(record for record in candidates if _matches(record, query))


def query_diff(value: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery | None = None, *, resource: str = "summary", action_id: str | None = None, field: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult:
    if not isinstance(value, diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff):
        raise ValidationError("observability bundle catalog promotion package diff query requires a typed diff")
    diff_model.verify_diff(value)
    selected = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery(resource, action_id, field, text, offset, limit) if query is None else query
    if not isinstance(selected, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery):
        raise ValidationError("observability bundle catalog promotion package diff query requires a typed query")
    records = _records(value, selected)
    window = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult(value.content_address, selected, len(records), len(window), tuple(window), "pending:observability-bundle-catalog-promotion-package-diff-query")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult(value.content_address, selected, provisional.total_count, provisional.returned_count, provisional.records, address_query(provisional))


def query_from_mapping(value: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult:
    return query_diff(diff_model.diff_from_mapping(value), query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult):
        raise ValidationError("observability bundle catalog promotion package diff query verification requires a typed result")
    value._validate()
    if address_query(value) != value.content_address:
        raise ValidationError("observability bundle catalog promotion package diff query content address does not replay")
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult:
    return verify_query(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult.from_mapping(value))


def query_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult) -> str:
    value = verify_query(value)
    fields = sorted({str(key) for record in value.records for key in record}) or ["content_address"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in value.records:
        writer.writerow({field: canonical_json(record[field]) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult) -> str:
    value = verify_query(value)
    lines = ["# Assurance History Observatory Catalog Promotion Release Package Diff Query", "", f"- Resource: `{value.query.resource}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- Diff: `{value.diff_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records:
        fields = sorted({str(key) for record in value.records for key in record})
        lines.append("| " + " | ".join(fields) + " |")
        lines.append("| " + " | ".join("---" for _ in fields) + " |")
        lines.extend("| " + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields) + " |" for record in value.records)
    else:
        lines.append("No matching records.")
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery.FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "action_id": {"type": ["string", "null"], "maxLength": 128}, "field": {"type": ["string", "null"], "maxLength": 128}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult.FIELDS), "properties": {"diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "resources": RESOURCES, "compare_fields": diff_model.COMPARE_FIELDS, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS}, "features": ("persisted package diff summary inspection", "field and action transition views", "added removed and changed action filters", "decision transition inspection", "deterministic pagination", "content-addressed result replay", "raw diff mapping query", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY", "DEFAULT_LIMIT", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_PREFIX", "RESOURCES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQuery", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffQueryResult",
    "address_query", "capabilities", "query_csv", "query_diff", "query_from_mapping", "query_json", "query_result_from_mapping", "query_result_schema", "query_schema", "render_query_markdown", "verify_query",
]
