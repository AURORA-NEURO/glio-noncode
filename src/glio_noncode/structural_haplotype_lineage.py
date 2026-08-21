"""Sanitized source-to-result lineage graph for Domain 02 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .structural_haplotype_fixture_eval import (
    StructuralHaplotypeFixtureEvaluationReport,
    evaluate_structural_haplotype_fixture,
)
from .structural_haplotype_public_data import (
    StructuralHaplotypeFixtureCatalog,
    StructuralHaplotypeFixtureState,
)


class StructuralHaplotypeLineageNodeKind(StrEnum):
    """Typed vertices in the C09-C12 source-to-result graph."""

    SOURCE = "source"
    FIXTURE = "fixture"
    RECORD = "record"
    RESULT = "result"


class StructuralHaplotypeLineageRelation(StrEnum):
    """Typed relationships in the lineage graph."""

    DECLARES = "declares"
    CONTAINS = "contains"
    PRODUCES = "produces"


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeLineageNode:
    """A sanitized lineage node with no raw operation payload."""

    node_id: str
    kind: StructuralHaplotypeLineageNodeKind
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
            raise ValidationError("structural haplotype lineage context requires six fields")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("structural haplotype lineage node must be addressed")
        if self.kind == StructuralHaplotypeLineageNodeKind.SOURCE and not self.source_id:
            raise ValidationError("structural haplotype source node requires source_id")
        if self.kind in {StructuralHaplotypeLineageNodeKind.RECORD, StructuralHaplotypeLineageNodeKind.RESULT} and not self.record_id:
            raise ValidationError("structural haplotype record/result node requires record_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeLineageEdge:
    """A content-addressed relationship between two lineage nodes."""

    edge_id: str
    from_node: str
    to_node: str
    relation: StructuralHaplotypeLineageRelation
    content_address: str

    def __post_init__(self) -> None:
        for field_name in ("edge_id", "from_node", "to_node", "content_address"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.from_node == self.to_node:
            raise ValidationError("structural haplotype lineage edge cannot self-reference")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("structural haplotype lineage edge must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeLineageGraph:
    """Sanitized graph for one C09-C12 fixture."""

    graph_id: str
    fixture_id: str
    context_key: str
    state: StructuralHaplotypeFixtureState
    source_ids: tuple[str, ...]
    nodes: tuple[StructuralHaplotypeLineageNode, ...]
    edges: tuple[StructuralHaplotypeLineageEdge, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field_name in ("graph_id", "fixture_id", "context_key", "content_address"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("structural haplotype lineage graph context requires six fields")
        if not self.nodes:
            raise ValidationError("structural haplotype lineage graph requires nodes")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("structural haplotype lineage graph must be addressed")

    @property
    def accepted(self) -> bool:
        return self.state == StructuralHaplotypeFixtureState.ACCEPTED

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(node.node_id for node in self.nodes)

    @property
    def edge_ids(self) -> tuple[str, ...]:
        return tuple(edge.edge_id for edge in self.edges)

    @property
    def root_ids(self) -> tuple[str, ...]:
        destinations = {edge.to_node for edge in self.edges}
        return tuple(sorted(node_id for node_id in self.node_ids if node_id not in destinations))

    def children(self, node_id: str) -> tuple[str, ...]:
        require_non_empty(node_id, "node_id")
        if node_id not in self.node_ids:
            raise ValidationError(f"unknown structural haplotype lineage node: {node_id}")
        return tuple(sorted(edge.to_node for edge in self.edges if edge.from_node == node_id))

    def node(self, node_id: str) -> StructuralHaplotypeLineageNode:
        matches = tuple(node for node in self.nodes if node.node_id == node_id)
        if len(matches) != 1:
            raise ValidationError(f"structural haplotype lineage node lookup failed: {node_id}")
        return matches[0]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "root_ids": self.root_ids,
        }

    def verify(self) -> bool:
        if len(self.node_ids) != len(set(self.node_ids)):
            return False
        if len(self.edge_ids) != len(set(self.edge_ids)):
            return False
        if any(edge.from_node not in self.node_ids or edge.to_node not in self.node_ids for edge in self.edges):
            return False
        return self.content_address == content_hash(_graph_body(self))


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeLineageAudit:
    """Independent checks over a C09-C12 lineage graph."""

    graph_id: str
    fixture_id: str
    state: StructuralHaplotypeFixtureState
    issue_codes: tuple[str, ...]
    node_count: int
    edge_count: int
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == StructuralHaplotypeFixtureState.ACCEPTED and not self.issue_codes

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


class StructuralHaplotypeLineageBuilder:
    """Construct and audit a sanitized C09-C12 lineage graph."""

    def build(
        self,
        fixture: StructuralHaplotypeFixtureCatalog | str,
        *,
        evaluation: StructuralHaplotypeFixtureEvaluationReport | None = None,
        graph_id: str | None = None,
    ) -> StructuralHaplotypeLineageGraph:
        catalog = StructuralHaplotypeFixtureCatalog.from_file(fixture) if isinstance(fixture, str) else fixture
        report = evaluation or evaluate_structural_haplotype_fixture(catalog)
        receipt_by_id = {receipt.record_id: receipt for receipt in report.receipts}
        nodes: list[StructuralHaplotypeLineageNode] = []
        edges: list[StructuralHaplotypeLineageEdge] = []
        for source in catalog.sources:
            node_id = f"source:{source.source_id}"
            source_body = {
                "node_id": node_id,
                "kind": StructuralHaplotypeLineageNodeKind.SOURCE,
                "source_id": source.source_id,
                "title": source.title,
                "version": source.version,
                "scope": source.data_scope,
                "context_key": catalog.context_key,
            }
            nodes.append(
                StructuralHaplotypeLineageNode(
                    node_id=node_id,
                    kind=StructuralHaplotypeLineageNodeKind.SOURCE,
                    label=source.title,
                    state=StructuralHaplotypeFixtureState.ACCEPTED.value,
                    context_key=catalog.context_key,
                    content_address=content_hash(source_body),
                    source_id=source.source_id,
                )
            )
        fixture_node_id = f"fixture:{catalog.fixture_id}"
        nodes.append(
            StructuralHaplotypeLineageNode(
                node_id=fixture_node_id,
                kind=StructuralHaplotypeLineageNodeKind.FIXTURE,
                label=catalog.fixture_id,
                state=StructuralHaplotypeFixtureState.ACCEPTED.value if report.passed else StructuralHaplotypeFixtureState.REVIEW.value,
                context_key=catalog.context_key,
                content_address=catalog.content_address,
            )
        )
        for record in catalog.positives + catalog.controls:
            receipt = receipt_by_id[record.record_id]
            record_node_id = f"record:{record.record_id}"
            record_body = {
                "node_id": record_node_id,
                "kind": StructuralHaplotypeLineageNodeKind.RECORD,
                "record_id": record.record_id,
                "operation": record.operation,
                "expected_state": record.expected_state,
                "expected_result_state": record.expected_result_state,
                "context_key": record.context_key,
                "source_id": record.source_id,
            }
            nodes.append(
                StructuralHaplotypeLineageNode(
                    node_id=record_node_id,
                    kind=StructuralHaplotypeLineageNodeKind.RECORD,
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
                StructuralHaplotypeLineageNode(
                    node_id=result_node_id,
                    kind=StructuralHaplotypeLineageNodeKind.RESULT,
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
                    _edge(f"source:{record.source_id}", record_node_id, StructuralHaplotypeLineageRelation.DECLARES),
                    _edge(fixture_node_id, record_node_id, StructuralHaplotypeLineageRelation.CONTAINS),
                    _edge(record_node_id, result_node_id, StructuralHaplotypeLineageRelation.PRODUCES),
                )
            )
        selected_graph_id = require_non_empty(graph_id or f"{catalog.fixture_id}-lineage", "graph_id")
        sorted_nodes = tuple(sorted(nodes, key=lambda node: node.node_id))
        sorted_edges = tuple(sorted(edges, key=lambda edge: edge.edge_id))
        body = {
            "graph_id": selected_graph_id,
            "fixture_id": catalog.fixture_id,
            "context_key": catalog.context_key,
            "state": StructuralHaplotypeFixtureState.ACCEPTED if report.passed else StructuralHaplotypeFixtureState.REVIEW,
            "source_ids": catalog.source_ids,
            "nodes": sorted_nodes,
            "edges": sorted_edges,
        }
        return StructuralHaplotypeLineageGraph(
            graph_id=selected_graph_id,
            fixture_id=catalog.fixture_id,
            context_key=catalog.context_key,
            state=body["state"],
            source_ids=catalog.source_ids,
            nodes=sorted_nodes,
            edges=sorted_edges,
            content_address=content_hash(body),
        )

    def audit(self, graph: StructuralHaplotypeLineageGraph) -> StructuralHaplotypeLineageAudit:
        issues: set[str] = set()
        if not graph.verify():
            issues.add("graph_address_or_endpoint_invalid")
        source_nodes = {node.source_id for node in graph.nodes if node.kind == StructuralHaplotypeLineageNodeKind.SOURCE}
        if source_nodes != set(graph.source_ids):
            issues.add("source_coverage")
        if not any(node.kind == StructuralHaplotypeLineageNodeKind.FIXTURE for node in graph.nodes):
            issues.add("fixture_node_missing")
        record_nodes = {node.record_id for node in graph.nodes if node.kind == StructuralHaplotypeLineageNodeKind.RECORD}
        result_nodes = {node.record_id for node in graph.nodes if node.kind == StructuralHaplotypeLineageNodeKind.RESULT}
        if record_nodes != result_nodes:
            issues.add("record_result_mismatch")
        if any(node.context_key != graph.context_key for node in graph.nodes):
            issues.add("context_mismatch")
        if any(node.kind == StructuralHaplotypeLineageNodeKind.RECORD and node.source_id not in source_nodes for node in graph.nodes):
            issues.add("record_source_missing")
        state = StructuralHaplotypeFixtureState.ACCEPTED if not issues else StructuralHaplotypeFixtureState.REVIEW
        body = {
            "graph_id": graph.graph_id,
            "fixture_id": graph.fixture_id,
            "state": state,
            "issues": tuple(sorted(issues)),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
        }
        return StructuralHaplotypeLineageAudit(
            graph_id=graph.graph_id,
            fixture_id=graph.fixture_id,
            state=state,
            issue_codes=tuple(sorted(issues)),
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            content_address=content_hash(body),
        )


def build_structural_haplotype_lineage(
    fixture: StructuralHaplotypeFixtureCatalog | str,
    *,
    evaluation: StructuralHaplotypeFixtureEvaluationReport | None = None,
    graph_id: str | None = None,
) -> StructuralHaplotypeLineageGraph:
    """Build a deterministic C09-C12 lineage graph."""

    return StructuralHaplotypeLineageBuilder().build(fixture, evaluation=evaluation, graph_id=graph_id)


def audit_structural_haplotype_lineage(graph: StructuralHaplotypeLineageGraph) -> StructuralHaplotypeLineageAudit:
    """Audit an already-built C09-C12 lineage graph."""

    return StructuralHaplotypeLineageBuilder().audit(graph)


def _edge(source: str, target: str, relation: StructuralHaplotypeLineageRelation) -> StructuralHaplotypeLineageEdge:
    edge_id = f"{relation.value}:{source}->{target}"
    body = {"edge_id": edge_id, "from_node": source, "to_node": target, "relation": relation}
    return StructuralHaplotypeLineageEdge(
        edge_id=edge_id,
        from_node=source,
        to_node=target,
        relation=relation,
        content_address=content_hash(body),
    )


def _graph_body(graph: StructuralHaplotypeLineageGraph) -> dict[str, Any]:
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
    "StructuralHaplotypeLineageAudit",
    "StructuralHaplotypeLineageBuilder",
    "StructuralHaplotypeLineageEdge",
    "StructuralHaplotypeLineageGraph",
    "StructuralHaplotypeLineageNode",
    "StructuralHaplotypeLineageNodeKind",
    "StructuralHaplotypeLineageRelation",
    "audit_structural_haplotype_lineage",
    "build_structural_haplotype_lineage",
]
