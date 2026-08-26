"""Read-only provenance graph for the local content-addressed storage.

This module projects the persisted run and batch indexes into an address-only
graph. It follows the same typed object-reference boundary as the storage
audit, retains missing and orphan components explicitly, and never returns an
object payload. Graph construction is deterministic: files, nodes, edges,
filters, and exports are all ordered by stable identifiers and content
addresses. The graph is suitable for provenance inspection, structural diff,
and offline handoff, not for executing repair operations.
"""

from __future__ import annotations

import csv
import json
from collections import deque
from collections.abc import Mapping
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .release_assurance_support import text_matches
from .serialization import canonical_json, content_hash
from .storage_audit import (
    StorageAuditReport,
    _object_references,
    build_storage_audit,
)
from .storage_lineage_contracts import (
    STORAGE_LINEAGE_BOUNDARY,
    STORAGE_LINEAGE_DEFAULT_LIMIT,
    STORAGE_LINEAGE_EDGE_KINDS,
    STORAGE_LINEAGE_MAX_EDGES,
    STORAGE_LINEAGE_MAX_LIMIT,
    STORAGE_LINEAGE_MAX_NODES,
    STORAGE_LINEAGE_NODE_KINDS,
    STORAGE_LINEAGE_RESOURCES,
    STORAGE_LINEAGE_SCHEMA_VERSION,
    STORAGE_LINEAGE_VERSION,
    StorageLineageDiff,
    StorageLineageEdge,
    StorageLineageEdgeKind,
    StorageLineageGraph,
    StorageLineageNode,
    StorageLineageNodeKind,
    StorageLineageQueryResult,
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


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _as_report(value: StorageAuditReport | CaseRuntime) -> StorageAuditReport:
    if isinstance(value, StorageAuditReport):
        return value
    if isinstance(value, CaseRuntime):
        return build_storage_audit(value)
    raise ValidationError("storage lineage requires a storage audit or case runtime")


def _object_node_id(address: str) -> str:
    return f"object:{address}"


def _missing_node_id(address: str) -> str:
    return f"missing:{address}"


def _run_node_id(run_id: str) -> str:
    return f"run:{run_id}"


def _batch_node_id(batch_id: str) -> str:
    return f"batch:{batch_id}"


def _object_path(address: str) -> str | None:
    if address.startswith("sha256:"):
        return f"objects/{address.split(':', 1)[1]}.json"
    return None


def _node(
    *,
    node_id: str,
    kind: StorageLineageNodeKind,
    address: str | None,
    path: str | None,
    accepted: bool,
    root: bool,
    referenced: bool,
    depth: int,
    in_degree: int,
    out_degree: int,
) -> StorageLineageNode:
    body = {
        "node_id": node_id,
        "kind": kind,
        "address": address,
        "path": path,
        "accepted": accepted,
        "root": root,
        "referenced": referenced,
        "depth": depth,
        "in_degree": in_degree,
        "out_degree": out_degree,
    }
    return StorageLineageNode(
        **body,
        content_address=content_hash(body, prefix="storage-lineage-node"),
    )


def _edge(
    *,
    edge_id: str,
    source_id: str,
    target_id: str,
    kind: StorageLineageEdgeKind,
    field: str,
    accepted: bool,
) -> StorageLineageEdge:
    body = {
        "edge_id": edge_id,
        "source_id": source_id,
        "target_id": target_id,
        "kind": kind,
        "field": field,
        "accepted": accepted,
    }
    return StorageLineageEdge(
        **body,
        content_address=content_hash(body, prefix="storage-lineage-edge"),
    )


def _edge_key(
    source_id: str,
    target_id: str,
    kind: StorageLineageEdgeKind,
    field: str,
) -> tuple[str, str, str, str]:
    return source_id, target_id, kind.value, field


def _load_object(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _depths(root_ids: tuple[str, ...], edges: tuple[StorageLineageEdge, ...]) -> dict[str, int]:
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source_id, []).append(edge.target_id)
    depths = {node_id: 0 for node_id in root_ids}
    queue = deque(root_ids)
    while queue:
        source = queue.popleft()
        for target in sorted(adjacency.get(source, ())):
            candidate = depths[source] + 1
            if target not in depths or candidate < depths[target]:
                depths[target] = candidate
                queue.append(target)
    return depths


def build_storage_lineage(
    source: StorageAuditReport | CaseRuntime,
) -> StorageLineageGraph:
    """Build a deterministic address-only graph from a store-wide audit."""

    report = _as_report(source)
    root = Path(report.root)
    object_by_address = {item.address: item for item in report.objects}
    node_data: dict[str, dict[str, Any]] = {}
    root_ids: list[str] = []
    for item in report.runs:
        node_id = _run_node_id(item.run_id)
        node_data[node_id] = {
            "kind": StorageLineageNodeKind.RUN,
            "address": None,
            "path": f"runs/{item.filename}",
            "accepted": item.accepted,
            "root": True,
            "referenced": False,
        }
        root_ids.append(node_id)
    for item in report.batches:
        node_id = _batch_node_id(item.batch_id)
        node_data[node_id] = {
            "kind": StorageLineageNodeKind.BATCH,
            "address": None,
            "path": f"batches/{item.filename}",
            "accepted": item.accepted,
            "root": True,
            "referenced": False,
        }
        root_ids.append(node_id)
    for address, item in object_by_address.items():
        node_data[_object_node_id(address)] = {
            "kind": (
                StorageLineageNodeKind.ORPHAN
                if address in report.orphan_addresses
                else StorageLineageNodeKind.OBJECT
            ),
            "address": address,
            "path": f"objects/{item.filename}",
            "accepted": item.accepted,
            "root": False,
            "referenced": item.referenced,
        }
    for address in report.missing_addresses:
        node_data[_missing_node_id(address)] = {
            "kind": StorageLineageNodeKind.MISSING,
            "address": address,
            "path": _object_path(address),
            "accepted": False,
            "root": False,
            "referenced": True,
        }
    missing_node_ids = {_missing_node_id(value) for value in report.missing_addresses}
    edge_specs: set[tuple[str, str, str, str]] = set()
    for item in report.runs:
        source_id = _run_node_id(item.run_id)
        for address in item.pointer_addresses:
            target_id = (
                _object_node_id(address)
                if address in object_by_address
                else _missing_node_id(address)
            )
            edge_specs.add(_edge_key(source_id, target_id, StorageLineageEdgeKind.ROOT, "run.pointer"))
    for item in report.batches:
        source_id = _batch_node_id(item.batch_id)
        for field, address in (
            ("batch.input", item.input_address),
            ("batch.result", item.result_address),
        ):
            if address is None:
                continue
            target_id = (
                _object_node_id(address)
                if address in object_by_address
                else _missing_node_id(address)
            )
            edge_specs.add(_edge_key(source_id, target_id, StorageLineageEdgeKind.ROOT, field))
    for address, item in object_by_address.items():
        if not item.accepted:
            continue
        payload = _load_object(root / "objects" / item.filename)
        if payload is None:
            continue
        references, _malformed = _object_references(payload)
        source_id = _object_node_id(address)
        for reference in references:
            target_id = (
                _object_node_id(reference)
                if reference in object_by_address
                else _missing_node_id(reference)
            )
            edge_kind = (
                StorageLineageEdgeKind.REFERENCE
                if reference in object_by_address
                else StorageLineageEdgeKind.MISSING_REFERENCE
            )
            edge_specs.add(_edge_key(source_id, target_id, edge_kind, "object.reference"))
    edge_specs_sorted = sorted(edge_specs)
    if len(edge_specs_sorted) > STORAGE_LINEAGE_MAX_EDGES:
        raise ValidationError("storage lineage edge count exceeds its contract")
    edges = tuple(
        _edge(
            edge_id=f"storage-lineage-edge-{index:06d}",
            source_id=source_id,
            target_id=target_id,
            kind=StorageLineageEdgeKind(kind),
            field=field,
            accepted=target_id not in missing_node_ids,
        )
        for index, (source_id, target_id, kind, field) in enumerate(edge_specs_sorted, start=1)
    )
    root_ids_tuple = tuple(sorted(set(root_ids)))
    depths = _depths(root_ids_tuple, edges)
    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}
    for edge in edges:
        outgoing[edge.source_id] = outgoing.get(edge.source_id, 0) + 1
        incoming[edge.target_id] = incoming.get(edge.target_id, 0) + 1
    nodes = tuple(
        _node(
            node_id=node_id,
            kind=data["kind"],
            address=data["address"],
            path=data["path"],
            accepted=data["accepted"],
            root=data["root"],
            referenced=data["referenced"] or incoming.get(node_id, 0) > 0,
            depth=depths.get(node_id, 0),
            in_degree=incoming.get(node_id, 0),
            out_degree=outgoing.get(node_id, 0),
        )
        for node_id, data in sorted(node_data.items())
    )
    if len(nodes) > STORAGE_LINEAGE_MAX_NODES:
        raise ValidationError("storage lineage node count exceeds its contract")
    body = {
        "storage_lineage_version": STORAGE_LINEAGE_VERSION,
        "root": str(report.root),
        "audit_address": report.content_address,
        "nodes": tuple(item.to_dict() for item in nodes),
        "edges": tuple(item.to_dict() for item in edges),
        "root_node_ids": root_ids_tuple,
        "missing_addresses": tuple(sorted(report.missing_addresses)),
        "orphan_addresses": tuple(sorted(report.orphan_addresses)),
        "accepted": report.accepted,
    }
    return StorageLineageGraph(
        root=str(report.root),
        audit_address=report.content_address,
        nodes=nodes,
        edges=edges,
        root_node_ids=root_ids_tuple,
        missing_addresses=tuple(sorted(report.missing_addresses)),
        orphan_addresses=tuple(sorted(report.orphan_addresses)),
        accepted=report.accepted,
        content_address=content_hash(body, prefix="storage-lineage"),
    )


