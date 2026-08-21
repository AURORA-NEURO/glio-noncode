"""Sanitized source-to-result lineage graph for Domain 02 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .structural_frontier_fixture_eval import (
    StructuralFrontierFixtureEvaluationReport,
    evaluate_structural_frontier_fixture,
)
from .structural_frontier_public_data import (
    StructuralFrontierFixtureCatalog,
    StructuralFrontierFixtureState,
)


class StructuralFrontierLineageNodeKind(StrEnum):
    """Typed node classes in the C13-C16 evidence graph."""

    SOURCE = "source"
    FIXTURE = "fixture"
    RECORD = "record"
    RESULT = "result"


class StructuralFrontierLineageRelation(StrEnum):
    """Typed relationships in the C13-C16 evidence graph."""

    DECLARES = "declares"
    CONTAINS = "contains"
    PRODUCES = "produces"


@dataclass(frozen=True, slots=True)
class StructuralFrontierLineageNode:
    """A sanitized graph node with no raw operation payload."""

    node_id: str
    kind: StructuralFrontierLineageNodeKind
    label: str
    state: str
    context_key: str
    content_address: str
    source_id: str | None = None
    record_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("node_id", "label", "state", "context_key", "content_address"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("structural frontier lineage context requires six fields")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("structural frontier lineage node must be addressed")
        if self.kind == StructuralFrontierLineageNodeKind.SOURCE and not self.source_id:
            raise ValidationError("structural frontier source node requires source_id")
        if self.kind in {StructuralFrontierLineageNodeKind.RECORD, StructuralFrontierLineageNodeKind.RESULT} and not self.record_id:
            raise ValidationError("structural frontier record/result node requires record_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFrontierLineageEdge:
    """A content-addressed relationship between two graph nodes."""

    edge_id: str
    from_node: str
    to_node: str
    relation: StructuralFrontierLineageRelation
    content_address: str

    def __post_init__(self) -> None:
        for field_name in ("edge_id", "from_node", "to_node", "content_address"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.from_node == self.to_node:
            raise ValidationError("structural frontier lineage edge cannot self-reference")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("structural frontier lineage edge must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFrontierLineageGraph:
    """Sanitized graph for one C13-C16 fixture."""

    graph_id: str
    fixture_id: str
    context_key: str
    state: StructuralFrontierFixtureState
    source_ids: tuple[str, ...]
    nodes: tuple[StructuralFrontierLineageNode, ...]
    edges: tuple[StructuralFrontierLineageEdge, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field_name in ("graph_id", "fixture_id", "context_key", "content_address"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("structural frontier lineage graph context requires six fields")
        if not self.nodes:
            raise ValidationError("structural frontier lineage graph requires nodes")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("structural frontier lineage graph must be addressed")

    @property
    def accepted(self) -> bool:
        return self.state == StructuralFrontierFixtureState.ACCEPTED

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(node.node_id for node in self.nodes)

    @property
    def source_ids_sorted(self) -> tuple[str, ...]:
        return tuple(sorted(self.source_ids))

    @property
    def root_ids(self) -> tuple[str, ...]:
        incoming = {edge.to_node for edge in self.edges}
        return tuple(node.node_id for node in self.nodes if node.node_id not in incoming)

    def node(self, node_id: str) -> StructuralFrontierLineageNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise ValidationError(f"unknown structural frontier lineage node: {node_id}")

    def children(self, node_id: str) -> tuple[str, ...]:
        self.node(node_id)
        return tuple(edge.to_node for edge in self.edges if edge.from_node == node_id)

    def verify(self) -> bool:
        node_ids = set(self.node_ids)
        if len(node_ids) != len(self.nodes):
            return False
        if any(edge.from_node not in node_ids or edge.to_node not in node_ids for edge in self.edges):
            return False
        return self.content_address == content_hash(_graph_body(self))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "root_ids": self.root_ids,
        }


@dataclass(frozen=True, slots=True)
class StructuralFrontierLineageAudit:
    """Audit result for graph addresses, endpoints, and source coverage."""

    graph_id: str
    fixture_id: str
    state: StructuralFrontierFixtureState
    issue_codes: tuple[str, ...]
    node_count: int
    edge_count: int
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == StructuralFrontierFixtureState.ACCEPTED and not self.issue_codes

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


class StructuralFrontierLineageBuilder:
    """Build and audit a deterministic four-layer source graph."""

    def build(
        self,
        fixture: StructuralFrontierFixtureCatalog | str,
        *,
        evaluation: StructuralFrontierFixtureEvaluationReport | None = None,
        graph_id: str | None = None,
    ) -> StructuralFrontierLineageGraph:
        catalog = StructuralFrontierFixtureCatalog.from_file(fixture) if isinstance(fixture, str) else fixture
        report = evaluation or evaluate_structural_frontier_fixture(catalog)
        receipt_by_id = {receipt.record_id: receipt for receipt in report.receipts}
        nodes: list[StructuralFrontierLineageNode] = []
        edges: list[StructuralFrontierLineageEdge] = []
        for source in catalog.sources:
            node_id = f"source:{source.source_id}"
            source_body = {
                "node_id": node_id,
                "kind": StructuralFrontierLineageNodeKind.SOURCE,
                "source_id": source.source_id,
                "title": source.title,
                "version": source.version,
                "scope": source.data_scope,
                "context_key": catalog.context_key,
            }
            nodes.append(
                StructuralFrontierLineageNode(
                    node_id=node_id,
                    kind=StructuralFrontierLineageNodeKind.SOURCE,
                    label=source.title,
                    state=StructuralFrontierFixtureState.ACCEPTED.value,
                    context_key=catalog.context_key,
                    content_address=content_hash(source_body),
                    source_id=source.source_id,
                )
            )
        fixture_node_id = f"fixture:{catalog.fixture_id}"
        nodes.append(
            StructuralFrontierLineageNode(
                node_id=fixture_node_id,
                kind=StructuralFrontierLineageNodeKind.FIXTURE,
                label=catalog.fixture_id,
                state=StructuralFrontierFixtureState.ACCEPTED.value if report.passed else StructuralFrontierFixtureState.REVIEW.value,
                context_key=catalog.context_key,
                content_address=catalog.content_address,
            )
        )
        for record in catalog.positives + catalog.controls:
            receipt = receipt_by_id[record.record_id]
            record_node_id = f"record:{record.record_id}"
            record_body = {
                "node_id": record_node_id,
                "kind": StructuralFrontierLineageNodeKind.RECORD,
                "record_id": record.record_id,
                "operation": record.operation,
                "expected_state": record.expected_state,
                "expected_result_state": record.expected_result_state,
                "context_key": record.context_key,
                "source_id": record.source_id,
            }
            nodes.append(
                StructuralFrontierLineageNode(
                    node_id=record_node_id,
                    kind=StructuralFrontierLineageNodeKind.RECORD,
                    label=record.record_id,
                    state=record.expected_state.value,
                    context_key=record.context_key,
                    content_address=content_hash(record_body),
                    source_id=record.source_id,
                    record_id=record.record_id,
                )
            )
            result_node_id = f"result:{record.record_id}"
            nodes.append(
                StructuralFrontierLineageNode(
                    node_id=result_node_id,
                    kind=StructuralFrontierLineageNodeKind.RESULT,
                    label=record.operation.value,
                    state=receipt.observed_state.value,
                    context_key=record.context_key,
                    content_address=receipt.output_address,
                    source_id=record.source_id,
                    record_id=record.record_id,
                )
            )
            edges.extend(
                (
                    _edge(f"source:{record.source_id}", record_node_id, StructuralFrontierLineageRelation.DECLARES),
                    _edge(fixture_node_id, record_node_id, StructuralFrontierLineageRelation.CONTAINS),
                    _edge(record_node_id, result_node_id, StructuralFrontierLineageRelation.PRODUCES),
                )
            )
        selected_graph_id = require_non_empty(graph_id or f"{catalog.fixture_id}-lineage", "graph_id")
        sorted_nodes = tuple(sorted(nodes, key=lambda node: node.node_id))
        sorted_edges = tuple(sorted(edges, key=lambda edge: edge.edge_id))
        body = {
            "graph_id": selected_graph_id,
            "fixture_id": catalog.fixture_id,
            "context_key": catalog.context_key,
            "state": StructuralFrontierFixtureState.ACCEPTED if report.passed else StructuralFrontierFixtureState.REVIEW,
            "source_ids": catalog.source_ids,
            "nodes": sorted_nodes,
            "edges": sorted_edges,
        }
        return StructuralFrontierLineageGraph(
            graph_id=selected_graph_id,
            fixture_id=catalog.fixture_id,
            context_key=catalog.context_key,
            state=body["state"],
            source_ids=catalog.source_ids,
            nodes=sorted_nodes,
            edges=sorted_edges,
            content_address=content_hash(body),
        )

    def audit(self, graph: StructuralFrontierLineageGraph) -> StructuralFrontierLineageAudit:
        issues: set[str] = set()
        if not graph.verify():
            issues.add("graph_address_or_endpoint_invalid")
        source_nodes = {
            node.source_id
            for node in graph.nodes
            if node.kind == StructuralFrontierLineageNodeKind.SOURCE
        }
        if source_nodes != set(graph.source_ids):
            issues.add("source_coverage")
        if not any(node.kind == StructuralFrontierLineageNodeKind.FIXTURE for node in graph.nodes):
            issues.add("fixture_node_missing")
        record_nodes = {
            node.record_id
            for node in graph.nodes
            if node.kind == StructuralFrontierLineageNodeKind.RECORD
        }
        result_nodes = {
            node.record_id
            for node in graph.nodes
            if node.kind == StructuralFrontierLineageNodeKind.RESULT
        }
        if record_nodes != result_nodes:
            issues.add("record_result_mismatch")
        if any(node.context_key != graph.context_key for node in graph.nodes):
            issues.add("context_mismatch")
        if any(
            node.kind == StructuralFrontierLineageNodeKind.RECORD and node.source_id not in source_nodes
            for node in graph.nodes
        ):
            issues.add("record_source_missing")
        state = StructuralFrontierFixtureState.ACCEPTED if not issues else StructuralFrontierFixtureState.REVIEW
        body = {
            "graph_id": graph.graph_id,
            "fixture_id": graph.fixture_id,
            "state": state,
            "issues": tuple(sorted(issues)),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
        }
        return StructuralFrontierLineageAudit(
            graph_id=graph.graph_id,
            fixture_id=graph.fixture_id,
            state=state,
            issue_codes=tuple(sorted(issues)),
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            content_address=content_hash(body),
        )


def build_structural_frontier_lineage(
    fixture: StructuralFrontierFixtureCatalog | str,
    *,
    evaluation: StructuralFrontierFixtureEvaluationReport | None = None,
    graph_id: str | None = None,
) -> StructuralFrontierLineageGraph:
    """Build a deterministic C13-C16 lineage graph."""

    return StructuralFrontierLineageBuilder().build(fixture, evaluation=evaluation, graph_id=graph_id)


def audit_structural_frontier_lineage(graph: StructuralFrontierLineageGraph) -> StructuralFrontierLineageAudit:
    """Audit an already-built C13-C16 lineage graph."""

    return StructuralFrontierLineageBuilder().audit(graph)


def _edge(
    source: str,
    target: str,
    relation: StructuralFrontierLineageRelation,
) -> StructuralFrontierLineageEdge:
    edge_id = f"{relation.value}:{source}->{target}"
    body = {"edge_id": edge_id, "from_node": source, "to_node": target, "relation": relation}
    return StructuralFrontierLineageEdge(
        edge_id=edge_id,
        from_node=source,
        to_node=target,
        relation=relation,
        content_address=content_hash(body),
    )


def _graph_body(graph: StructuralFrontierLineageGraph) -> dict[str, Any]:
    return {
        "graph_id": graph.graph_id,
        "fixture_id": graph.fixture_id,
        "context_key": graph.context_key,
        "state": graph.state,
        "source_ids": graph.source_ids,
        "nodes": tuple(sorted(graph.nodes, key=lambda node: node.node_id)),
        "edges": tuple(sorted(graph.edges, key=lambda edge: edge.edge_id)),
    }


__all__ = [
    "StructuralFrontierLineageAudit",
    "StructuralFrontierLineageBuilder",
    "StructuralFrontierLineageEdge",
    "StructuralFrontierLineageGraph",
    "StructuralFrontierLineageNode",
    "StructuralFrontierLineageNodeKind",
    "StructuralFrontierLineageRelation",
    "audit_structural_frontier_lineage",
    "build_structural_frontier_lineage",
]
