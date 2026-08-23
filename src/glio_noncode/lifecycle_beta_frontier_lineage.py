"""Source, execution, and review lineage for the beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierLineageEdge:
    edge_id: str
    source_node: str
    target_node: str
    relation: str
    active: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierLineageReport:
    fixture_id: str
    node_ids: tuple[str, ...]
    edges: tuple[LifecycleBetaFrontierLineageEdge, ...]
    source_ids: tuple[str, ...]
    execution_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_lineage(fixture: LifecycleBetaFrontierFixture, evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierLineageReport:
    nodes = ["fixture:" + fixture.fixture_id]
    edges = []
    for source in fixture.sources:
        source_node = "source:" + source.source_id
        nodes.append(source_node)
        body = {"source_node": source_node, "target_node": nodes[0], "relation": "declared_source", "active": True}
        edges.append(LifecycleBetaFrontierLineageEdge(content_hash(body, prefix="edge"), source_node, nodes[0], "declared_source", True, content_hash(body)))
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        record_node = "record:" + record.record_id
        execution_node = "execution:" + execution.record_id
        nodes.extend((record_node, execution_node))
        body = {"source_node": record_node, "target_node": execution_node, "relation": "executed_as", "active": True}
        edges.append(LifecycleBetaFrontierLineageEdge(content_hash(body, prefix="edge"), record_node, execution_node, "executed_as", True, content_hash(body)))
        for source_id in record.source_ids:
            source_node = "source:" + source_id
            body = {"source_node": source_node, "target_node": record_node, "relation": "supports_record", "active": True}
            edges.append(LifecycleBetaFrontierLineageEdge(content_hash(body, prefix="edge"), source_node, record_node, "supports_record", True, content_hash(body)))
    return LifecycleBetaFrontierLineageReport(fixture.fixture_id, tuple(dict.fromkeys(nodes)), tuple(edges), tuple(item.source_id for item in fixture.sources), tuple(item.record_id for item in evaluation.executions), content_hash({"nodes": tuple(nodes), "edges": tuple(edges)}))


def verify_lifecycle_beta_frontier_lineage(report: LifecycleBetaFrontierLineageReport) -> bool:
    return bool(report.node_ids) and bool(report.edges) and len({item.edge_id for item in report.edges}) == len(report.edges) and all(item.content_address.startswith("sha256:") for item in report.edges)


__all__ = ["LifecycleBetaFrontierLineageEdge", "LifecycleBetaFrontierLineageReport", "build_lifecycle_beta_frontier_lineage", "verify_lifecycle_beta_frontier_lineage"]