def _as_graph(value: StorageLineageGraph | Mapping[str, Any]) -> StorageLineageGraph:
    if isinstance(value, StorageLineageGraph):
        return value
    return StorageLineageGraph.from_mapping(value)


def query_storage_lineage(
    graph: StorageLineageGraph | Mapping[str, Any],
    *,
    resource: str = "nodes",
    node_kind: str | None = None,
    edge_kind: str | None = None,
    root_only: bool = False,
    orphan_only: bool = False,
    missing_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = STORAGE_LINEAGE_DEFAULT_LIMIT,
) -> StorageLineageQueryResult:
    """Return a bounded node or edge page with explicit graph filters."""

    selected = _as_graph(graph)
    resource = _text(resource, "resource", maximum=40).lower()
    if resource not in STORAGE_LINEAGE_RESOURCES:
        raise ValidationError(f"unsupported storage lineage resource: {resource}")
    node_filter = None if node_kind is None else _text(node_kind, "node_kind", maximum=40).lower()
    edge_filter = None if edge_kind is None else _text(edge_kind, "edge_kind", maximum=40).lower()
    if node_filter is not None and node_filter not in STORAGE_LINEAGE_NODE_KINDS:
        raise ValidationError(f"unsupported storage lineage node kind: {node_filter}")
    if edge_filter is not None and edge_filter not in STORAGE_LINEAGE_EDGE_KINDS:
        raise ValidationError(f"unsupported storage lineage edge kind: {edge_filter}")
    offset = _int(offset, "offset", minimum=0)
    limit = _int(limit, "limit", minimum=1, maximum=STORAGE_LINEAGE_MAX_LIMIT)
    text_filter = None if text is None else _text(text, "text", maximum=240).lower()
    if resource == "nodes":
        items: tuple[Any, ...] = selected.nodes
        if node_filter is not None:
            items = tuple(item for item in items if item.kind.value == node_filter)
        if root_only:
            items = tuple(item for item in items if item.root)
        if orphan_only:
            items = tuple(item for item in items if item.kind is StorageLineageNodeKind.ORPHAN)
        if missing_only:
            items = tuple(item for item in items if item.kind is StorageLineageNodeKind.MISSING)
    else:
        items = selected.edges
        if edge_filter is not None:
            items = tuple(item for item in items if item.kind.value == edge_filter)
        if root_only:
            items = tuple(item for item in items if item.kind is StorageLineageEdgeKind.ROOT)
        if orphan_only or missing_only:
            node_map = {item.node_id: item for item in selected.nodes}
            if orphan_only:
                items = tuple(
                    item
                    for item in items
                    if node_map.get(item.target_id, None)
                    and node_map[item.target_id].kind is StorageLineageNodeKind.ORPHAN
                )
            if missing_only:
                items = tuple(
                    item
                    for item in items
                    if node_map.get(item.target_id, None)
                    and node_map[item.target_id].kind is StorageLineageNodeKind.MISSING
                )
    if text_filter:
        items = tuple(item for item in items if text_matches(item.to_dict(), text_filter))
    total = len(items)
    page = items[offset : offset + limit]
    filters = {
        "resource": resource,
        "node_kind": node_kind,
        "edge_kind": edge_kind,
        "root_only": root_only,
        "orphan_only": orphan_only,
        "missing_only": missing_only,
        "text": text,
    }
    body = {
        "resource": resource,
        "filters": filters,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": tuple(item.to_dict() for item in page),
        "graph_address": selected.content_address,
        "accepted": selected.accepted,
    }
    return StorageLineageQueryResult(
        resource=resource,
        filters=filters,
        total=total,
        offset=offset,
        limit=limit,
        items=tuple(item.to_dict() for item in page),
        graph_address=selected.content_address,
        accepted=selected.accepted,
        content_address=content_hash(body, prefix="storage-lineage-query"),
    )


