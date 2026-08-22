"""Provenance graph closure for public alpha evidence and derived outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_lineage import CausalAlphaFrontierLineage
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierProvenanceNode:
    node_id: str
    kind: str
    address: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "kind": self.kind, "address": self.address, "metadata": dict(self.metadata)}


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierProvenanceGraph:
    fixture_id: str
    nodes: tuple[CausalAlphaFrontierProvenanceNode, ...]
    edges: tuple[tuple[str, str, str], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "nodes": [item.to_dict() for item in self.nodes], "edges": self.edges, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_provenance(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, lineage: CausalAlphaFrontierLineage) -> CausalAlphaFrontierProvenanceGraph:
    nodes: list[CausalAlphaFrontierProvenanceNode] = [CausalAlphaFrontierProvenanceNode("fixture", "fixture", fixture.content_address, {"version": fixture.version, "boundary": fixture.boundary})]
    nodes.extend(CausalAlphaFrontierProvenanceNode(f"source:{item.source_id}", "source", item.content_address, {"uri": item.uri, "release": item.release}) for item in fixture.sources)
    nodes.extend(CausalAlphaFrontierProvenanceNode(f"record:{item.record_id}", "record", item.content_address, {"operation": item.operation, "context_key": item.context_key}) for item in fixture.records)
    nodes.extend(CausalAlphaFrontierProvenanceNode(f"result:{item.record_id}", "result", item.content_address, {"state": item.observed_state, "accepted": item.accepted}) for item in evaluation.evaluation.results)
    edges = [("fixture", f"source:{item.source_id}", "contains") for item in fixture.sources]
    edges.extend((f"source:{source_id}", f"record:{record.record_id}", "supports") for record in fixture.records for source_id in record.source_ids)
    edges.extend((f"record:{item.record_id}", f"result:{item.record_id}", "derives") for item in evaluation.evaluation.results)
    known = {item.node_id for item in nodes}
    accepted = bool(lineage.accepted and len(nodes) == 1 + len(fixture.sources) + len(fixture.records) + len(evaluation.evaluation.results) and all(parent in known and child in known for parent, child, _ in edges))
    return CausalAlphaFrontierProvenanceGraph(fixture.fixture_id, tuple(nodes), tuple(edges), accepted)


__all__ = ["CausalAlphaFrontierProvenanceGraph", "CausalAlphaFrontierProvenanceNode", "build_causal_alpha_frontier_provenance"]
