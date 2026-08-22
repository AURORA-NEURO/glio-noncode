"""Source-to-result lineage for chromatin-alpha evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .chromatin_alpha_frontier_public_data import ChromatinAlphaFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierLineageEdge:
    source_id: str
    record_id: str
    operation: str
    result_address: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.source_id
            or not self.record_id
            or not self.operation
            or not self.result_address
        ):
            raise ValidationError("lineage edge is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierLineage:
    fixture_id: str
    edges: tuple[ChromatinAlphaFrontierLineageEdge, ...]
    source_count: int
    record_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.edges:
            raise ValidationError("lineage requires fixture and edges")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_source(self, source_id: str) -> tuple[ChromatinAlphaFrontierLineageEdge, ...]:
        return tuple(edge for edge in self.edges if edge.source_id == source_id)

    def for_record(self, record_id: str) -> tuple[ChromatinAlphaFrontierLineageEdge, ...]:
        return tuple(edge for edge in self.edges if edge.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_alpha_frontier_lineage(
    fixture: ChromatinAlphaFrontierFixture,
    evaluation: ChromatinAlphaFrontierEvaluation,
) -> ChromatinAlphaFrontierLineage:
    record_map = fixture.record_map()
    edges = tuple(
        ChromatinAlphaFrontierLineageEdge(
            source_id=source_id,
            record_id=item.record_id,
            operation=item.operation,
            result_address=item.adapter.content_address,
        )
        for item in evaluation.records
        for source_id in record_map[item.record_id].source_ids
    )
    return ChromatinAlphaFrontierLineage(
        fixture_id=fixture.fixture_id,
        edges=edges,
        source_count=len(fixture.sources),
        record_count=len(evaluation.records),
        accepted=len(edges) >= len(evaluation.records)
        and all(edge.result_address.startswith("sha256:") for edge in edges),
    )


def verify_chromatin_alpha_frontier_lineage(
    lineage: ChromatinAlphaFrontierLineage,
    fixture: ChromatinAlphaFrontierFixture,
    evaluation: ChromatinAlphaFrontierEvaluation,
) -> bool:
    expected = {
        (source_id, item.record_id)
        for item in evaluation.records
        for source_id in fixture.record_map()[item.record_id].source_ids
    }
    observed = {(edge.source_id, edge.record_id) for edge in lineage.edges}
    return (
        lineage.accepted
        and expected <= observed
        and len(lineage.for_record(evaluation.records[0].record_id)) >= 1
    )


__all__ = [
    "ChromatinAlphaFrontierLineage",
    "ChromatinAlphaFrontierLineageEdge",
    "build_chromatin_alpha_frontier_lineage",
    "verify_chromatin_alpha_frontier_lineage",
]
