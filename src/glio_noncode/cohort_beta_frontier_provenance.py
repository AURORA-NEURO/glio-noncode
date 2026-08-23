"""Public source provenance graph and receipt closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierProvenanceNode:
    node_id: str
    node_kind: str
    locator: str
    version: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierProvenanceEdge:
    source: str
    target: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierProvenanceGraph:
    nodes: tuple[CohortBetaFrontierProvenanceNode, ...]
    edges: tuple[CohortBetaFrontierProvenanceEdge, ...]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_provenance(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierProvenanceGraph:
    nodes = [CohortBetaFrontierProvenanceNode(fixture.fixture_id, "fixture", fixture.fixture_id, fixture.fixture_version, content_hash(fixture.fixture_id, prefix="provenance-node"))]
    edges: list[CohortBetaFrontierProvenanceEdge] = []
    for source in fixture.sources:
        nodes.append(CohortBetaFrontierProvenanceNode(source.source_id, "public_source", source.url, source.version, source.content_address))
        raw = {"source": source.source_id, "target": fixture.fixture_id, "relation": "defines_boundary"}
        edges.append(CohortBetaFrontierProvenanceEdge(source.source_id, fixture.fixture_id, "defines_boundary", content_hash(raw, prefix="provenance-edge")))
    for row in evaluation.rows:
        result_id = f"result:{row.record_id}"
        nodes.append(CohortBetaFrontierProvenanceNode(result_id, "execution_result", row.record_id, row.observed_state.value, row.content_address))
        raw = {"source": fixture.fixture_id, "target": result_id, "relation": "evaluated"}
        edges.append(CohortBetaFrontierProvenanceEdge(fixture.fixture_id, result_id, "evaluated", content_hash(raw, prefix="provenance-edge")))
    closed = bool(nodes) and len(evaluation.rows) == len(fixture.records) and all(edge.source in {node.node_id for node in nodes} and edge.target in {node.node_id for node in nodes} for edge in edges)
    body = {"nodes": nodes, "edges": edges, "closed": closed}
    return CohortBetaFrontierProvenanceGraph(tuple(nodes), tuple(edges), closed, content_hash(body, prefix="provenance"))


__all__ = ["CohortBetaFrontierProvenanceEdge", "CohortBetaFrontierProvenanceGraph", "CohortBetaFrontierProvenanceNode", "build_cohort_beta_frontier_provenance"]
