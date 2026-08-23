"""Source-to-record provenance graph for planning evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningFixture, PlanningEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningProvenance:
    source_nodes: tuple[dict[str, Any], ...]
    record_edges: tuple[dict[str, Any], ...]
    execution_edges: tuple[dict[str, Any], ...]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_provenance(fixture: PlanningFixture, evaluation: PlanningEvaluation) -> PlanningProvenance:
    source_nodes = tuple({"source_id": item.source_id, "uri": item.uri, "content_address": item.content_address} for item in fixture.sources)
    record_edges = tuple({"record_id": item.record_id, "source_ids": item.source_ids, "record_address": item.content_address} for item in fixture.records)
    execution_edges = tuple({"record_id": item.record_id, "execution_address": item.content_address} for item in evaluation.executions)
    source_ids = {item["source_id"] for item in source_nodes}
    closed = bool(source_nodes and record_edges and len(execution_edges) == len(record_edges) and all(set(item["source_ids"]) <= source_ids for item in record_edges))
    body = {"source_nodes": source_nodes, "record_edges": record_edges, "execution_edges": execution_edges, "closed": closed}
    return PlanningProvenance(source_nodes, record_edges, execution_edges, closed, content_hash(body, prefix="planning-provenance"))


__all__ = ["PlanningProvenance", "build_planning_provenance"]
