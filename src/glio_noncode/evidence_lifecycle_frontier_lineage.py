"""Source and execution lineage for the Domain 14 lifecycle frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_fixture_eval import EvidenceLifecycleEvaluation
from .evidence_lifecycle_frontier_public_data import EvidenceLifecycleFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleLineageEdge:
    parent_id: str
    child_id: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleLineageGraph:
    graph_id: str
    edges: tuple[EvidenceLifecycleLineageEdge, ...]
    terminal_addresses: tuple[str, ...]
    acyclic: bool
    content_address: str

    def by_child(self, child_id: str) -> tuple[EvidenceLifecycleLineageEdge, ...]:
        return tuple(item for item in self.edges if item.child_id == child_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_lifecycle_lineage(fixture: EvidenceLifecycleFixture, evaluation: EvidenceLifecycleEvaluation) -> EvidenceLifecycleLineageGraph:
    edges: list[EvidenceLifecycleLineageEdge] = []
    source_cursor: dict[str, int] = {}
    for record in fixture.records:
        for source_id in record.source_ids:
            index = source_cursor.get(source_id, 0)
            source_cursor[source_id] = index + 1
            body = {"parent_id": source_id, "child_id": f"execution:{record.record_id}", "relation": "source_to_execution", "ordinal": index}
            edges.append(EvidenceLifecycleLineageEdge(body["parent_id"], body["child_id"], body["relation"], content_hash(body)))
        body = {"parent_id": f"fixture:{fixture.fixture_id}", "child_id": f"execution:{record.record_id}", "relation": "fixture_to_execution"}
        edges.append(EvidenceLifecycleLineageEdge(body["parent_id"], body["child_id"], body["relation"], content_hash(body)))
    terminals = tuple(item.content_address for item in evaluation.executions)
    body = {"graph_id": "evidence-lifecycle-lineage", "edges": tuple(edges), "terminal_addresses": terminals, "acyclic": True}
    return EvidenceLifecycleLineageGraph(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleLineageEdge", "EvidenceLifecycleLineageGraph", "build_evidence_lifecycle_lineage"]
