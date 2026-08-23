"""Source-to-record-to-execution lineage for deployment governance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierFixture
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierLineageEdge:
    parent_id: str
    child_id: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierLineage:
    node_ids: tuple[str, ...]
    edges: tuple[DeploymentFrontierLineageEdge, ...]
    root_source_ids: tuple[str, ...]
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_lineage(fixture: DeploymentFrontierFixture, evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierLineage:
    nodes = [source.source_id for source in fixture.sources]
    edges = []
    by_record = {item.record_id: item for item in fixture.records}
    for execution in evaluation.executions:
        record = by_record[execution.record_id]
        nodes.append(record.record_id)
        nodes.append(f"execution:{execution.record_id}")
        for source_id in record.source_ids:
            edge_body = {"parent_id": source_id, "child_id": record.record_id, "relation": "supports"}
            edges.append(DeploymentFrontierLineageEdge(**edge_body, content_address=deployment_address(edge_body)))
        edge_body = {"parent_id": record.record_id, "child_id": f"execution:{execution.record_id}", "relation": "executes"}
        edges.append(DeploymentFrontierLineageEdge(**edge_body, content_address=deployment_address(edge_body)))
    node_ids = tuple(dict.fromkeys(nodes))
    body = {"node_ids": node_ids, "edges": tuple(edges), "root_source_ids": tuple(source.source_id for source in fixture.sources), "complete": len(edges) >= len(evaluation.executions)}
    return DeploymentFrontierLineage(**body, content_address=deployment_address(body))


def verify_deployment_frontier_lineage(lineage: DeploymentFrontierLineage) -> tuple[str, ...]:
    issues = []
    nodes = set(lineage.node_ids)
    if any(edge.parent_id not in nodes or edge.child_id not in nodes for edge in lineage.edges):
        issues.append("orphan_lineage_edge")
    if not lineage.complete:
        issues.append("lineage_incomplete")
    return tuple(issues)


__all__ = ["DeploymentFrontierLineage", "DeploymentFrontierLineageEdge", "build_deployment_frontier_lineage", "verify_deployment_frontier_lineage"]
