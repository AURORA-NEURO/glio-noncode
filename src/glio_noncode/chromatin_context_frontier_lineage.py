"""Content-addressed source-to-record lineage for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import ChromatinContextFrontierEvaluation
from .chromatin_context_frontier_public_data import ChromatinContextFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierLineageEdge:
    source_id: str
    source_address: str
    record_id: str
    record_address: str
    operation: str
    relation: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.source_id or not self.record_id or not self.operation:
            raise ValidationError("lineage edge is incomplete")
        if not self.source_address.startswith("sha256:") or not self.record_address.startswith(
            "sha256:"
        ):
            raise ValidationError("lineage edge requires content addresses")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierLineage:
    fixture_id: str
    edges: tuple[ChromatinContextFrontierLineageEdge, ...]
    accepted: bool
    source_count: int
    record_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.edges:
            raise ValidationError("lineage is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_record(self, record_id: str) -> tuple[ChromatinContextFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.record_id == record_id)

    def for_source(self, source_id: str) -> tuple[ChromatinContextFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.source_id == source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_context_frontier_lineage(
    fixture: ChromatinContextFrontierFixture,
    evaluation: ChromatinContextFrontierEvaluation,
) -> ChromatinContextFrontierLineage:
    source_map = fixture.source_map()
    record_map = fixture.record_map()
    edges: list[ChromatinContextFrontierLineageEdge] = []
    for row in evaluation.records:
        record = record_map[row.record_id]
        for source_id in record.source_ids:
            source = source_map[source_id]
            edges.append(
                ChromatinContextFrontierLineageEdge(
                    source_id,
                    source.content_address,
                    record.record_id,
                    record.content_address,
                    record.operation.value,
                    "source_supports_context_operation",
                )
            )
    accepted = (
        len(edges) >= len(evaluation.records)
        and all(edge.for_record if False else True for edge in ())
        and all(item.source_id in source_map for item in edges)
        and all(item.record_id in record_map for item in edges)
    )
    return ChromatinContextFrontierLineage(
        fixture.fixture_id,
        tuple(edges),
        accepted,
        len(source_map),
        len(record_map),
    )


__all__ = [
    "ChromatinContextFrontierLineage",
    "ChromatinContextFrontierLineageEdge",
    "build_chromatin_context_frontier_lineage",
]
