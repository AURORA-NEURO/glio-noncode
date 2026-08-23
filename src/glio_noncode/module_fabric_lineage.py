"""Closed lineage graph for module-fabric fixture and reference receipts."""

from __future__ import annotations

from collections.abc import Iterable

from .module_fabric_contracts import FabricFixture, FabricLineage, FabricLineageEdge, FabricLineageNode, FabricEvaluation
from .module_fabric_fixture_eval import evaluate_module_fabric_fixture
from .module_fabric_public_data import default_module_fabric_fixture
from .serialization import content_hash


def _node(node_id: str, node_kind: str) -> FabricLineageNode:
    body = {"node_id": node_id, "node_kind": node_kind}
    return FabricLineageNode(**body, content_address=content_hash(body, prefix="module-fabric-node"))


def _edge(source_id: str, target_id: str, relation: str) -> FabricLineageEdge:
    body = {"source_id": source_id, "target_id": target_id, "relation": relation}
    return FabricLineageEdge(**body, content_address=content_hash(body, prefix="module-fabric-edge"))


def build_module_fabric_lineage(
    fixture: FabricFixture | None = None,
    evaluation: FabricEvaluation | None = None,
) -> FabricLineage:
    value = fixture or default_module_fabric_fixture()
    report = evaluation or evaluate_module_fabric_fixture(value)
    nodes: list[FabricLineageNode] = [_node(value.fixture_id, "fixture")]
    edges: list[FabricLineageEdge] = []
    for source in value.sources:
        nodes.append(_node(source.source_id, "source"))
        edges.append(_edge(value.fixture_id, source.source_id, "uses_source"))
    for record, execution in zip(value.records, report.executions, strict=True):
        nodes.extend((_node(record.record_id, "record"), _node(execution.content_address, "execution")))
        edges.extend(
            (
                _edge(value.fixture_id, record.record_id, "contains_record"),
                _edge(record.record_id, execution.content_address, "executes_to"),
            )
        )
        for source_id in record.source_ids:
            edges.append(_edge(record.record_id, source_id, "record_source"))
        for receipt in (*execution.implementation_receipts, *execution.test_receipts):
            receipt_node_id = f"{execution.content_address}:{receipt.content_address}"
            nodes.append(_node(receipt_node_id, receipt.kind.value))
            edges.append(_edge(execution.content_address, receipt_node_id, "resolves_reference"))
    node_ids = {item.node_id for item in nodes}
    issues = [
        "duplicate_node_id"
        if len(node_ids) != len(nodes)
        else "",
        "missing_edge_endpoint"
        if any(edge.source_id not in node_ids or edge.target_id not in node_ids for edge in edges)
        else "",
        "fixture_not_root"
        if not any(edge.source_id == value.fixture_id for edge in edges)
        else "",
    ]
    normalized = tuple(item for item in issues if item)
    body = {"nodes": nodes, "edges": edges, "accepted": not normalized, "issues": normalized}
    return FabricLineage(tuple(nodes), tuple(edges), not normalized, normalized, content_hash(body, prefix="module-fabric-lineage"))


def lineage_node_ids(lineage: FabricLineage) -> tuple[str, ...]:
    return tuple(item.node_id for item in lineage.nodes)


def lineage_edges_for(lineage: FabricLineage, node_id: str) -> tuple[FabricLineageEdge, ...]:
    return tuple(item for item in lineage.edges if item.source_id == node_id or item.target_id == node_id)


def verify_module_fabric_lineage(lineage: FabricLineage) -> tuple[str, ...]:
    node_ids = set(lineage_node_ids(lineage))
    issues: list[str] = []
    if len(node_ids) != len(lineage.nodes):
        issues.append("duplicate_node_id")
    if any(edge.source_id not in node_ids or edge.target_id not in node_ids for edge in lineage.edges):
        issues.append("missing_edge_endpoint")
    if not lineage.accepted:
        issues.extend(lineage.issues)
    return tuple(dict.fromkeys(issues))


__all__ = [
    "build_module_fabric_lineage",
    "lineage_edges_for",
    "lineage_node_ids",
    "verify_module_fabric_lineage",
]
