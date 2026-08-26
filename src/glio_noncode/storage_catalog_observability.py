"""Build and export deterministic health observations for storage catalogs."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_support import text_matches
from .serialization import canonical_json, content_hash
from .storage_catalog import _as_catalog
from .storage_catalog_contracts import StorageCatalog, StorageCatalogEntryKind, StorageCatalogState
from .storage_catalog_observability_contracts import (
    STORAGE_CATALOG_EVENT_TYPES,
    STORAGE_CATALOG_METRIC_NAMES,
    STORAGE_CATALOG_OBSERVABILITY_BOUNDARY,
    STORAGE_CATALOG_OBSERVABILITY_DEFAULT_LIMIT,
    STORAGE_CATALOG_OBSERVABILITY_MAX_EVENTS,
    STORAGE_CATALOG_OBSERVABILITY_MAX_LIMIT,
    STORAGE_CATALOG_OBSERVABILITY_SCHEMA_VERSION,
    STORAGE_CATALOG_OBSERVABILITY_VERSION,
    STORAGE_CATALOG_OBSERVATION_STATES,
    StorageCatalogEventType,
    StorageCatalogMetric,
    StorageCatalogObservability,
    StorageCatalogObservabilityQueryResult,
    StorageCatalogObservation,
    StorageCatalogObservationState,
)


def _text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


def _optional_text(value: Any, field: str, *, maximum: int = 500) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum=maximum)


def _int(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        raise ValidationError(f"{field} is outside its contract")
    return result


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _state(value: StorageCatalogState) -> StorageCatalogObservationState:
    return StorageCatalogObservationState(value.value)


def _event_type(kind: StorageCatalogEntryKind) -> StorageCatalogEventType:
    return {
        StorageCatalogEntryKind.OBJECT: StorageCatalogEventType.OBJECT_ENTRY,
        StorageCatalogEntryKind.MISSING: StorageCatalogEventType.MISSING_ENTRY,
        StorageCatalogEntryKind.RUN: StorageCatalogEventType.RUN_ENTRY,
        StorageCatalogEntryKind.BATCH: StorageCatalogEventType.BATCH_ENTRY,
        StorageCatalogEntryKind.UNEXPECTED: StorageCatalogEventType.UNEXPECTED_ENTRY,
    }[kind]


def _observation(
    *,
    sequence: int,
    event_type: StorageCatalogEventType,
    entry_id: str | None,
    index_name: str | None,
    kind: str,
    state: StorageCatalogObservationState,
    value: int,
    catalog_address: str,
) -> StorageCatalogObservation:
    body = {
        "sequence": sequence,
        "event_type": event_type.value,
        "entry_id": entry_id,
        "index_name": index_name,
        "kind": kind,
        "state": state.value,
        "value": value,
        "catalog_address": catalog_address,
    }
    return StorageCatalogObservation(
        sequence=sequence,
        event_type=event_type,
        entry_id=entry_id,
        index_name=index_name,
        kind=kind,
        state=state,
        value=value,
        catalog_address=catalog_address,
        content_address=content_hash(body, prefix="storage-catalog-observation"),
    )


def _metric(name: str, value: int | float, catalog_address: str) -> StorageCatalogMetric:
    body = {
        "name": name,
        "value": value,
        "unit": "count",
        "scope": "catalog",
        "catalog_address": catalog_address,
    }
    return StorageCatalogMetric(
        **body,
        content_address=content_hash(body, prefix="storage-catalog-metric"),
    )


def build_storage_catalog_observability(
    catalog: StorageCatalog | Mapping[str, Any],
) -> StorageCatalogObservability:
    """Create stable per-entry observations and aggregate catalog metrics."""

    selected = _as_catalog(catalog)
    specs: list[
        tuple[
            StorageCatalogEventType,
            str | None,
            str | None,
            str,
            StorageCatalogObservationState,
            int,
        ]
    ] = []
    for item in selected.entries:
        state = _state(item.state)
        specs.append(
            (
                StorageCatalogEventType.ENTRY_SEEN,
                item.entry_id,
                None,
                item.kind.value,
                state,
                int(item.accepted),
            )
        )
        specs.append(
            (_event_type(item.kind), item.entry_id, None, item.kind.value, state, item.byte_count)
        )
        if item.state is StorageCatalogState.ORPHAN:
            specs.append(
                (
                    StorageCatalogEventType.ORPHAN_ENTRY,
                    item.entry_id,
                    None,
                    item.kind.value,
                    StorageCatalogObservationState.ORPHAN,
                    1,
                )
            )
        elif not item.accepted:
            specs.append(
                (
                    StorageCatalogEventType.REJECTED_ENTRY,
                    item.entry_id,
                    None,
                    item.kind.value,
                    StorageCatalogObservationState.REJECTED,
                    1,
                )
            )
    for index_name in ("address", "path", "kind", "state"):
        rows = tuple(getattr(selected, f"{index_name}_index"))
        for row in rows:
            specs.append(
                (
                    StorageCatalogEventType.INDEX_BUILT,
                    None,
                    index_name,
                    "index",
                    StorageCatalogObservationState.OBSERVED,
                    len(row.entry_ids),
                )
            )
    if len(specs) > STORAGE_CATALOG_OBSERVABILITY_MAX_EVENTS:
        raise ValidationError("catalog observability event count exceeds its contract")
    events = tuple(
        _observation(
            sequence=sequence,
            event_type=event_type,
            entry_id=entry_id,
            index_name=index_name,
            kind=kind,
            state=state,
            value=value,
            catalog_address=selected.content_address,
        )
        for sequence, (event_type, entry_id, index_name, kind, state, value) in enumerate(
            specs, start=1
        )
    )
    counts = {
        kind: sum(item.kind.value == kind for item in selected.entries)
        for kind in ("object", "missing", "run", "batch", "unexpected")
    }
    states = {
        state: sum(item.state.value == state for item in selected.entries)
        for state in ("accepted", "rejected", "orphan", "missing", "unexpected")
    }
    index_rows = {
        name: len(tuple(getattr(selected, f"{name}_index")))
        for name in ("address", "path", "kind", "state")
    }
    index_key_count = sum(index_rows.values())
    indexed_entry_ids = {
        entry_id
        for name in ("address", "path", "kind", "state")
        for row in tuple(getattr(selected, f"{name}_index"))
        for entry_id in row.entry_ids
    }
    values: dict[str, int] = {
        "entry_count": selected.entry_count,
        "object_count": counts["object"],
        "missing_count": counts["missing"],
        "run_count": counts["run"],
        "batch_count": counts["batch"],
        "unexpected_count": counts["unexpected"],
        "accepted_entry_count": states["accepted"],
        "rejected_entry_count": states["rejected"],
        "orphan_entry_count": states["orphan"],
        "warning_total": sum(item.warning_count for item in selected.entries),
        "referenced_entry_count": sum(item.referenced for item in selected.entries),
        "index_row_count": selected.index_row_count,
        "index_key_count": index_key_count,
        "indexed_entry_count": len(indexed_entry_ids),
        "address_index_rows": index_rows["address"],
        "path_index_rows": index_rows["path"],
        "kind_index_rows": index_rows["kind"],
        "state_index_rows": index_rows["state"],
        "accepted_catalog": int(selected.accepted),
    }
    metrics = tuple(
        _metric(name, values[name], selected.content_address) for name in sorted(values)
    )
    return_body = {
        "storage_catalog_observability_version": STORAGE_CATALOG_OBSERVABILITY_VERSION,
        "catalog_address": selected.content_address,
        "events": tuple(item.to_dict() for item in events),
        "metrics": tuple(item.to_dict() for item in metrics),
        "accepted": selected.accepted,
    }
    return StorageCatalogObservability(
        catalog_address=selected.content_address,
        events=events,
        metrics=metrics,
        accepted=selected.accepted,
        content_address=content_hash(return_body, prefix="storage-catalog-observability"),
    )


def _as_observability(
    value: StorageCatalogObservability | Mapping[str, Any],
) -> StorageCatalogObservability:
    if isinstance(value, StorageCatalogObservability):
        return value
    return StorageCatalogObservability.from_mapping(value)


def query_storage_catalog_observability(
    observability: StorageCatalogObservability | Mapping[str, Any],
    *,
    event_type: str | None = None,
    state: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = STORAGE_CATALOG_OBSERVABILITY_DEFAULT_LIMIT,
) -> StorageCatalogObservabilityQueryResult:
    """Return a bounded, reproducible event page."""

    selected = _as_observability(observability)
    event_type = _optional_text(event_type, "event_type", maximum=80)
    state = _optional_text(state, "state", maximum=40)
    if event_type is not None and event_type not in STORAGE_CATALOG_EVENT_TYPES:
        raise ValidationError(f"unsupported catalog event type: {event_type}")
    if state is not None and state not in STORAGE_CATALOG_OBSERVATION_STATES:
        raise ValidationError(f"unsupported catalog observation state: {state}")
    text = _optional_text(text, "text", maximum=240)
    offset = _int(offset, "offset", minimum=0)
    limit = _int(limit, "limit", minimum=1, maximum=STORAGE_CATALOG_OBSERVABILITY_MAX_LIMIT)
    events = selected.events
    if event_type is not None:
        events = tuple(item for item in events if item.event_type.value == event_type)
    if state is not None:
        events = tuple(item for item in events if item.state.value == state)
    if text is not None:
        events = tuple(item for item in events if text_matches(item.to_dict(), text))
    total = len(events)
    items = tuple(item.to_dict() for item in events[offset : offset + limit])
    body = {
        "event_type": event_type,
        "state": state,
        "text": text,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": items,
        "observability_address": selected.content_address,
        "accepted": selected.accepted,
    }
    return StorageCatalogObservabilityQueryResult(
        event_type=event_type,
        state=state,
        text=text,
        total=total,
        offset=offset,
        limit=limit,
        items=items,
        observability_address=selected.content_address,
        accepted=selected.accepted,
        content_address=content_hash(body, prefix="storage-catalog-observability-query"),
    )


def storage_catalog_observability_json(
    observability: StorageCatalogObservability | Mapping[str, Any],
) -> str:
    return canonical_json(_as_observability(observability).to_dict())


def storage_catalog_observability_events_csv(
    observability: StorageCatalogObservability | Mapping[str, Any],
) -> str:
    selected = _as_observability(observability)
    fields = (
        "sequence",
        "event_type",
        "entry_id",
        "index_name",
        "kind",
        "state",
        "value",
        "catalog_address",
        "content_address",
    )
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in selected.events:
        writer.writerow({field: item.to_dict().get(field, "") for field in fields})
    return output.getvalue()


def storage_catalog_observability_metrics_csv(
    observability: StorageCatalogObservability | Mapping[str, Any],
) -> str:
    selected = _as_observability(observability)
    fields = ("name", "value", "unit", "scope", "catalog_address", "content_address")
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in selected.metrics:
        writer.writerow({field: item.to_dict().get(field, "") for field in fields})
    return output.getvalue()


def storage_catalog_observability_capabilities() -> dict[str, Any]:
    return {
        "version": STORAGE_CATALOG_OBSERVABILITY_VERSION,
        "schema_version": STORAGE_CATALOG_OBSERVABILITY_SCHEMA_VERSION,
        "boundary": STORAGE_CATALOG_OBSERVABILITY_BOUNDARY,
        "timestamp_free": True,
        "payload_exposure": False,
        "entry_events": True,
        "index_events": True,
        "aggregate_metrics": True,
        "bounded_event_query": True,
        "json_export": True,
        "events_csv": True,
        "metrics_csv": True,
        "mutation": False,
        "event_types": STORAGE_CATALOG_EVENT_TYPES,
        "states": STORAGE_CATALOG_OBSERVATION_STATES,
        "metric_names": STORAGE_CATALOG_METRIC_NAMES,
        "max_events": STORAGE_CATALOG_OBSERVABILITY_MAX_EVENTS,
        "max_limit": STORAGE_CATALOG_OBSERVABILITY_MAX_LIMIT,
    }


def storage_catalog_observability_schema() -> dict[str, Any]:
    return {
        "version": STORAGE_CATALOG_OBSERVABILITY_SCHEMA_VERSION,
        "type": "object",
        "boundary": STORAGE_CATALOG_OBSERVABILITY_BOUNDARY,
        "required": (
            "storage_catalog_observability_version",
            "catalog_address",
            "events",
            "metrics",
            "accepted",
            "content_address",
        ),
        "event_required": (
            "sequence",
            "event_type",
            "entry_id",
            "index_name",
            "kind",
            "state",
            "value",
            "catalog_address",
            "content_address",
        ),
        "metric_required": ("name", "value", "unit", "scope", "catalog_address", "content_address"),
        "event_types": STORAGE_CATALOG_EVENT_TYPES,
        "states": STORAGE_CATALOG_OBSERVATION_STATES,
        "metric_names": STORAGE_CATALOG_METRIC_NAMES,
        "derived": ("boundary", "event_count", "metric_count"),
        "timestamp_free": True,
        "payload_exposure": False,
        "strict_unknown_fields": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_CATALOG")
    or name.startswith("StorageCatalog")
    or name.startswith("build_storage_catalog_observability")
    or name.startswith("query_storage_catalog_observability")
    or name.startswith("storage_catalog_observability")
]
