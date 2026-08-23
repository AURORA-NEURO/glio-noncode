"""Source-to-record-to-execution lineage for platform receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierLineageEdge:
    edge_id: str
    parent_id: str
    child_id: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierLineage:
    fixture_id: str
    edges: tuple[PlatformFrontierLineageEdge, ...]
    node_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_lineage(fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation) -> PlatformFrontierLineage:
    edges = []
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        for source_id in record.source_ids:
            body = {"edge_id": f"{source_id}->{record.record_id}", "parent_id": source_id, "child_id": record.record_id, "relation": "supports_record"}
            edges.append(PlatformFrontierLineageEdge(**body, content_address=content_hash(body)))
        body = {"edge_id": f"{record.record_id}->{execution.record_id}", "parent_id": record.record_id, "child_id": execution.record_id, "relation": "evaluates_record"}
        edges.append(PlatformFrontierLineageEdge(**body, content_address=content_hash(body)))
    nodes = {item.source_id for item in fixture.sources} | {item.record_id for item in fixture.records} | {item.record_id for item in evaluation.executions}
    return PlatformFrontierLineage(fixture.fixture_id, tuple(edges), len(nodes), bool(edges), content_hash(tuple(edges)))


def verify_platform_frontier_lineage(lineage: PlatformFrontierLineage) -> tuple[str, ...]:
    issues = []
    if not lineage.edges:
        issues.append("lineage_empty")
    if len({item.edge_id for item in lineage.edges}) != len(lineage.edges):
        issues.append("duplicate_edge_id")
    if any(not item.content_address.startswith("sha256:") for item in lineage.edges):
        issues.append("edge_address_missing")
    return tuple(issues)


__all__ = ["PlatformFrontierLineage", "PlatformFrontierLineageEdge", "build_platform_frontier_lineage", "verify_platform_frontier_lineage"]
