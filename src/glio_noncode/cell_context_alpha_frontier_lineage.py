"""Source-to-record lineage for context-alpha evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierLineageEdge:
    edge_id: str
    record_id: str
    source_id: str
    source_version: str
    operation: str
    evidence_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierLineage:
    fixture_id: str
    edges: tuple[CellContextAlphaFrontierLineageEdge, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.edges:
            raise ValueError("alpha lineage is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def source_count(self) -> int:
        return len({item.source_id for item in self.edges})

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"source_count": self.source_count}


def build_cell_context_alpha_frontier_lineage(
    fixture: CellContextAlphaFrontierFixture, evaluation: CellContextAlphaFrontierEvaluation
) -> CellContextAlphaFrontierLineage:
    source_map = fixture.source_map()
    edges = []
    for row in evaluation.records:
        record = fixture.record_map()[row.record_id]
        source = source_map[record.source_ids[0]]
        edges.append(
            CellContextAlphaFrontierLineageEdge(
                f"{row.record_id}:{source.source_id}",
                row.record_id,
                source.source_id,
                source.release,
                row.operation,
                tuple(row.adapter.measurements.get("evidence_ids", ())),
            )
        )
    return CellContextAlphaFrontierLineage(
        fixture.fixture_id, tuple(edges), len(edges) == len(evaluation.records)
    )


__all__ = [
    "CellContextAlphaFrontierLineage",
    "CellContextAlphaFrontierLineageEdge",
    "build_cell_context_alpha_frontier_lineage",
]
