"""Deterministic events and metrics for the storage-lineage graph."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_support import text_matches
from .serialization import canonical_json, content_hash
from .storage_lineage import build_storage_lineage
from .storage_lineage_contracts import StorageLineageEdgeKind, StorageLineageGraph, StorageLineageNodeKind
from .storage_lineage_observability_contracts import (
    STORAGE_LINEAGE_EVENT_TYPES,
    STORAGE_LINEAGE_METRIC_NAMES,
    STORAGE_LINEAGE_OBSERVABILITY_BOUNDARY,
    STORAGE_LINEAGE_OBSERVABILITY_DEFAULT_LIMIT,
    STORAGE_LINEAGE_OBSERVABILITY_MAX_EVENTS,
    STORAGE_LINEAGE_OBSERVABILITY_MAX_LIMIT,
    STORAGE_LINEAGE_OBSERVABILITY_MAX_METRICS,
    STORAGE_LINEAGE_OBSERVABILITY_SCHEMA_VERSION,
    STORAGE_LINEAGE_OBSERVABILITY_STATES,
    STORAGE_LINEAGE_OBSERVABILITY_VERSION,
    StorageLineageEventType,
    StorageLineageMetric,
    StorageLineageObservation,
    StorageLineageObservationState,
    StorageLineageObservability,
)
from .runtime import CaseRuntime


def _text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


def _int(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        bound = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValidationError(f"{field} must be {bound}")
    return result


def _as_graph(value: StorageLineageGraph | CaseRuntime | Mapping[str, Any]) -> StorageLineageGraph:
    if isinstance(value, StorageLineageGraph):
        return value
    if isinstance(value, CaseRuntime):
        return build_storage_lineage(value)
    if isinstance(value, Mapping):
        return StorageLineageGraph.from_mapping(value)
    raise ValidationError("lineage observability requires a graph or case runtime")


def _event(
    *,
    sequence: int,
    event_type: StorageLineageEventType,
    node_id: str | None,
    edge_id: str | None,
    kind: str,
    state: StorageLineageObservationState,
    depth: int,
    degree: int,
    value: int,
    graph_address: str,
) -> StorageLineageObservation:
    body = {
        "sequence": sequence,
        "event_type": event_type.value,
        "node_id": node_id,
        "edge_id": edge_id,
        "kind": kind,
        "state": state.value,
        "depth": depth,
        "degree": degree,
        "value": value,
        "graph_address": graph_address,
    }
    return StorageLineageObservation(
        sequence=sequence,
        event_type=event_type,
        node_id=node_id,
        edge_id=edge_id,
        kind=kind,
        state=state,
        depth=depth,
        degree=degree,
        value=value,
        graph_address=graph_address,
        content_address=content_hash(body, prefix="storage-lineage-observation"),
    )


def _metric(name: str, value: int | float, graph_address: str) -> StorageLineageMetric:
    if name not in STORAGE_LINEAGE_METRIC_NAMES:
        raise ValidationError(f"unsupported lineage metric: {name}")
    body = {
        "name": name,
        "value": value,
        "unit": "count" if name != "max_depth" else "levels",
        "scope": "storage-lineage-graph",
        "graph_address": graph_address,
    }
    return StorageLineageMetric(
        **body,
        content_address=content_hash(body, prefix="storage-lineage-metric"),
    )


def _node_event(node: Any, sequence: int, graph_address: str) -> StorageLineageObservation:
    if node.kind is StorageLineageNodeKind.MISSING:
        event_type = StorageLineageEventType.MISSING_REFERENCE
        state = StorageLineageObservationState.UNRESOLVED
    elif node.kind is StorageLineageNodeKind.ORPHAN:
        event_type = StorageLineageEventType.ORPHAN_OBJECT
        state = StorageLineageObservationState.REJECTED if not node.accepted else StorageLineageObservationState.OBSERVED
    elif node.accepted:
        event_type = StorageLineageEventType.NODE_SEEN
        state = StorageLineageObservationState.ACCEPTED
    else:
        event_type = StorageLineageEventType.INVALID_NODE
        state = StorageLineageObservationState.REJECTED
    return _event(
        sequence=sequence,
        event_type=event_type,
        node_id=node.node_id,
        edge_id=None,
        kind=node.kind.value,
        state=state,
        depth=node.depth,
        degree=node.in_degree + node.out_degree,
        value=1,
        graph_address=graph_address,
    )


def _edge_event(edge: Any, sequence: int, graph_address: str) -> StorageLineageObservation:
    if edge.kind is StorageLineageEdgeKind.MISSING_REFERENCE:
        event_type = StorageLineageEventType.MISSING_REFERENCE
        state = StorageLineageObservationState.UNRESOLVED
    elif edge.accepted:
        event_type = StorageLineageEventType.EDGE_SEEN
        state = StorageLineageObservationState.ACCEPTED
    else:
        event_type = StorageLineageEventType.INVALID_EDGE
        state = StorageLineageObservationState.REJECTED
    return _event(
        sequence=sequence,
        event_type=event_type,
        node_id=None,
        edge_id=edge.edge_id,
        kind=edge.kind.value,
        state=state,
        depth=0,
        degree=1,
        value=1,
        graph_address=graph_address,
    )


def _metric_values(graph: StorageLineageGraph) -> dict[str, int]:
    roots = set(graph.root_node_ids)
    reachable = {item.node_id for item in graph.nodes if item.node_id in roots or item.depth > 0}
    components = 0
    pending = {item.node_id for item in graph.nodes}
    adjacency: dict[str, set[str]] = {item.node_id: set() for item in graph.nodes}
    for edge in graph.edges:
        adjacency[edge.source_id].add(edge.target_id)
        adjacency[edge.target_id].add(edge.source_id)
    while pending:
        components += 1
        start = min(pending)
        pending.remove(start)
        stack = [start]
        while stack:
            current = stack.pop()
            for target in sorted(adjacency[current]):
                if target in pending:
                    pending.remove(target)
                    stack.append(target)
    return {
        "node_count": graph.node_count,
        "edge_count": graph.edge_count,
        "root_count": graph.root_count,
        "object_node_count": graph.object_node_count,
        "missing_node_count": graph.missing_node_count,
        "orphan_node_count": graph.orphan_node_count,
        "accepted_node_count": sum(item.accepted for item in graph.nodes),
        "rejected_node_count": sum(not item.accepted for item in graph.nodes),
        "accepted_edge_count": sum(item.accepted for item in graph.edges),
        "rejected_edge_count": sum(not item.accepted for item in graph.edges),
        "max_depth": graph.max_depth,
        "max_in_degree": max((item.in_degree for item in graph.nodes), default=0),
        "max_out_degree": max((item.out_degree for item in graph.nodes), default=0),
        "reachable_node_count": len(reachable),
        "unreachable_node_count": graph.node_count - len(reachable),
        "connected_component_count": components,
    }


def build_storage_lineage_observability(
    source: StorageLineageGraph | CaseRuntime | Mapping[str, Any],
) -> StorageLineageObservability:
    """Build stable node, edge, and aggregate health observations."""

    graph = _as_graph(source)
    raw_events = [
        _node_event(item, index, graph.content_address)
        for index, item in enumerate(graph.nodes, start=1)
    ]
    raw_events.extend(
        _edge_event(item, index, graph.content_address)
        for index, item in enumerate(graph.edges, start=len(raw_events) + 1)
    )
    if len(raw_events) > STORAGE_LINEAGE_OBSERVABILITY_MAX_EVENTS:
        raise ValidationError("lineage observability event count exceeds its contract")
    events = tuple(raw_events)
    values = _metric_values(graph)
    metrics = tuple(_metric(name, values[name], graph.content_address) for name in sorted(values))
    if len(metrics) > STORAGE_LINEAGE_OBSERVABILITY_MAX_METRICS:
        raise ValidationError("lineage observability metric count exceeds its contract")
    body = {
        "storage_lineage_observability_version": STORAGE_LINEAGE_OBSERVABILITY_VERSION,
        "graph_address": graph.content_address,
        "events": tuple(item.to_dict() for item in events),
        "metrics": tuple(item.to_dict() for item in metrics),
        "accepted": graph.accepted,
    }
    return StorageLineageObservability(
        graph_address=graph.content_address,
        events=events,
        metrics=metrics,
        accepted=graph.accepted,
        content_address=content_hash(body, prefix="storage-lineage-observability"),
    )


def query_storage_lineage_events(
    source: StorageLineageObservability | StorageLineageGraph | CaseRuntime | Mapping[str, Any],
    *,
    event_type: str | None = None,
    kind: str | None = None,
    state: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = STORAGE_LINEAGE_OBSERVABILITY_DEFAULT_LIMIT,
) -> tuple[StorageLineageObservation, ...]:
    """Return a bounded deterministic event page."""

    if isinstance(source, StorageLineageObservability):
        observation = source
    elif isinstance(source, Mapping):
        observation = StorageLineageObservability.from_mapping(source)
    else:
        observation = build_storage_lineage_observability(source)
    values = {
        "event_type": event_type,
        "kind": kind,
        "state": state,
    }
    for field, value in values.items():
        if value is not None:
            values[field] = _text(value, field, maximum=80).lower()
    event_type = values["event_type"]
    kind = values["kind"]
    state = values["state"]
    if event_type is not None and event_type not in STORAGE_LINEAGE_EVENT_TYPES:
        raise ValidationError(f"unsupported lineage event type: {event_type}")
    if state is not None and state not in STORAGE_LINEAGE_OBSERVABILITY_STATES:
        raise ValidationError(f"unsupported lineage observation state: {state}")
    if kind is not None:
        kind = values["kind"]
    offset = _int(offset, "offset", minimum=0)
    limit = _int(limit, "limit", minimum=1, maximum=STORAGE_LINEAGE_OBSERVABILITY_MAX_LIMIT)
    selected = observation.events
    if event_type is not None:
        selected = tuple(item for item in selected if item.event_type.value == event_type)
    if kind is not None:
        selected = tuple(item for item in selected if item.kind == kind)
    if state is not None:
        selected = tuple(item for item in selected if item.state.value == state)
    if text is not None:
        text_value = _text(text, "text", maximum=240).lower()
        selected = tuple(item for item in selected if text_matches(item.to_dict(), text_value))
    return selected[offset : offset + limit]


def storage_lineage_observability_json(
    source: StorageLineageObservability | StorageLineageGraph | CaseRuntime | Mapping[str, Any],
) -> str:
    if isinstance(source, StorageLineageObservability):
        observation = source
    elif isinstance(source, Mapping):
        observation = StorageLineageObservability.from_mapping(source)
    else:
        observation = build_storage_lineage_observability(source)
    return canonical_json(observation.to_dict())


def storage_lineage_events_csv(
    source: StorageLineageObservability | StorageLineageGraph | CaseRuntime | Mapping[str, Any],
) -> str:
    if isinstance(source, StorageLineageObservability):
        observation = source
    elif isinstance(source, Mapping):
        observation = StorageLineageObservability.from_mapping(source)
    else:
        observation = build_storage_lineage_observability(source)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("sequence", "event_type", "node_id", "edge_id", "kind", "state", "depth", "degree", "value", "graph_address", "content_address"))
    for item in observation.events:
        writer.writerow((item.sequence, item.event_type.value, item.node_id or "", item.edge_id or "", item.kind, item.state.value, item.depth, item.degree, item.value, item.graph_address, item.content_address))
    return output.getvalue()


def storage_lineage_metrics_csv(
    source: StorageLineageObservability | StorageLineageGraph | CaseRuntime | Mapping[str, Any],
) -> str:
    if isinstance(source, StorageLineageObservability):
        observation = source
    elif isinstance(source, Mapping):
        observation = StorageLineageObservability.from_mapping(source)
    else:
        observation = build_storage_lineage_observability(source)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("name", "value", "unit", "scope", "graph_address", "content_address"))
    for item in observation.metrics:
        writer.writerow((item.name, item.value, item.unit, item.scope, item.graph_address, item.content_address))
    return output.getvalue()


def storage_lineage_observability_capabilities() -> dict[str, Any]:
    return {
        "version": STORAGE_LINEAGE_OBSERVABILITY_VERSION,
        "schema_version": STORAGE_LINEAGE_OBSERVABILITY_SCHEMA_VERSION,
        "boundary": STORAGE_LINEAGE_OBSERVABILITY_BOUNDARY,
        "deterministic_events": True,
        "aggregate_metrics": True,
        "bounded_event_query": True,
        "events_csv": True,
        "metrics_csv": True,
        "payload_exposure": False,
        "mutation": False,
        "timestamp_free": True,
        "event_types": STORAGE_LINEAGE_EVENT_TYPES,
        "states": STORAGE_LINEAGE_OBSERVABILITY_STATES,
        "metric_names": STORAGE_LINEAGE_METRIC_NAMES,
        "max_events": STORAGE_LINEAGE_OBSERVABILITY_MAX_EVENTS,
        "max_metrics": STORAGE_LINEAGE_OBSERVABILITY_MAX_METRICS,
    }


def storage_lineage_observability_schema() -> dict[str, Any]:
    return {
        "version": STORAGE_LINEAGE_OBSERVABILITY_SCHEMA_VERSION,
        "type": "object",
        "boundary": STORAGE_LINEAGE_OBSERVABILITY_BOUNDARY,
        "required": (
            "storage_lineage_observability_version",
            "graph_address",
            "events",
            "metrics",
            "accepted",
            "content_address",
        ),
        "event_required": (
            "sequence", "event_type", "node_id", "edge_id", "kind", "state",
            "depth", "degree", "value", "graph_address", "content_address",
        ),
        "metric_required": ("name", "value", "unit", "scope", "graph_address", "content_address"),
        "event_types": STORAGE_LINEAGE_EVENT_TYPES,
        "states": STORAGE_LINEAGE_OBSERVABILITY_STATES,
        "metric_names": STORAGE_LINEAGE_METRIC_NAMES,
        "payload_exposure": False,
        "timestamp_free": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_LINEAGE_")
    or name.startswith("StorageLineage")
    or name.startswith("build_storage_lineage_observability")
    or name.startswith("query_storage_lineage_events")
    or name.startswith("storage_lineage_")
]
