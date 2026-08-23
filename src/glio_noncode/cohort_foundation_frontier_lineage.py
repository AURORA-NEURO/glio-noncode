"""Source-to-operation lineage graph for Domain 12 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_public_data import CohortFoundationFixture


class CohortFoundationLineageNodeKind(StrEnum):
    SOURCE = "source"
    FIXTURE = "fixture"
    RECORD = "record"
    EXECUTION = "execution"


@dataclass(frozen=True, slots=True)
class CohortFoundationLineageNode:
    node_id: str
    kind: CohortFoundationLineageNodeKind
    label: str
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationLineageEdge:
    edge_id: str
    parent_id: str
    child_id: str
    relation: str
    source_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationLineageGraph:
    nodes: tuple[CohortFoundationLineageNode, ...]
    edges: tuple[CohortFoundationLineageEdge, ...]
    roots: tuple[str, ...]
    content_address: str

    def children_of(self, node_id: str) -> tuple[str, ...]:
        return tuple(item.child_id for item in self.edges if item.parent_id == node_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_lineage(fixture: CohortFoundationFixture, evaluation: CohortFoundationEvaluation) -> CohortFoundationLineageGraph:
    nodes: list[CohortFoundationLineageNode] = []
    edges: list[CohortFoundationLineageEdge] = []
    nodes.append(CohortFoundationLineageNode(fixture.fixture_id, CohortFoundationLineageNodeKind.FIXTURE, "public aggregate fixture", fixture.context_key, content_hash((fixture.fixture_id, fixture.context_key))))
    for source in fixture.sources:
        nodes.append(CohortFoundationLineageNode(source.source_id, CohortFoundationLineageNodeKind.SOURCE, source.title, source.context_key, content_hash(source.to_dict())))
        body = (source.source_id, fixture.fixture_id, "contributes_source")
        edges.append(CohortFoundationLineageEdge(content_hash(body, prefix="edge"), source.source_id, fixture.fixture_id, "contributes_source", (source.source_id,), content_hash(body)))
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        nodes.append(CohortFoundationLineageNode(record.record_id, CohortFoundationLineageNodeKind.RECORD, record.description, record.context_key, record.content_address or content_hash(record.to_dict())))
        nodes.append(CohortFoundationLineageNode(execution.record_id + ":execution", CohortFoundationLineageNodeKind.EXECUTION, execution.actual_state, fixture.context_key, execution.content_address))
        body = (fixture.fixture_id, record.record_id, "contains_record")
        edges.append(CohortFoundationLineageEdge(content_hash(body, prefix="edge"), fixture.fixture_id, record.record_id, "contains_record", record.source_ids, content_hash(body)))
        body = (record.record_id, execution.record_id + ":execution", "evaluated_as")
        edges.append(CohortFoundationLineageEdge(content_hash(body, prefix="edge"), record.record_id, execution.record_id + ":execution", "evaluated_as", record.source_ids, content_hash(body)))
    body = {"nodes": nodes, "edges": edges, "roots": (fixture.fixture_id,)}
    return CohortFoundationLineageGraph(tuple(nodes), tuple(edges), (fixture.fixture_id,), content_hash(body))


__all__ = ["CohortFoundationLineageEdge", "CohortFoundationLineageGraph", "CohortFoundationLineageNode", "CohortFoundationLineageNodeKind", "build_cohort_foundation_frontier_lineage"]
