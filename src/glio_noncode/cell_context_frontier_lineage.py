"""Source-to-record lineage for Domain 08 context evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .cell_context_frontier_public_data import CellContextFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierLineageEdge:
    source_id: str
    source_address: str
    record_id: str
    record_address: str
    operation: str
    relation: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.source_id or not self.record_id or not self.operation or not self.relation:
            raise ValidationError("cell lineage edge is incomplete")
        if not self.source_address.startswith("sha256:") or not self.record_address.startswith(
            "sha256:"
        ):
            raise ValidationError("cell lineage addresses are required")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierLineage:
    fixture_id: str
    edges: tuple[CellContextFrontierLineageEdge, ...]
    accepted: bool
    source_count: int
    record_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.edges:
            raise ValidationError("cell lineage is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_record(self, record_id: str) -> tuple[CellContextFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.record_id == record_id)

    def for_source(self, source_id: str) -> tuple[CellContextFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.source_id == source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_frontier_lineage(
    fixture: CellContextFrontierFixture, evaluation: CellContextFrontierEvaluation
) -> CellContextFrontierLineage:
    source_map = fixture.source_map()
    record_map = fixture.record_map()
    edges = tuple(
        CellContextFrontierLineageEdge(
            source_id,
            source_map[source_id].content_address,
            row.record_id,
            record_map[row.record_id].content_address,
            row.operation,
            "source_supports_context_resolution",
        )
        for row in evaluation.records
        for source_id in record_map[row.record_id].source_ids
    )
    accepted = len(edges) >= len(evaluation.records) and all(
        item.record_id in record_map and item.source_id in source_map for item in edges
    )
    return CellContextFrontierLineage(
        fixture.fixture_id, edges, accepted, len(source_map), len(record_map)
    )


__all__ = [
    "CellContextFrontierLineage",
    "CellContextFrontierLineageEdge",
    "build_cell_context_frontier_lineage",
]
