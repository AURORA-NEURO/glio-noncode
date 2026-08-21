"""Sanitized source-to-result lineage graph for Domain 03 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .specimen_lineage_fixture_eval import evaluate_specimen_lineage_fixture
from .specimen_lineage_public_data import SpecimenLineageFixtureCatalog


class SpecimenLineageNodeKind(StrEnum):
    SOURCE = "source"
    FIXTURE = "fixture"
    RECORD = "record"
    RESULT = "result"


class SpecimenLineageRelation(StrEnum):
    DECLARES = "declares"
    CONTAINS = "contains"
    PRODUCES = "produces"


@dataclass(frozen=True, slots=True)
class SpecimenLineageNode:
    """One source, fixture, record, or sanitized result vertex."""

    node_id: str
    kind: SpecimenLineageNodeKind
    context_key: str
    content_address: str
    source_id: str | None = None
    record_id: str | None = None
    operation: str | None = None
    state: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.node_id, "lineage node ID")
        require_non_empty(self.context_key, "lineage node context")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("lineage node address must be sha256-prefixed")
        if self.kind == SpecimenLineageNodeKind.SOURCE and not self.source_id:
            raise ValueError("lineage source node requires source_id")
        if (
            self.kind in {SpecimenLineageNodeKind.RECORD, SpecimenLineageNodeKind.RESULT}
            and not self.record_id
        ):
            raise ValueError("lineage record/result node requires record_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenLineageEdge:
    """Typed directed relation between two graph vertices."""

    edge_id: str
    from_node: str
    to_node: str
    relation: SpecimenLineageRelation

    def __post_init__(self) -> None:
        for name in ("edge_id", "from_node", "to_node"):
            require_non_empty(str(getattr(self, name)), f"lineage edge {name}")
        if self.from_node == self.to_node:
            raise ValueError("lineage edge cannot be self-referential")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenLineageGraph:
    """Complete sanitized evidence graph for one fixture run."""

    fixture_id: str
    context_key: str
    nodes: tuple[SpecimenLineageNode, ...]
    edges: tuple[SpecimenLineageEdge, ...]
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
class SpecimenLineageGraphAuditReport:
    """Graph integrity result."""

    fixture_id: str
    passed: bool
    issue_codes: tuple[str, ...]
    node_count: int
    edge_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_specimen_lineage_lineage(
    catalog: SpecimenLineageFixtureCatalog,
) -> SpecimenLineageGraph:
    """Build a graph without copying raw input payloads."""

    evaluation = evaluate_specimen_lineage_fixture(catalog)
    nodes: list[SpecimenLineageNode] = []
    edges: list[SpecimenLineageEdge] = []
    fixture_node = "fixture:" + catalog.fixture_id
    for source in catalog.sources:
        nodes.append(
            SpecimenLineageNode(
                node_id="source:" + source.source_id,
                kind=SpecimenLineageNodeKind.SOURCE,
                context_key=catalog.context_key,
                content_address=content_hash(source),
                source_id=source.source_id,
            )
        )
        edges.append(
            _edge(
                "source:" + source.source_id,
                fixture_node,
                SpecimenLineageRelation.DECLARES,
            )
        )
    nodes.append(
        SpecimenLineageNode(
            node_id=fixture_node,
            kind=SpecimenLineageNodeKind.FIXTURE,
            context_key=catalog.context_key,
            content_address=catalog.content_address,
        )
    )
    receipts_by_id = {receipt.record_id: receipt for receipt in evaluation.receipts}
    for record in catalog.records:
        receipt = receipts_by_id[record.record_id]
        record_node = "record:" + record.record_id
        result_node = "result:" + record.record_id
        nodes.append(
            SpecimenLineageNode(
                node_id=record_node,
                kind=SpecimenLineageNodeKind.RECORD,
                context_key=record.context_key,
                content_address=record.content_address,
                record_id=record.record_id,
                operation=record.operation.value,
                state=record.expected_fixture_state.value,
            )
        )
        nodes.append(
            SpecimenLineageNode(
                node_id=result_node,
                kind=SpecimenLineageNodeKind.RESULT,
                context_key=record.context_key,
                content_address=receipt.output_address,
                record_id=record.record_id,
                operation=record.operation.value,
                state=receipt.observed_result_state,
            )
        )
        edges.append(_edge(fixture_node, record_node, SpecimenLineageRelation.CONTAINS))
        edges.append(_edge(record_node, result_node, SpecimenLineageRelation.PRODUCES))
    nodes = sorted(nodes, key=lambda item: item.node_id)
    edges = sorted(edges, key=lambda item: item.edge_id)
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "nodes": nodes,
        "edges": edges,
    }
    return SpecimenLineageGraph(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        nodes=tuple(nodes),
        edges=tuple(edges),
        content_address=content_hash(body),
    )


def audit_specimen_lineage_lineage(graph: SpecimenLineageGraph) -> SpecimenLineageGraphAuditReport:
    """Audit graph identity, references, shape, and sanitized fields."""

    issues: set[str] = set()
    node_ids = set(graph.node_ids)
    edge_ids = set(graph.edge_ids)
    if len(node_ids) != len(graph.nodes):
        issues.add("duplicate_node_id")
    if len(edge_ids) != len(graph.edges):
        issues.add("duplicate_edge_id")
    if any(edge.from_node not in node_ids or edge.to_node not in node_ids for edge in graph.edges):
        issues.add("dangling_edge")
    if len(graph.nodes) != 29:
        issues.add("node_shape")
    if len(graph.edges) != 28:
        issues.add("edge_shape")
    if sum(node.kind == SpecimenLineageNodeKind.SOURCE for node in graph.nodes) != 4:
        issues.add("source_shape")
    if sum(node.kind == SpecimenLineageNodeKind.RECORD for node in graph.nodes) != 12:
        issues.add("record_shape")
    if sum(node.kind == SpecimenLineageNodeKind.RESULT for node in graph.nodes) != 12:
        issues.add("result_shape")
    if any(node.context_key != graph.context_key for node in graph.nodes):
        issues.add("context_drift")
    if any(not node.content_address.startswith("sha256:") for node in graph.nodes):
        issues.add("node_address")
    if any(not edge.edge_id.startswith("edge:") for edge in graph.edges):
        issues.add("edge_address")
    serialized = graph.to_dict()
    if _forbidden_keys(serialized):
        issues.add("raw_payload_boundary")
    body = {
        "fixture_id": graph.fixture_id,
        "passed": not issues,
        "issue_codes": tuple(sorted(issues)),
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
    }
    return SpecimenLineageGraphAuditReport(
        fixture_id=graph.fixture_id,
        passed=not issues,
        issue_codes=tuple(sorted(issues)),
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
        content_address=content_hash(body),
    )


def _edge(from_node: str, to_node: str, relation: SpecimenLineageRelation) -> SpecimenLineageEdge:
    body = {"from_node": from_node, "to_node": to_node, "relation": relation}
    return SpecimenLineageEdge(
        edge_id="edge:" + content_hash(body).split(":", 1)[1][:24],
        from_node=from_node,
        to_node=to_node,
        relation=relation,
    )


def _forbidden_keys(value: Any) -> tuple[str, ...]:
    forbidden = {
        "records",
        "raw_records",
        "patient_id",
        "subject_id",
        "medical_record_number",
        "sample_patient_id",
        "participant_id",
        "case_uuid",
        "individual_id",
        "person_id",
    }
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in forbidden:
                found.add(normalized)
            found.update(_forbidden_keys(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found.update(_forbidden_keys(nested))
    return tuple(sorted(found))


__all__ = [
    "SpecimenLineageEdge",
    "SpecimenLineageGraph",
    "SpecimenLineageGraphAuditReport",
    "SpecimenLineageNode",
    "SpecimenLineageNodeKind",
    "SpecimenLineageRelation",
    "audit_specimen_lineage_lineage",
    "build_specimen_lineage_lineage",
]