def diff_storage_lineage(
    baseline: StorageLineageGraph | Mapping[str, Any],
    candidate: StorageLineageGraph | Mapping[str, Any],
) -> StorageLineageDiff:
    """Compare two graph closures by node/edge content addresses and sets."""

    left = _as_graph(baseline)
    right = _as_graph(candidate)
    left_nodes = {item.node_id: item for item in left.nodes}
    right_nodes = {item.node_id: item for item in right.nodes}
    left_edges = {item.edge_id: item for item in left.edges}
    right_edges = {item.edge_id: item for item in right.edges}
    body = {
        "storage_lineage_diff_version": "storage-lineage-diff-v1",
        "baseline_address": left.content_address,
        "candidate_address": right.content_address,
        "added_node_ids": tuple(sorted(set(right_nodes) - set(left_nodes))),
        "removed_node_ids": tuple(sorted(set(left_nodes) - set(right_nodes))),
        "changed_node_ids": tuple(
            sorted(
                node_id
                for node_id in set(left_nodes) & set(right_nodes)
                if left_nodes[node_id].content_address != right_nodes[node_id].content_address
            )
        ),
        "added_edge_ids": tuple(sorted(set(right_edges) - set(left_edges))),
        "removed_edge_ids": tuple(sorted(set(left_edges) - set(right_edges))),
        "changed_edge_ids": tuple(
            sorted(
                edge_id
                for edge_id in set(left_edges) & set(right_edges)
                if left_edges[edge_id].content_address != right_edges[edge_id].content_address
            )
        ),
        "root_set_changed": left.root_node_ids != right.root_node_ids,
        "missing_set_changed": left.missing_addresses != right.missing_addresses,
        "orphan_set_changed": left.orphan_addresses != right.orphan_addresses,
        # A diff is an accepted comparison operation even when either input
        # graph records an integrity problem; the problem is represented by
        # the input graph state and the changed sets remain useful evidence.
        "accepted": True,
    }
    return StorageLineageDiff(
        baseline_address=left.content_address,
        candidate_address=right.content_address,
        added_node_ids=body["added_node_ids"],
        removed_node_ids=body["removed_node_ids"],
        changed_node_ids=body["changed_node_ids"],
        added_edge_ids=body["added_edge_ids"],
        removed_edge_ids=body["removed_edge_ids"],
        changed_edge_ids=body["changed_edge_ids"],
        root_set_changed=body["root_set_changed"],
        missing_set_changed=body["missing_set_changed"],
        orphan_set_changed=body["orphan_set_changed"],
        accepted=body["accepted"],
        content_address=content_hash(body, prefix="storage-lineage-diff"),
    )


