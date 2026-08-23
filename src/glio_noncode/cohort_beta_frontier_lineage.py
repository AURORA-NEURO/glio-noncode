"""Source-to-row-to-result lineage for every C05-C08 execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierLineageEdge:
    parent: str
    child: str
    relation: str
    operation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierLineage:
    fixture_id: str
    nodes: tuple[str, ...]
    edges: tuple[CohortBetaFrontierLineageEdge, ...]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_lineage(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierLineage:
    nodes = {fixture.fixture_id, *[source.source_id for source in fixture.sources]}
    edges: list[CohortBetaFrontierLineageEdge] = []
    for record in fixture.records:
        nodes.add(record.record_id)
        nodes.add(f"result:{record.record_id}")
        for source_id in record.source_ids:
            nodes.add(source_id)
            raw = {"parent": source_id, "child": record.record_id, "relation": "source_to_input", "operation": record.operation}
            edges.append(CohortBetaFrontierLineageEdge(source_id, record.record_id, "source_to_input", record.operation, content_hash(raw, prefix="lineage-edge")))
        raw = {"parent": record.record_id, "child": f"result:{record.record_id}", "relation": "input_to_result", "operation": record.operation}
        edges.append(CohortBetaFrontierLineageEdge(record.record_id, f"result:{record.record_id}", "input_to_result", record.operation, content_hash(raw, prefix="lineage-edge")))
    closed = len(evaluation.rows) == len(fixture.records) and len(edges) >= len(fixture.records) * 2
    body = {"fixture_id": fixture.fixture_id, "nodes": sorted(nodes), "edges": edges, "closed": closed}
    return CohortBetaFrontierLineage(fixture.fixture_id, tuple(sorted(nodes)), tuple(edges), closed, content_hash(body, prefix="lineage"))


def verify_cohort_beta_frontier_lineage(lineage: CohortBetaFrontierLineage) -> bool:
    return lineage.closed and all(edge.parent in lineage.nodes and edge.child in lineage.nodes for edge in lineage.edges)


__all__ = ["CohortBetaFrontierLineage", "CohortBetaFrontierLineageEdge", "build_cohort_beta_frontier_lineage", "verify_cohort_beta_frontier_lineage"]
