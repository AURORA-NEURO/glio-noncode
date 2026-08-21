"""Sanitized source-to-result lineage graph for Domain 03 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_frontier_fixture_eval import (
    SpecimenFrontierFixtureEvaluationReport,
    evaluate_specimen_frontier_fixture,
)
from .specimen_frontier_public_data import (
    SpecimenFrontierFixtureCatalog,
    SpecimenFrontierFixtureState,
)


class SpecimenFrontierLineageNodeKind(StrEnum):
    """Typed node classes in the C01-C04 evidence graph."""

    SOURCE = "source"
    FIXTURE = "fixture"
    RECORD = "record"
    RESULT = "result"


class SpecimenFrontierLineageRelation(StrEnum):
    """Typed relationships in the C01-C04 evidence graph."""

    DECLARES = "declares"
    CONTAINS = "contains"
    PRODUCES = "produces"


@dataclass(frozen=True, slots=True)
class SpecimenFrontierLineageNode:
    """A sanitized graph node with no raw operation payload."""

    node_id: str
    kind: SpecimenFrontierLineageNodeKind
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
            raise ValidationError("specimen frontier lineage context requires six fields")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("specimen frontier lineage node must be addressed")
        if self.kind == SpecimenFrontierLineageNodeKind.SOURCE and not self.source_id:
            raise ValidationError("specimen frontier source node requires source_id")
        if (
            self.kind
            in {SpecimenFrontierLineageNodeKind.RECORD, SpecimenFrontierLineageNodeKind.RESULT}
            and not self.record_id
        ):
            raise ValidationError("specimen frontier record/result node requires record_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierLineageEdge:
    """A content-addressed relationship between two graph nodes."""

    edge_id: str
    from_node: str
    to_node: str
    relation: SpecimenFrontierLineageRelation
    content_address: str

    def __post_init__(self) -> None:
        for field_name in ("edge_id", "from_node", "to_node", "content_address"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.from_node == self.to_node:
            raise ValidationError("specimen frontier lineage edge cannot self-reference")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("specimen frontier lineage edge must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierLineageGraph:
    """Sanitized graph for one C01-C04 fixture."""

    graph_id: str
    fixture_id: str
    context_key: str
    state: SpecimenFrontierFixtureState
    source_ids: tuple[str, ...]
    nodes: tuple[SpecimenFrontierLineageNode, ...]
    edges: tuple[SpecimenFrontierLineageEdge, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field_name in ("graph_id", "fixture_id", "context_key", "content_address"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("specimen frontier lineage graph context requires six fields")
        if not self.nodes:
            raise ValidationError("specimen frontier lineage graph requires nodes")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("specimen frontier lineage graph must be addressed")

    @property
    def accepted(self) -> bool:
        return self.state == SpecimenFrontierFixtureState.ACCEPTED

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(node.node_id for node in self.nodes)

    @property
    def root_ids(self) -> tuple[str, ...]:
        incoming = {edge.to_node for edge in self.edges}
        return tuple(node.node_id for node in self.nodes if node.node_id not in incoming)

    def node(self, node_id: str) -> SpecimenFrontierLineageNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise ValidationError(f"unknown specimen frontier lineage node: {node_id}")

    def children(self, node_id: str) -> tuple[str, ...]:
        self.node(node_id)
        return tuple(edge.to_node for edge in self.edges if edge.from_node == node_id)

    def verify(self) -> bool:
        node_ids = set(self.node_ids)
        if len(node_ids) != len(self.nodes):
            return False
        if any(
            edge.from_node not in node_ids or edge.to_node not in node_ids for edge in self.edges
        ):
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
class SpecimenFrontierLineageAudit:
    """Audit result for graph addresses, endpoints, and source coverage."""

    graph_id: str
    fixture_id: str
    state: SpecimenFrontierFixtureState
    issue_codes: tuple[str, ...]
    node_count: int
    edge_count: int
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == SpecimenFrontierFixtureState.ACCEPTED and not self.issue_codes

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


class SpecimenFrontierLineageBuilder:
    """Build and audit a deterministic four-layer source graph."""

    def build(
        self,
        fixture: SpecimenFrontierFixtureCatalog | str,
        *,
        evaluation: SpecimenFrontierFixtureEvaluationReport | None = None,
        graph_id: str | None = None,
    ) -> SpecimenFrontierLineageGraph:
        catalog = (
            SpecimenFrontierFixtureCatalog.from_file(fixture)
            if isinstance(fixture, str)
            else fixture
        )
        report = evaluation or evaluate_specimen_frontier_fixture(catalog)
        receipt_by_id = {receipt.record_id: receipt for receipt in report.receipts}
        nodes: list[SpecimenFrontierLineageNode] = []
        edges: list[SpecimenFrontierLineageEdge] = []
        for source in catalog.sources:
            node_id = f"source:{source.source_id}"
            source_body = {
                "node_id": node_id,
                "kind": SpecimenFrontierLineageNodeKind.SOURCE,
                "source_id": source.source_id,
                "label": source.label,
                "release": source.release,
                "context_key": catalog.context_key,
            }
            nodes.append(
                SpecimenFrontierLineageNode(
                    node_id=node_id,
                    kind=SpecimenFrontierLineageNodeKind.SOURCE,
                    label=source.label,
                    state=SpecimenFrontierFixtureState.ACCEPTED.value,
                    context_key=catalog.context_key,
                    content_address=content_hash(source_body),
                    source_id=source.source_id,
                )
            )
        fixture_node_id = f"fixture:{catalog.fixture_id}"
        nodes.append(
            SpecimenFrontierLineageNode(
                node_id=fixture_node_id,
                kind=SpecimenFrontierLineageNodeKind.FIXTURE,
                label=catalog.fixture_id,
                state=(
                    SpecimenFrontierFixtureState.ACCEPTED.value
                    if report.passed
                    else SpecimenFrontierFixtureState.REVIEW.value
                ),
                context_key=catalog.context_key,
                content_address=catalog.content_address,
            )
        )
        for record in catalog.positives + catalog.controls:
            receipt = receipt_by_id[record.record_id]
            record_node_id = f"record:{record.record_id}"
            record_body = {
                "node_id": record_node_id,
                "kind": SpecimenFrontierLineageNodeKind.RECORD,
                "record_id": record.record_id,
                "operation": record.operation,
                "expected_state": record.expected_state,
                "expected_result_state": record.expected_result_state,
                "context_key": record.context_key,
                "source_id": record.source_id,
            }
            nodes.append(
                SpecimenFrontierLineageNode(
                    node_id=record_node_id,
                    kind=SpecimenFrontierLineageNodeKind.RECORD,
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
                SpecimenFrontierLineageNode(
                    node_id=result_node_id,
                    kind=SpecimenFrontierLineageNodeKind.RESULT,
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
                    _edge(
                        f"source:{record.source_id}",
                        record_node_id,
                        SpecimenFrontierLineageRelation.DECLARES,
                    ),
                    _edge(
                        fixture_node_id,
                        record_node_id,
                        SpecimenFrontierLineageRelation.CONTAINS,
                    ),
                    _edge(
                        record_node_id,
                        result_node_id,
                        SpecimenFrontierLineageRelation.PRODUCES,
                    ),
                )
            )
        selected_graph_id = require_non_empty(
            graph_id or f"{catalog.fixture_id}-lineage", "graph_id"
        )
        sorted_nodes = tuple(sorted(nodes, key=lambda node: node.node_id))
        sorted_edges = tuple(sorted(edges, key=lambda edge: edge.edge_id))
        body = {
            "graph_id": selected_graph_id,
            "fixture_id": catalog.fixture_id,
            "context_key": catalog.context_key,
            "state": (
                SpecimenFrontierFixtureState.ACCEPTED
                if report.passed
                else SpecimenFrontierFixtureState.REVIEW
            ),
            "source_ids": catalog.source_ids,
            "nodes": sorted_nodes,
            "edges": sorted_edges,
        }
        return SpecimenFrontierLineageGraph(
            graph_id=selected_graph_id,
            fixture_id=catalog.fixture_id,
            context_key=catalog.context_key,
            state=body["state"],
            source_ids=catalog.source_ids,
            nodes=sorted_nodes,
            edges=sorted_edges,
            content_address=content_hash(body),
        )

    def audit(self, graph: SpecimenFrontierLineageGraph) -> SpecimenFrontierLineageAudit:
        issues: set[str] = set()
        if not graph.verify():
            issues.add("graph_address_or_endpoint_invalid")
        source_nodes = {
            node.source_id
            for node in graph.nodes
            if node.kind == SpecimenFrontierLineageNodeKind.SOURCE
        }
        if source_nodes != set(graph.source_ids):
            issues.add("source_coverage")
        if not any(node.kind == SpecimenFrontierLineageNodeKind.FIXTURE for node in graph.nodes):
            issues.add("fixture_node_missing")
        record_nodes = {
            node.record_id
            for node in graph.nodes
            if node.kind == SpecimenFrontierLineageNodeKind.RECORD
        }
        result_nodes = {
            node.record_id
            for node in graph.nodes
            if node.kind == SpecimenFrontierLineageNodeKind.RESULT
        }
        if record_nodes != result_nodes:
            issues.add("record_result_mismatch")
        if any(node.context_key != graph.context_key for node in graph.nodes):
            issues.add("context_mismatch")
        if any(
            node.kind == SpecimenFrontierLineageNodeKind.RECORD
            and node.source_id not in source_nodes
            for node in graph.nodes
        ):
            issues.add("record_source_missing")
        state = (
            SpecimenFrontierFixtureState.ACCEPTED
            if not issues
            else SpecimenFrontierFixtureState.REVIEW
        )
        body = {
            "graph_id": graph.graph_id,
            "fixture_id": graph.fixture_id,
            "state": state,
            "issues": tuple(sorted(issues)),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
        }
        return SpecimenFrontierLineageAudit(
            graph_id=graph.graph_id,
            fixture_id=graph.fixture_id,
            state=state,
            issue_codes=tuple(sorted(issues)),
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            content_address=content_hash(body),
        )


def build_specimen_frontier_lineage(
    fixture: SpecimenFrontierFixtureCatalog | str,
    *,
    evaluation: SpecimenFrontierFixtureEvaluationReport | None = None,
    graph_id: str | None = None,
) -> SpecimenFrontierLineageGraph:
    """Build a deterministic C01-C04 lineage graph."""

    return SpecimenFrontierLineageBuilder().build(
        fixture,
        evaluation=evaluation,
        graph_id=graph_id,
    )


def audit_specimen_frontier_lineage(
    graph: SpecimenFrontierLineageGraph,
) -> SpecimenFrontierLineageAudit:
    """Audit an already-built C01-C04 lineage graph."""

    return SpecimenFrontierLineageBuilder().audit(graph)


def _edge(
    source: str,
    target: str,
    relation: SpecimenFrontierLineageRelation,
) -> SpecimenFrontierLineageEdge:
    edge_id = f"{relation.value}:{source}->{target}"
    body = {
        "edge_id": edge_id,
        "from_node": source,
        "to_node": target,
        "relation": relation,
    }
    return SpecimenFrontierLineageEdge(
        edge_id=edge_id,
        from_node=source,
        to_node=target,
        relation=relation,
        content_address=content_hash(body),
    )


def _graph_body(graph: SpecimenFrontierLineageGraph) -> dict[str, Any]:
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
    "SpecimenFrontierLineageAudit",
    "SpecimenFrontierLineageBuilder",
    "SpecimenFrontierLineageEdge",
    "SpecimenFrontierLineageGraph",
    "SpecimenFrontierLineageNode",
    "SpecimenFrontierLineageNodeKind",
    "SpecimenFrontierLineageRelation",
    "audit_specimen_frontier_lineage",
    "build_specimen_frontier_lineage",
]