def storage_lineage_json(graph: StorageLineageGraph | Mapping[str, Any]) -> str:
    """Serialize a strict graph as canonical JSON."""

    return canonical_json(_as_graph(graph).to_dict())


def storage_lineage_nodes_csv(graph: StorageLineageGraph | Mapping[str, Any]) -> str:
    """Serialize graph nodes without object payloads."""

    selected = _as_graph(graph)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "node_id",
            "kind",
            "address",
            "path",
            "accepted",
            "root",
            "referenced",
            "depth",
            "in_degree",
            "out_degree",
            "content_address",
        )
    )
    for item in selected.nodes:
        writer.writerow(
            (
                item.node_id,
                item.kind.value,
                item.address or "",
                item.path or "",
                str(item.accepted).lower(),
                str(item.root).lower(),
                str(item.referenced).lower(),
                item.depth,
                item.in_degree,
                item.out_degree,
                item.content_address,
            )
        )
    return output.getvalue()


def storage_lineage_edges_csv(graph: StorageLineageGraph | Mapping[str, Any]) -> str:
    """Serialize graph edges as deterministic CSV."""

    selected = _as_graph(graph)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ("edge_id", "source_id", "target_id", "kind", "field", "accepted", "content_address")
    )
    for item in selected.edges:
        writer.writerow(
            (
                item.edge_id,
                item.source_id,
                item.target_id,
                item.kind.value,
                item.field,
                str(item.accepted).lower(),
                item.content_address,
            )
        )
    return output.getvalue()


