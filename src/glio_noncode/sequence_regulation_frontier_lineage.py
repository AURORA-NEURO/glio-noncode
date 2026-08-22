"""Source-to-result lineage for the C09-C12 evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .sequence_regulation_frontier_public_data import SequenceRegulationFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationLineageEdge:
    source_id: str
    record_id: str
    operation: str
    result_address: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.source_id or not self.record_id or not self.result_address:
            raise ValidationError("lineage edge is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationLineage:
    fixture_id: str
    edges: tuple[SequenceRegulationLineageEdge, ...]
    source_count: int
    record_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.edges:
            raise ValidationError("lineage requires edges")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_source(self, source_id: str) -> tuple[SequenceRegulationLineageEdge, ...]:
        return tuple(edge for edge in self.edges if edge.source_id == source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_regulation_lineage(
    fixture: SequenceRegulationFixture,
    evaluation: SequenceRegulationEvaluation,
) -> SequenceRegulationLineage:
    source_lookup = {record.record_id: record.source_ids for record in fixture.records}
    edges = tuple(
        SequenceRegulationLineageEdge(
            source_id=source_id,
            record_id=item.record_id,
            operation=item.adapter.operation.value,
            result_address=item.adapter.content_address,
        )
        for item in evaluation.records
        for source_id in source_lookup[item.record_id]
    )
    return SequenceRegulationLineage(
        fixture_id=fixture.fixture_id,
        edges=edges,
        source_count=len(fixture.sources),
        record_count=len(fixture.records),
        accepted=len(edges) >= len(evaluation.records)
        and all(edge.result_address.startswith("sha256:") for edge in edges),
    )


__all__ = [
    "SequenceRegulationLineage",
    "SequenceRegulationLineageEdge",
    "build_sequence_regulation_lineage",
]
