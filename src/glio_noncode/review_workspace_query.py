"""Bounded indexing and query projections for the review workspace.

The review workspace is useful as a complete graph, but an operational client
usually needs a smaller question: which evidence is contradictory, which
edges have weak context fit, which source is represented across the graph, or
which review items are highest priority?  This module builds a deterministic
public index over the already-sanitized review report and answers those
questions without reopening dossier payloads or introducing a ranking score.

Every query is bounded, explicitly typed, content addressed, and stable under
repeat execution.  Facets describe the selected rows; they are not a hidden
model or a replacement for human adjudication.  An invalid persisted run still
returns an inspectable, empty result with its accepted flag false.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace import ReviewWorkspaceConfig, ReviewWorkspaceReport, build_persisted_review_workspace
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash, jsonable


REVIEW_WORKSPACE_QUERY_VERSION = "review-workspace-query-v1"
REVIEW_WORKSPACE_QUERY_SCHEMA_VERSION = "review-workspace-query-schema-v1"
REVIEW_WORKSPACE_QUERY_DEFAULT_LIMIT = 50
REVIEW_WORKSPACE_QUERY_MAX_LIMIT = 500
REVIEW_WORKSPACE_QUERY_MAX_TEXT = 256
REVIEW_WORKSPACE_QUERY_MAX_VALUES = 50
REVIEW_WORKSPACE_QUERY_MAX_FACET_VALUES = 5_000
REVIEW_WORKSPACE_QUERY_COLLECTIONS = (
    "hypotheses",
    "edges",
    "evidence",
    "alternatives",
    "deltas",
    "provenance",
    "review_queue",
)
REVIEW_WORKSPACE_QUERY_ALL_COLLECTIONS = "all"

_IDENTIFIER_FIELDS = {
    "hypotheses": "hypothesis_id",
    "edges": "edge_id",
    "evidence": "evidence_id",
    "alternatives": "alternative_id",
    "deltas": "delta_id",
    "provenance": "provenance_id",
    "review_queue": "item_id",
}
_COLLECTION_ORDER = {name: index for index, name in enumerate(REVIEW_WORKSPACE_QUERY_COLLECTIONS)}


def _values(value: Any, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    raw = value if isinstance(value, (list, tuple, set)) else (value,)
    selected: list[str] = []
    for item in raw:
        normalized = str(item).strip()
        if normalized and normalized not in selected:
            selected.append(normalized)
    if len(selected) > REVIEW_WORKSPACE_QUERY_MAX_VALUES:
        raise ValidationError(f"{field} has too many values")
    return tuple(sorted(selected, key=lambda item: (item.casefold(), item)))


def _optional_text(value: Any, field: str, *, maximum: int = REVIEW_WORKSPACE_QUERY_MAX_TEXT) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > maximum:
        raise ValidationError(f"{field} exceeds the {maximum}-character limit")
    return text


def _integer(value: Any, field: str, *, minimum: int, maximum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        bound = f"{minimum}..{maximum}" if maximum is not None else f">={minimum}"
        raise ValidationError(f"{field} must be {bound}")
    return result


def _canonical_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): jsonable(item) for key, item in value.items()}


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceQuery:
    """Validated filters for one deterministic review-workspace query."""

    collection: str = REVIEW_WORKSPACE_QUERY_ALL_COLLECTIONS
    item_id: str | None = None
    text: str | None = None
    states: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    context_key: str | None = None
    item_type: str | None = None
    dimension: str | None = None
    priority: int | None = None
    offset: int = 0
    limit: int | None = REVIEW_WORKSPACE_QUERY_DEFAULT_LIMIT

    def __post_init__(self) -> None:
        collection = str(self.collection).strip().casefold() or REVIEW_WORKSPACE_QUERY_ALL_COLLECTIONS
        if collection not in (*REVIEW_WORKSPACE_QUERY_COLLECTIONS, REVIEW_WORKSPACE_QUERY_ALL_COLLECTIONS):
            raise ValidationError(f"collection must be one of: {', '.join(REVIEW_WORKSPACE_QUERY_COLLECTIONS)}, all")
        object.__setattr__(self, "collection", collection)
        object.__setattr__(self, "item_id", _optional_text(self.item_id, "item_id"))
        object.__setattr__(self, "text", _optional_text(self.text, "text"))
        object.__setattr__(self, "states", _values(self.states, "states"))
        object.__setattr__(self, "source_ids", _values(self.source_ids, "source_ids"))
        object.__setattr__(self, "context_key", _optional_text(self.context_key, "context_key"))
        object.__setattr__(self, "item_type", _optional_text(self.item_type, "item_type"))
        object.__setattr__(self, "dimension", _optional_text(self.dimension, "dimension"))
        if self.priority is not None:
            object.__setattr__(
                self,
                "priority",
                _integer(self.priority, "priority", minimum=0, maximum=3),
            )
        object.__setattr__(self, "offset", _integer(self.offset, "offset", minimum=0))
        if self.limit is not None:
            object.__setattr__(
                self,
                "limit",
                _integer(
                    self.limit,
                    "limit",
                    minimum=1,
                    maximum=REVIEW_WORKSPACE_QUERY_MAX_LIMIT,
                ),
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "ReviewWorkspaceQuery":
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise ValidationError("review workspace query must be an object")
        allowed = {
            "collection", "item_id", "text", "states", "source_ids", "context_key", "item_type",
            "dimension", "priority", "offset", "limit",
        }
        unknown = sorted(str(key) for key in value if str(key) not in allowed)
        if unknown:
            raise ValidationError(f"unknown review workspace query fields: {', '.join(unknown)}")
        return cls(**{key: value[key] for key in allowed if key in value})

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _collection_records(report: ReviewWorkspaceReport) -> tuple[tuple[str, dict[str, Any]], ...]:
    records: list[tuple[str, dict[str, Any]]] = []
    body = report.to_dict()
    for collection in REVIEW_WORKSPACE_QUERY_COLLECTIONS:
        values = body.get(collection, ())
        if not isinstance(values, list):
            raise ValidationError(f"review workspace collection {collection} is not a list")
        identifier = _IDENTIFIER_FIELDS[collection]
        for raw in values:
            record = _canonical_mapping(raw, f"{collection} record")
            if not str(record.get(identifier, "")).strip():
                raise ValidationError(f"{collection} record has no {identifier}")
            records.append((collection, record))
    return tuple(
        sorted(
            records,
            key=lambda item: (_COLLECTION_ORDER[item[0]], str(item[1][_IDENTIFIER_FIELDS[item[0]]])),
        )
    )


def _record_values(record: Mapping[str, Any], *keys: str) -> tuple[str, ...]:
    result: list[str] = []
    for key in keys:
        value = record.get(key)
        raw = value if isinstance(value, (list, tuple, set)) else (value,)
        for item in raw:
            if item is None:
                continue
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
    return tuple(sorted(result, key=lambda item: (item.casefold(), item)))


def _state_values(collection: str, record: Mapping[str, Any]) -> tuple[str, ...]:
    if collection == "hypotheses":
        return _record_values(record, "status")
    if collection == "edges":
        return _record_values(record, "support_level")
    if collection == "evidence":
        return _record_values(record, "state")
    if collection == "alternatives":
        return _record_values(record, "state")
    if collection == "deltas":
        return _record_values(record, "direction")
    if collection == "provenance":
        return _record_values(record, "states")
    return _record_values(record, "state")


def _source_values(collection: str, record: Mapping[str, Any]) -> tuple[str, ...]:
    return _record_values(record, "source_id", "source_ids")


def _context_values(collection: str, record: Mapping[str, Any]) -> tuple[str, ...]:
    return _record_values(record, "context_key", "context_keys")


def _dimension_values(collection: str, record: Mapping[str, Any]) -> tuple[str, ...]:
    return _record_values(record, "dimension")


def _item_type_values(collection: str, record: Mapping[str, Any]) -> tuple[str, ...]:
    return _record_values(record, "item_type")


def _priority(collection: str, record: Mapping[str, Any]) -> int | None:
    if collection != "review_queue" or record.get("priority") is None:
        return None
    try:
        return int(record["priority"])
    except (TypeError, ValueError):
        return None


def _record_id(collection: str, record: Mapping[str, Any]) -> str:
    return str(record[_IDENTIFIER_FIELDS[collection]])


def _search_blob(record: Mapping[str, Any]) -> str:
    return canonical_json(record).casefold()


def _matches(collection: str, record: Mapping[str, Any], query: ReviewWorkspaceQuery) -> bool:
    if query.collection != REVIEW_WORKSPACE_QUERY_ALL_COLLECTIONS and collection != query.collection:
        return False
    if query.item_id is not None and _record_id(collection, record) != query.item_id:
        return False
    if query.text is not None and query.text.casefold() not in _search_blob(record):
        return False
    states = _state_values(collection, record)
    if query.states and not set(query.states).intersection(states):
        return False
    sources = _source_values(collection, record)
    if query.source_ids and not set(query.source_ids).intersection(sources):
        return False
    contexts = _context_values(collection, record)
    if query.context_key is not None and query.context_key not in contexts:
        return False
    item_types = _item_type_values(collection, record)
    if query.item_type is not None and query.item_type not in item_types:
        return False
    dimensions = _dimension_values(collection, record)
    if query.dimension is not None and query.dimension not in dimensions:
        return False
    if query.priority is not None and _priority(collection, record) != query.priority:
        return False
    return True


def _facet_counts(records: Iterable[tuple[str, Mapping[str, Any]]]) -> dict[str, dict[str, int]]:
    facets: dict[str, Counter[str]] = {
        "collections": Counter(),
        "states": Counter(),
        "sources": Counter(),
        "contexts": Counter(),
        "dimensions": Counter(),
        "item_types": Counter(),
        "priorities": Counter(),
    }
    for collection, record in records:
        facets["collections"][collection] += 1
        facets["states"].update(f"{collection}:{value}" for value in _state_values(collection, record))
        facets["sources"].update(_source_values(collection, record))
        facets["contexts"].update(_context_values(collection, record))
        facets["dimensions"].update(_dimension_values(collection, record))
        facets["item_types"].update(_item_type_values(collection, record))
        priority = _priority(collection, record)
        if priority is not None:
            facets["priorities"][str(priority)] += 1
    result = {
        facet: dict(sorted(values.items(), key=lambda item: (item[0].casefold(), item[0])))
        for facet, values in facets.items()
    }
    for facet, values in result.items():
        if len(values) > REVIEW_WORKSPACE_QUERY_MAX_FACET_VALUES:
            raise ValidationError(f"{facet} facet exceeds the configured ceiling")
    return result


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceIndex:
    """Reusable public facets for one review report."""

    workspace_id: str
    report_address: str
    record_count: int
    collection_counts: Mapping[str, int]
    facets: Mapping[str, Mapping[str, int]]
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_review_workspace_index(report: ReviewWorkspaceReport) -> ReviewWorkspaceIndex:
    """Build a deterministic index without copying private dossier payloads."""

    if not isinstance(report, ReviewWorkspaceReport):
        raise ValidationError("review workspace index requires a typed report")
    public_body = report.to_dict()
    warnings: list[str] = []
    boundary_valid = not contains_private_key(public_body)
    if not boundary_valid:
        warnings.append("review workspace index rejected a forbidden public key")
    if not report.accepted:
        warnings.append("review report was not accepted; index collections were withheld")
    if report.accepted and boundary_valid:
        try:
            records = _collection_records(report)
        except ValidationError as exc:
            records = ()
            warnings.append(str(exc))
    else:
        records = ()
    collection_counts = {
        collection: sum(item[0] == collection for item in records)
        for collection in REVIEW_WORKSPACE_QUERY_COLLECTIONS
    }
    body = {
        "workspace_id": report.workspace_id,
        "report_address": report.content_address,
        "record_count": len(records),
        "collection_counts": collection_counts,
        "facets": _facet_counts(records),
        "accepted": report.accepted and boundary_valid and not warnings,
        "warnings": tuple(dict.fromkeys(warnings)),
    }
    return ReviewWorkspaceIndex(
        **body,
        content_address=content_hash(body, prefix="review-workspace-index"),
    )


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceQueryRow:
    """One public row returned by a review workspace query."""

    collection: str
    item_id: str
    states: tuple[str, ...]
    priority: int | None
    source_ids: tuple[str, ...]
    context_keys: tuple[str, ...]
    dimensions: tuple[str, ...]
    item_types: tuple[str, ...]
    record: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _query_row(collection: str, record: Mapping[str, Any]) -> ReviewWorkspaceQueryRow:
    body = {
        "collection": collection,
        "item_id": _record_id(collection, record),
        "states": _state_values(collection, record),
        "priority": _priority(collection, record),
        "source_ids": _source_values(collection, record),
        "context_keys": _context_values(collection, record),
        "dimensions": _dimension_values(collection, record),
        "item_types": _item_type_values(collection, record),
        "record": dict(record),
    }
    return ReviewWorkspaceQueryRow(
        **body,
        content_address=content_hash(body, prefix="review-workspace-query-row"),
    )


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceQueryResult:
    """Bounded query page plus full-match counts and facets."""

    workspace_id: str
    report_address: str
    query: ReviewWorkspaceQuery
    rows: tuple[ReviewWorkspaceQueryRow, ...]
    total_count: int
    offset: int
    limit: int | None
    has_more: bool
    facets: Mapping[str, Mapping[str, int]]
    index_address: str
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_version": REVIEW_WORKSPACE_QUERY_VERSION,
            "workspace_id": self.workspace_id,
            "report_address": self.report_address,
            "query": self.query.to_dict(),
            "rows": [item.to_dict() for item in self.rows],
            "total_count": self.total_count,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.has_more,
            "facets": jsonable(self.facets),
            "index_address": self.index_address,
            "accepted": self.accepted,
            "warnings": list(self.warnings),
            "content_address": self.content_address,
        }


def query_review_workspace(
    report: ReviewWorkspaceReport,
    query: ReviewWorkspaceQuery | Mapping[str, Any] | None = None,
    *,
    index: ReviewWorkspaceIndex | None = None,
) -> ReviewWorkspaceQueryResult:
    """Filter and paginate one report while preserving complete-match facets."""

    if not isinstance(report, ReviewWorkspaceReport):
        raise ValidationError("review workspace query requires a typed report")
    selected_query = query if isinstance(query, ReviewWorkspaceQuery) else ReviewWorkspaceQuery.from_mapping(query)
    selected_index = index or build_review_workspace_index(report)
    if selected_index.workspace_id != report.workspace_id or selected_index.report_address != report.content_address:
        raise ValidationError("review workspace query index does not match the report")
    public_body = report.to_dict()
    records = (
        _collection_records(report)
        if report.accepted and not contains_private_key(public_body)
        else ()
    )
    matched = tuple(item for item in records if _matches(item[0], item[1], selected_query))
    if selected_query.limit is None:
        page = matched[selected_query.offset:]
    else:
        page = matched[selected_query.offset : selected_query.offset + selected_query.limit]
    has_more = (
        False
        if selected_query.limit is None
        else selected_query.offset + len(page) < len(matched)
    )
    warnings = list(selected_index.warnings)
    if not report.accepted:
        warnings.append("review report was not accepted; query rows are inspectable but not publishable")
    public_boundary_valid = not contains_private_key({"rows": [item[1] for item in page], "facets": _facet_counts(matched)})
    accepted = report.accepted and selected_index.accepted and public_boundary_valid
    body = {
        "workspace_id": report.workspace_id,
        "report_address": report.content_address,
        "query": selected_query.to_dict(),
        "rows": tuple(_query_row(collection, record).to_dict() for collection, record in page),
        "total_count": len(matched),
        "offset": selected_query.offset,
        "limit": selected_query.limit,
        "has_more": has_more,
        "facets": _facet_counts(matched),
        "index_address": selected_index.content_address,
        "accepted": accepted,
        "warnings": tuple(dict.fromkeys(warnings)),
    }
    return ReviewWorkspaceQueryResult(
        workspace_id=report.workspace_id,
        report_address=report.content_address,
        query=selected_query,
        rows=tuple(_query_row(collection, record) for collection, record in page),
        total_count=len(matched),
        offset=selected_query.offset,
        limit=selected_query.limit,
        has_more=has_more,
        facets=_facet_counts(matched),
        index_address=selected_index.content_address,
        accepted=accepted,
        warnings=tuple(dict.fromkeys(warnings)),
        content_address=content_hash(body, prefix="review-workspace-query"),
    )


def build_review_workspace_query_closure(
    report: ReviewWorkspaceReport,
    *,
    index: ReviewWorkspaceIndex | None = None,
) -> ReviewWorkspaceQueryResult:
    """Return every bounded public row plus complete facets for offline use."""

    return query_review_workspace(
        report,
        ReviewWorkspaceQuery(limit=None),
        index=index,
    )


def build_persisted_review_workspace_index(
    runtime: CaseRuntime,
    run_id: str,
    *,
    baseline_run_id: str | None = None,
    config: ReviewWorkspaceConfig | None = None,
) -> ReviewWorkspaceIndex:
    report = build_persisted_review_workspace(
        runtime,
        run_id,
        baseline_run_id=baseline_run_id,
        config=config,
    )
    return build_review_workspace_index(report)


def build_persisted_review_workspace_query(
    runtime: CaseRuntime,
    run_id: str,
    query: ReviewWorkspaceQuery | Mapping[str, Any] | None = None,
    *,
    baseline_run_id: str | None = None,
    config: ReviewWorkspaceConfig | None = None,
) -> ReviewWorkspaceQueryResult:
    report = build_persisted_review_workspace(
        runtime,
        run_id,
        baseline_run_id=baseline_run_id,
        config=config,
    )
    return query_review_workspace(report, query)


def review_workspace_query_schema() -> dict[str, Any]:
    """Return the machine-readable query and facet contract."""

    return {
        "version": REVIEW_WORKSPACE_QUERY_SCHEMA_VERSION,
        "query_version": REVIEW_WORKSPACE_QUERY_VERSION,
        "collections": list(REVIEW_WORKSPACE_QUERY_COLLECTIONS),
        "filters": {
            "collection": {"type": "string", "default": "all"},
            "item_id": {"type": "string", "exact": True},
            "text": {"type": "string", "max_length": REVIEW_WORKSPACE_QUERY_MAX_TEXT},
            "states": {"type": "array", "max_items": REVIEW_WORKSPACE_QUERY_MAX_VALUES},
            "source_ids": {"type": "array", "max_items": REVIEW_WORKSPACE_QUERY_MAX_VALUES},
            "context_key": {"type": "string"},
            "item_type": {"type": "string"},
            "dimension": {"type": "string"},
            "priority": {"type": "integer", "minimum": 0, "maximum": 3},
            "offset": {"type": "integer", "minimum": 0},
            "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": REVIEW_WORKSPACE_QUERY_MAX_LIMIT},
        },
        "facets": ["collections", "states", "sources", "contexts", "dimensions", "item_types", "priorities"],
        "boundary": [
            "queries operate only on the public review projection",
            "raw evidence payloads are never searchable or returned",
            "facets retain evidence and review states as separate values",
            "invalid replay-gated reports remain inspectable but are not accepted",
        ],
        "limits": {
            "default_limit": REVIEW_WORKSPACE_QUERY_DEFAULT_LIMIT,
            "max_limit": REVIEW_WORKSPACE_QUERY_MAX_LIMIT,
            "max_text": REVIEW_WORKSPACE_QUERY_MAX_TEXT,
            "max_values": REVIEW_WORKSPACE_QUERY_MAX_VALUES,
        },
    }


def review_workspace_query_capabilities() -> dict[str, Any]:
    """Return operational query capabilities without case-specific rows."""

    return {
        "version": REVIEW_WORKSPACE_QUERY_VERSION,
        "bounded_pagination": True,
        "faceted_filtering": True,
        "full_match_facets_with_page_results": True,
        "deterministic_sorting": True,
        "content_addressed_index_and_rows": True,
        "filters": list(review_workspace_query_schema()["filters"]),
        "public_boundary": {
            "raw_payload_search": False,
            "producer_metadata_search": False,
            "private_key_audit": True,
        },
    }


__all__ = [
    "REVIEW_WORKSPACE_QUERY_ALL_COLLECTIONS",
    "REVIEW_WORKSPACE_QUERY_COLLECTIONS",
    "REVIEW_WORKSPACE_QUERY_DEFAULT_LIMIT",
    "REVIEW_WORKSPACE_QUERY_MAX_FACET_VALUES",
    "REVIEW_WORKSPACE_QUERY_MAX_LIMIT",
    "REVIEW_WORKSPACE_QUERY_MAX_TEXT",
    "REVIEW_WORKSPACE_QUERY_MAX_VALUES",
    "REVIEW_WORKSPACE_QUERY_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_QUERY_VERSION",
    "ReviewWorkspaceIndex",
    "ReviewWorkspaceQuery",
    "ReviewWorkspaceQueryResult",
    "ReviewWorkspaceQueryRow",
    "build_persisted_review_workspace_index",
    "build_persisted_review_workspace_query",
    "build_review_workspace_index",
    "build_review_workspace_query_closure",
    "query_review_workspace",
    "review_workspace_query_capabilities",
    "review_workspace_query_schema",
]
