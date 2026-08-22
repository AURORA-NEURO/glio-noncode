"""Source-to-record-to-result lineage for causal foundation replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierLineageEdge:
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
class CausalFoundationFrontierLineage:
    fixture_id: str
    edges: tuple[CausalFoundationFrontierLineageEdge, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def record_edges(self) -> tuple[CausalFoundationFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.edge_kind == "record_to_result")

    @property
    def source_edges(self) -> tuple[CausalFoundationFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.edge_kind == "source_to_record")

    @property
    def fixture_edges(self) -> tuple[CausalFoundationFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.edge_kind == "fixture_to_record")

    def for_record(self, record_id: str) -> tuple[CausalFoundationFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.child_id == record_id or item.parent_id == record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "edges": [item.to_dict() for item in self.edges], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_foundation_frontier_lineage(fixture: CausalFoundationFrontierFixture, evaluation: CausalFoundationFrontierEvaluation) -> CausalFoundationFrontierLineage:
    edges: list[CausalFoundationFrontierLineageEdge] = []
    for record in fixture.records:
        edges.append(CausalFoundationFrontierLineageEdge(f"fixture:{fixture.fixture_id}", f"record:{record.record_id}", "fixture_to_record"))
        for source_id in record.source_ids:
            edges.append(CausalFoundationFrontierLineageEdge(f"source:{source_id}", f"record:{record.record_id}", "source_to_record"))
        row = next(item for item in evaluation.rows if item.record_id == record.record_id)
        edges.append(CausalFoundationFrontierLineageEdge(f"record:{record.record_id}", f"result:{row.adapter.content_address}", "record_to_result"))
    values = tuple(edges)
    record_ids = {f"record:{item.record_id}" for item in fixture.records}
    accepted = bool(values) and len({item.content_address for item in values}) == len(values) and all(item.parent_id and item.child_id for item in values) and len(record_ids) == len(fixture.records)
    return CausalFoundationFrontierLineage(fixture.fixture_id, values, accepted)


def verify_causal_foundation_frontier_lineage(lineage: CausalFoundationFrontierLineage, fixture: CausalFoundationFrontierFixture) -> bool:
    return lineage.accepted and len(lineage.record_edges) == len(fixture.records) and len(lineage.fixture_edges) == len(fixture.records) and all(item.edge_kind in {"fixture_to_record", "source_to_record", "record_to_result"} for item in lineage.edges)


__all__ = ["CausalFoundationFrontierLineage", "CausalFoundationFrontierLineageEdge", "build_causal_foundation_frontier_lineage", "verify_causal_foundation_frontier_lineage"]
