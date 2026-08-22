"""Source-to-record-to-result lineage for C05-C08 replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierLineageEdge:
    parent_id: str
    child_id: str
    edge_kind: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"parent_id": self.parent_id, "child_id": self.child_id, "edge_kind": self.edge_kind}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierLineage:
    fixture_id: str
    edges: tuple[CausalBetaFrontierLineageEdge, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def fixture_edges(self) -> tuple[CausalBetaFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.edge_kind == "fixture_to_record")

    @property
    def source_edges(self) -> tuple[CausalBetaFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.edge_kind == "source_to_record")

    @property
    def record_edges(self) -> tuple[CausalBetaFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.edge_kind == "record_to_result")

    def for_record(self, record_id: str) -> tuple[CausalBetaFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if record_id in {item.parent_id.removeprefix("record:"), item.child_id.removeprefix("record:")})

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "edges": [item.to_dict() for item in self.edges], "accepted": self.accepted, "fixture_edge_count": len(self.fixture_edges), "source_edge_count": len(self.source_edges), "record_edge_count": len(self.record_edges)}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_lineage(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation) -> CausalBetaFrontierLineage:
    edges: list[CausalBetaFrontierLineageEdge] = []
    for record in fixture.records:
        edges.append(CausalBetaFrontierLineageEdge(f"fixture:{fixture.fixture_id}", f"record:{record.record_id}", "fixture_to_record"))
        edges.extend(CausalBetaFrontierLineageEdge(f"source:{source_id}", f"record:{record.record_id}", "source_to_record") for source_id in record.source_ids)
        row = next(item for item in evaluation.rows if item.record_id == record.record_id)
        edges.append(CausalBetaFrontierLineageEdge(f"record:{record.record_id}", f"result:{row.adapter.content_address}", "record_to_result"))
    values = tuple(edges)
    accepted = bool(values) and len({item.content_address for item in values}) == len(values) and len({item.parent_id for item in values if item.edge_kind == "fixture_to_record"}) == 1
    return CausalBetaFrontierLineage(fixture.fixture_id, values, accepted)


def verify_causal_beta_frontier_lineage(lineage: CausalBetaFrontierLineage, fixture: CausalBetaFrontierFixture) -> bool:
    return lineage.accepted and len(lineage.fixture_edges) == len(fixture.records) and len(lineage.record_edges) == len(fixture.records) and all(item.edge_kind in {"fixture_to_record", "source_to_record", "record_to_result"} for item in lineage.edges)


__all__ = ["CausalBetaFrontierLineage", "CausalBetaFrontierLineageEdge", "build_causal_beta_frontier_lineage", "verify_causal_beta_frontier_lineage"]
