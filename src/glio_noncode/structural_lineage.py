"""Content-addressed lineage graph for the Domain 02 structural evidence stack.

The structural adapters intentionally return compact operation receipts rather
than carrying raw observation payloads into downstream reports.  A receipt is
useful for verification, but reviewers also need to see how a public source,
fixture record, and result relate to one another.  This module supplies that
missing graph without copying sensitive or high-volume payload fields.

The graph is deliberately small and deterministic:

* source nodes identify public aggregate receipts;
* fixture nodes identify the versioned catalog;
* record nodes identify positive operations and review controls;
* result nodes identify the content-addressed adapter output; and
* typed edges make every relationship explicit.

Every node and edge is independently addressable.  The graph address is a
hash over the complete sanitized graph, so a changed source, record, result,
context, or relationship invalidates the published lineage receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .structural_fixture_eval import (
    StructuralFixtureEvaluationReport,
    evaluate_structural_fixture,
)
from .structural_public_data import (
    StructuralFixtureCatalog,
    StructuralFixtureState,
)


class StructuralLineageNodeKind(StrEnum):
    """Typed vertices permitted in the sanitized structural graph."""

    SOURCE = "source"
    FIXTURE = "fixture"
    RECORD = "record"
    RESULT = "result"


class StructuralLineageRelation(StrEnum):
    """Typed relationships permitted between lineage vertices."""

    DECLARES = "declares"
    CONTAINS = "contains"
    EXECUTES = "executes"
    PRODUCES = "produces"


@dataclass(frozen=True, slots=True)
class StructuralLineageNode:
    """A sanitized lineage vertex with no operation payload."""

    node_id: str
    kind: StructuralLineageNodeKind
    label: str
    state: str
    context_key: str
    content_address: str
    source_id: str | None = None
    record_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "node_id",
            "label",
            "state",
            "context_key",
            "content_address",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("structural lineage context key requires six fields")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("structural lineage node must be content-addressed")
        if self.kind == StructuralLineageNodeKind.SOURCE and not self.source_id:
            raise ValidationError("source lineage node requires source_id")
        if self.kind in {StructuralLineageNodeKind.RECORD, StructuralLineageNodeKind.RESULT} and not self.record_id:
            raise ValidationError("record and result lineage nodes require record_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralLineageEdge:
    """A content-addressed relationship between two existing nodes."""

    edge_id: str
    from_node: str
    to_node: str
    relation: StructuralLineageRelation
    content_address: str

    def __post_init__(self) -> None:
        for field_name in ("edge_id", "from_node", "to_node", "content_address"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.from_node == self.to_node:
            raise ValidationError("structural lineage edge cannot be self-referential")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("structural lineage edge must be content-addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralLineageGraph:
    """Sanitized source-to-result graph for one structural fixture."""

    graph_id: str
    fixture_id: str
    context_key: str
    state: StructuralFixtureState
    source_ids: tuple[str, ...]
    nodes: tuple[StructuralLineageNode, ...]
    edges: tuple[StructuralLineageEdge, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field_name in ("graph_id", "fixture_id", "context_key", "content_address"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("structural lineage graph context key requires six fields")
        if not self.nodes:
            raise ValidationError("structural lineage graph requires nodes")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("structural lineage graph must be content-addressed")

    @property
    def accepted(self) -> bool:
        return self.state == StructuralFixtureState.ACCEPTED

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
        """Return deterministic direct descendants of one node."""

        require_non_empty(node_id, "node_id")
        if node_id not in self.node_ids:
            raise ValidationError(f"unknown structural lineage node: {node_id}")
        return tuple(sorted(edge.to_node for edge in self.edges if edge.from_node == node_id))

    def node(self, node_id: str) -> StructuralLineageNode:
        """Return one node by ID, rejecting ambiguous or unknown IDs."""

        matches = tuple(node for node in self.nodes if node.node_id == node_id)
        if len(matches) != 1:
            raise ValidationError(f"structural lineage node lookup failed: {node_id}")
        return matches[0]

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        result["node_count"] = len(self.nodes)
        result["edge_count"] = len(self.edges)
        result["root_ids"] = self.root_ids
        return result

    def verify(self) -> bool:
        """Verify node/edge uniqueness, endpoints, and the graph address."""

        if len(self.node_ids) != len(set(self.node_ids)):
            return False
        if len(self.edge_ids) != len(set(self.edge_ids)):
            return False
        if any(edge.from_node not in self.node_ids or edge.to_node not in self.node_ids for edge in self.edges):
            return False
        return self.content_address == content_hash(_graph_body(self))


@dataclass(frozen=True, slots=True)
class StructuralLineageAudit:
    """Independent structural checks over a lineage graph."""

    graph_id: str
    fixture_id: str
    state: StructuralFixtureState
    issue_codes: tuple[str, ...]
    node_count: int
    edge_count: int
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == StructuralFixtureState.ACCEPTED and not self.issue_codes

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        return result


class StructuralLineageBuilder:
    """Construct and audit a sanitized source-to-result lineage graph."""

    def build(
        self,
        fixture: StructuralFixtureCatalog | str,
        *,
        evaluation: StructuralFixtureEvaluationReport | None = None,
        graph_id: str | None = None,
    ) -> StructuralLineageGraph:
        catalog = StructuralFixtureCatalog.from_file(fixture) if isinstance(fixture, str) else fixture
        report = evaluation or evaluate_structural_fixture(catalog)
        receipt_by_id = {receipt.record_id: receipt for receipt in report.receipts}
        nodes: list[StructuralLineageNode] = []
        edges: list[StructuralLineageEdge] = []

        for source in catalog.sources:
            node_id = f"source:{source.source_id}"
            source_body = {
                "node_id": node_id,
                "kind": StructuralLineageNodeKind.SOURCE,
                "source_id": source.source_id,
                "title": source.title,
                "version": source.version,
                "scope": source.data_scope,
                "context_key": catalog.context_key,
            }
            nodes.append(
                StructuralLineageNode(
                    node_id=node_id,
                    kind=StructuralLineageNodeKind.SOURCE,
                    label=source.title,
                    state=StructuralFixtureState.ACCEPTED.value,
                    context_key=catalog.context_key,
                    content_address=content_hash(source_body),
                    source_id=source.source_id,
                )
            )

        fixture_node_id = f"fixture:{catalog.fixture_id}"
        nodes.append(
            StructuralLineageNode(
                node_id=fixture_node_id,
                kind=StructuralLineageNodeKind.FIXTURE,
                label=catalog.fixture_id,
                state=(
                    StructuralFixtureState.ACCEPTED.value
                    if report.passed
                    else StructuralFixtureState.REVIEW.value
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
                "kind": StructuralLineageNodeKind.RECORD,
                "record_id": record.record_id,
                "operation": record.operation,
                "expected_state": record.expected_state,
                "expected_result_state": record.expected_result_state,
                "context_key": record.context_key,
                "source_id": record.source_id,
            }
            nodes.append(
                StructuralLineageNode(
                    node_id=record_node_id,
                    kind=StructuralLineageNodeKind.RECORD,
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
                StructuralLineageNode(
                    node_id=result_node_id,
                    kind=StructuralLineageNodeKind.RESULT,
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
                    _edge(source_id=f"source:{record.source_id}", target=record_node_id, relation=StructuralLineageRelation.DECLARES),
                    _edge(source_id=fixture_node_id, target=record_node_id, relation=StructuralLineageRelation.CONTAINS),
                    _edge(source_id=record_node_id, target=result_node_id, relation=StructuralLineageRelation.PRODUCES),
                )
            )

        selected_graph_id = require_non_empty(graph_id or f"{catalog.fixture_id}-lineage", "graph_id")
        body = {
            "graph_id": selected_graph_id,
            "fixture_id": catalog.fixture_id,
            "context_key": catalog.context_key,
            "state": StructuralFixtureState.ACCEPTED if report.passed else StructuralFixtureState.REVIEW,
            "source_ids": catalog.source_ids,
            "nodes": tuple(nodes),
            "edges": tuple(edges),
        }
        return StructuralLineageGraph(
            graph_id=selected_graph_id,
            fixture_id=catalog.fixture_id,
            context_key=catalog.context_key,
            state=body["state"],
            source_ids=catalog.source_ids,
            nodes=tuple(sorted(nodes, key=lambda node: node.node_id)),
            edges=tuple(sorted(edges, key=lambda edge: edge.edge_id)),
            content_address=content_hash(
                {
                    **body,
                    "nodes": tuple(sorted(nodes, key=lambda node: node.node_id)),
                    "edges": tuple(sorted(edges, key=lambda edge: edge.edge_id)),
                }
            ),
        )

    def audit(self, graph: StructuralLineageGraph) -> StructuralLineageAudit:
        """Check graph shape, context, source coverage, and address integrity."""

        issues: set[str] = set()
        if not graph.verify():
            issues.add("graph_address_or_endpoint_invalid")
        source_nodes = {node.source_id for node in graph.nodes if node.kind == StructuralLineageNodeKind.SOURCE}
        if source_nodes != set(graph.source_ids):
            issues.add("source_coverage")
        if not any(node.kind == StructuralLineageNodeKind.FIXTURE for node in graph.nodes):
            issues.add("fixture_node_missing")
        record_nodes = {node.record_id for node in graph.nodes if node.kind == StructuralLineageNodeKind.RECORD}
        result_nodes = {node.record_id for node in graph.nodes if node.kind == StructuralLineageNodeKind.RESULT}
        if record_nodes != result_nodes:
            issues.add("record_result_mismatch")
        if any(node.context_key != graph.context_key for node in graph.nodes):
            issues.add("context_mismatch")
        if any(node.kind == StructuralLineageNodeKind.RECORD and node.source_id not in source_nodes for node in graph.nodes):
            issues.add("record_source_missing")
        state = StructuralFixtureState.ACCEPTED if not issues else StructuralFixtureState.REVIEW
        body = {
            "graph_id": graph.graph_id,
            "fixture_id": graph.fixture_id,
            "state": state,
            "issues": tuple(sorted(issues)),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
        }
        return StructuralLineageAudit(
            graph_id=graph.graph_id,
            fixture_id=graph.fixture_id,
            state=state,
            issue_codes=tuple(sorted(issues)),
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            content_address=content_hash(body),
        )


def build_structural_lineage(
    fixture: StructuralFixtureCatalog | str,
    *,
    graph_id: str | None = None,
) -> StructuralLineageGraph:
    """Build a deterministic lineage graph from a structural fixture."""

    return StructuralLineageBuilder().build(fixture, graph_id=graph_id)


def audit_structural_lineage(graph: StructuralLineageGraph) -> StructuralLineageAudit:
    """Audit an already-built structural lineage graph."""

    return StructuralLineageBuilder().audit(graph)


def _edge(source_id: str, target: str, relation: StructuralLineageRelation) -> StructuralLineageEdge:
    edge_id = f"{relation.value}:{source_id}->{target}"
    body = {"edge_id": edge_id, "from_node": source_id, "to_node": target, "relation": relation}
    return StructuralLineageEdge(
        edge_id=edge_id,
        from_node=source_id,
        to_node=target,
        relation=relation,
        content_address=content_hash(body),
    )


def _graph_body(graph: StructuralLineageGraph) -> dict[str, Any]:
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
    "StructuralLineageAudit",
    "StructuralLineageBuilder",
    "StructuralLineageEdge",
    "StructuralLineageGraph",
    "StructuralLineageNode",
    "StructuralLineageNodeKind",
    "StructuralLineageRelation",
    "audit_structural_lineage",
    "build_structural_lineage",
]
