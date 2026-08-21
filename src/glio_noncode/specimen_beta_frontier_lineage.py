"""Sanitized source-to-result lineage graph for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .specimen_beta_frontier_fixture_eval import evaluate_specimen_beta_frontier_fixture
from .specimen_beta_frontier_public_data import SpecimenBetaFrontierFixtureCatalog


class SpecimenBetaFrontierLineageNodeKind(StrEnum):
    SOURCE = "source"
    FIXTURE = "fixture"
    RECORD = "record"
    RESULT = "result"


class SpecimenBetaFrontierLineageRelation(StrEnum):
    DECLARES = "declares"
    CONTAINS = "contains"
    PRODUCES = "produces"


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierLineageNode:
    """One source, fixture, record, or result vertex."""

    node_id: str
    kind: SpecimenBetaFrontierLineageNodeKind
    context_key: str
    content_address: str
    source_id: str | None = None
    record_id: str | None = None
    operation: str | None = None
    state: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.node_id, "beta lineage node ID")
        require_non_empty(self.context_key, "beta lineage node context")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("beta lineage node address must be sha256-prefixed")
        if self.kind == SpecimenBetaFrontierLineageNodeKind.SOURCE and not self.source_id:
            raise ValueError("beta source node requires source_id")
        if (
            self.kind
            in {
                SpecimenBetaFrontierLineageNodeKind.RECORD,
                SpecimenBetaFrontierLineageNodeKind.RESULT,
            }
            and not self.record_id
        ):
            raise ValueError("beta record/result node requires record_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierLineageEdge:
    """Typed directed relationship between two lineage nodes."""

    edge_id: str
    from_node: str
    to_node: str
    relation: SpecimenBetaFrontierLineageRelation

    def __post_init__(self) -> None:
        for name in ("edge_id", "from_node", "to_node"):
            require_non_empty(str(getattr(self, name)), f"beta lineage edge {name}")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierLineageGraph:
    """Complete run lineage graph."""

    fixture_id: str
    context_key: str
    nodes: tuple[SpecimenBetaFrontierLineageNode, ...]
    edges: tuple[SpecimenBetaFrontierLineageEdge, ...]
    content_address: str

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(node.node_id for node in self.nodes)

    @property
    def edge_ids(self) -> tuple[str, ...]:
        return tuple(edge.edge_id for edge in self.edges)

    @property
    def root_ids(self) -> tuple[str, ...]:
        targets = {edge.to_node for edge in self.edges}
        return tuple(node.node_id for node in self.nodes if node.node_id not in targets)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierLineageAuditReport:
    """Integrity report for a lineage graph."""

    fixture_id: str
    passed: bool
    issue_codes: tuple[str, ...]
    node_count: int
    edge_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_specimen_beta_frontier_lineage(
    catalog: SpecimenBetaFrontierFixtureCatalog,
) -> SpecimenBetaFrontierLineageGraph:
    """Build four source, one fixture, twelve record, and twelve result nodes."""

    evaluation = evaluate_specimen_beta_frontier_fixture(catalog)
    receipt_by_id = {receipt.record_id: receipt for receipt in evaluation.receipts}
    nodes: list[SpecimenBetaFrontierLineageNode] = []
    for source in catalog.sources:
        nodes.append(
            SpecimenBetaFrontierLineageNode(
                node_id=f"source:{source.source_id}",
                kind=SpecimenBetaFrontierLineageNodeKind.SOURCE,
                context_key=catalog.context_key,
                content_address=content_hash(source.to_dict()),
                source_id=source.source_id,
                state="declared",
            )
        )
    nodes.append(
        SpecimenBetaFrontierLineageNode(
            node_id=f"fixture:{catalog.fixture_id}",
            kind=SpecimenBetaFrontierLineageNodeKind.FIXTURE,
            context_key=catalog.context_key,
            content_address=catalog.content_address,
            state="aggregate",
        )
    )
    for record in catalog.records:
        receipt = receipt_by_id[record.record_id]
        nodes.append(
            SpecimenBetaFrontierLineageNode(
                node_id=f"record:{record.record_id}",
                kind=SpecimenBetaFrontierLineageNodeKind.RECORD,
                context_key=record.context_key,
                content_address=record.content_address,
                record_id=record.record_id,
                operation=record.operation.value,
                state=record.expected_fixture_state.value,
            )
        )
        nodes.append(
            SpecimenBetaFrontierLineageNode(
                node_id=f"result:{record.record_id}",
                kind=SpecimenBetaFrontierLineageNodeKind.RESULT,
                context_key=record.context_key,
                content_address=receipt.output_address,
                record_id=record.record_id,
                operation=record.operation.value,
                state=receipt.observed_result_state,
            )
        )
    edges: list[SpecimenBetaFrontierLineageEdge] = []
    for index, record in enumerate(catalog.records, start=1):
        source_id = record.source_ids[0]
        edges.append(
            SpecimenBetaFrontierLineageEdge(
                edge_id=f"edge:{index:03d}:source-record",
                from_node=f"source:{source_id}",
                to_node=f"record:{record.record_id}",
                relation=SpecimenBetaFrontierLineageRelation.DECLARES,
            )
        )
        edges.append(
            SpecimenBetaFrontierLineageEdge(
                edge_id=f"edge:{index:03d}:fixture-record",
                from_node=f"fixture:{catalog.fixture_id}",
                to_node=f"record:{record.record_id}",
                relation=SpecimenBetaFrontierLineageRelation.CONTAINS,
            )
        )
        edges.append(
            SpecimenBetaFrontierLineageEdge(
                edge_id=f"edge:{index:03d}:record-result",
                from_node=f"record:{record.record_id}",
                to_node=f"result:{record.record_id}",
                relation=SpecimenBetaFrontierLineageRelation.PRODUCES,
            )
        )
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "nodes": nodes,
        "edges": edges,
    }
    return SpecimenBetaFrontierLineageGraph(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        nodes=tuple(nodes),
        edges=tuple(edges),
        content_address=content_hash(body),
    )


def audit_specimen_beta_frontier_lineage(
    graph: SpecimenBetaFrontierLineageGraph,
) -> SpecimenBetaFrontierLineageAuditReport:
    """Check graph shape, endpoints, addresses, context, and relation types."""

    issues: set[str] = set()
    node_ids = set(graph.node_ids)
    if len(node_ids) != len(graph.nodes):
        issues.add("duplicate_node_id")
    if len(set(graph.edge_ids)) != len(graph.edges):
        issues.add("duplicate_edge_id")
    if any(edge.from_node not in node_ids or edge.to_node not in node_ids for edge in graph.edges):
        issues.add("missing_endpoint")
    if any(edge.from_node == edge.to_node for edge in graph.edges):
        issues.add("self_edge")
    valid_relations = set(SpecimenBetaFrontierLineageRelation)
    if any(edge.relation not in valid_relations for edge in graph.edges):
        issues.add("unknown_relation")
    if len(graph.nodes) != 29:
        issues.add("node_shape")
    if len(graph.edges) != 36:
        issues.add("edge_shape")
    if len({node.context_key for node in graph.nodes}) != 1:
        issues.add("context_mismatch")
    if sum(node.kind == SpecimenBetaFrontierLineageNodeKind.SOURCE for node in graph.nodes) != 4:
        issues.add("source_shape")
    if sum(node.kind == SpecimenBetaFrontierLineageNodeKind.FIXTURE for node in graph.nodes) != 1:
        issues.add("fixture_shape")
    if sum(node.kind == SpecimenBetaFrontierLineageNodeKind.RECORD for node in graph.nodes) != 12:
        issues.add("record_shape")
    if sum(node.kind == SpecimenBetaFrontierLineageNodeKind.RESULT for node in graph.nodes) != 12:
        issues.add("result_shape")
    source_node_ids = {
        node.node_id
        for node in graph.nodes
        if node.kind == SpecimenBetaFrontierLineageNodeKind.SOURCE
    }
    if not source_node_ids.issubset({edge.from_node for edge in graph.edges}):
        issues.add("source_coverage")
    body = {
        "fixture_id": graph.fixture_id,
        "context_key": graph.context_key,
        "nodes": graph.nodes,
        "edges": graph.edges,
    }
    if graph.content_address != content_hash(body):
        issues.add("graph_address_mismatch")
    return SpecimenBetaFrontierLineageAuditReport(
        fixture_id=graph.fixture_id,
        passed=not issues,
        issue_codes=tuple(sorted(issues)),
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
        content_address=content_hash(
            {
                "fixture_id": graph.fixture_id,
                "passed": not issues,
                "issue_codes": tuple(sorted(issues)),
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
            }
        ),
    )


__all__ = [
    "SpecimenBetaFrontierLineageAuditReport",
    "SpecimenBetaFrontierLineageEdge",
    "SpecimenBetaFrontierLineageGraph",
    "SpecimenBetaFrontierLineageNode",
    "SpecimenBetaFrontierLineageNodeKind",
    "SpecimenBetaFrontierLineageRelation",
    "audit_specimen_beta_frontier_lineage",
    "build_specimen_beta_frontier_lineage",
]