def storage_lineage_markdown(graph: StorageLineageGraph | Mapping[str, Any]) -> str:
    """Serialize graph summary and a compact edge table for review."""

    selected = _as_graph(graph)
    lines = [
        "# Storage lineage graph",
        "",
        f"- Root: `{selected.root}`",
        f"- Audit: `{selected.audit_address}`",
        f"- Graph: `{selected.content_address}`",
        f"- Accepted: `{str(selected.accepted).lower()}`",
        f"- Nodes: {selected.node_count}",
        f"- Edges: {selected.edge_count}",
        f"- Roots: {selected.root_count}",
        f"- Missing: {selected.missing_node_count}",
        f"- Orphans: {selected.orphan_node_count}",
        f"- Max depth: {selected.max_depth}",
        f"- Connected: `{str(selected.connected).lower()}`",
        "",
        "| Edge | Source | Target | Kind | Field | Accepted |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.edge_id}` | `{item.source_id}` | `{item.target_id}` | "
        f"`{item.kind.value}` | `{item.field}` | `{str(item.accepted).lower()}` |"
        for item in selected.edges
    )
    return "\n".join(lines) + "\n"


def storage_lineage_capabilities() -> dict[str, Any]:
    """Describe the address-only lineage graph boundary."""

    return {
        "version": STORAGE_LINEAGE_VERSION,
        "schema_version": STORAGE_LINEAGE_SCHEMA_VERSION,
        "boundary": STORAGE_LINEAGE_BOUNDARY,
        "address_only": True,
        "payload_exposure": False,
        "run_root_edges": True,
        "batch_root_edges": True,
        "object_reference_edges": True,
        "missing_reference_nodes": True,
        "orphan_nodes": True,
        "depths_and_degrees": True,
        "connectedness": True,
        "bounded_query": True,
        "structural_diff": True,
        "json_export": True,
        "nodes_csv": True,
        "edges_csv": True,
        "markdown_export": True,
        "timestamp_free": True,
        "mutation": False,
        "node_kinds": STORAGE_LINEAGE_NODE_KINDS,
        "edge_kinds": STORAGE_LINEAGE_EDGE_KINDS,
        "resources": STORAGE_LINEAGE_RESOURCES,
        "max_nodes": STORAGE_LINEAGE_MAX_NODES,
        "max_edges": STORAGE_LINEAGE_MAX_EDGES,
    }


def storage_lineage_schema() -> dict[str, Any]:
    """Return the closed storage-lineage graph schema."""

    return {
        "version": STORAGE_LINEAGE_SCHEMA_VERSION,
        "type": "object",
        "boundary": STORAGE_LINEAGE_BOUNDARY,
        "required": (
            "storage_lineage_version",
            "root",
            "audit_address",
            "nodes",
            "edges",
            "root_node_ids",
            "missing_addresses",
            "orphan_addresses",
            "accepted",
            "content_address",
        ),
        "node_kinds": STORAGE_LINEAGE_NODE_KINDS,
        "edge_kinds": STORAGE_LINEAGE_EDGE_KINDS,
        "resources": STORAGE_LINEAGE_RESOURCES,
        "derived": (
            "node_count",
            "edge_count",
            "object_node_count",
            "root_count",
            "missing_node_count",
            "orphan_node_count",
            "max_depth",
            "connected",
        ),
        "address_only": True,
        "payload_exposure": False,
        "timestamp_free": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_LINEAGE")
    or name.startswith("StorageLineage")
    or name.startswith("build_storage_lineage")
    or name.startswith("query_storage_lineage")
    or name.startswith("diff_storage_lineage")
    or name.startswith("storage_lineage")
]
