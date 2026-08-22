"""Source and decision lineage for beta prior executions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .cell_context_beta_frontier_public_data import CellContextBetaFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierLineageEdge:
    edge_id: str
    record_id: str
    source_id: str
    source_version: str
    operation: str
    evidence_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.edge_id or not self.record_id or not self.source_id:
            raise ValidationError("beta lineage edge is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierLineage:
    fixture_id: str
    edges: tuple[CellContextBetaFrontierLineageEdge, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.edges:
            raise ValidationError("beta lineage is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def source_count(self) -> int:
        return len({item.source_id for item in self.edges})

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"source_count": self.source_count}


def build_cell_context_beta_frontier_lineage(
    fixture: CellContextBetaFrontierFixture, evaluation: CellContextBetaFrontierEvaluation
) -> CellContextBetaFrontierLineage:
    source_map = fixture.source_map()
    edges: list[CellContextBetaFrontierLineageEdge] = []
    for row in evaluation.records:
        for source_id in row.adapter.measurements.get("source_ids", ()) or (
            fixture.record_map()[row.record_id].source_ids[0],
        ):
            receipt = source_map.get(source_id)
            edges.append(
                CellContextBetaFrontierLineageEdge(
                    f"{row.record_id}:{source_id}",
                    row.record_id,
                    source_id,
                    str(receipt.release if receipt else "unknown"),
                    row.operation,
                    tuple(row.adapter.measurements.get("evidence_ids", ())),
                )
            )
    return CellContextBetaFrontierLineage(
        fixture.fixture_id, tuple(edges), len(edges) >= len(evaluation.records)
    )


__all__ = [
    "CellContextBetaFrontierLineage",
    "CellContextBetaFrontierLineageEdge",
    "build_cell_context_beta_frontier_lineage",
]
