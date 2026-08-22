"""Record-to-source-to-result lineage for candidate link outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierLineageEdge:
    edge_id: str
    record_id: str
    source_id: str
    operation: str
    evidence_ids: tuple[str, ...]
    result_address: str
    context_key: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierLineage:
    edges: tuple[LinkGraphAlphaFrontierLineageEdge, ...]
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_record(self, record_id: str) -> tuple[LinkGraphAlphaFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.record_id == record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"edges": [item.to_dict() for item in self.edges], "source_ids": self.source_ids, "record_ids": self.record_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_lineage(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierLineage:
    by_id = {record.record_id: record for record in fixture.records}
    edges = []
    for row in evaluation.rows:
        record = by_id[row.record_id]
        for source_id in record.source_ids:
            edges.append(LinkGraphAlphaFrontierLineageEdge(content_hash((record.record_id, source_id, row.adapter.content_address)), record.record_id, source_id, record.operation.value, row.adapter.evidence_ids, row.adapter.content_address, record.context_key))
    values = tuple(edges)
    accepted = len(values) >= len(fixture.records) and all(item.record_id in by_id for item in values) and all(item.source_id for item in values)
    return LinkGraphAlphaFrontierLineage(values, tuple(sorted({item.source_id for item in values})), tuple(sorted({item.record_id for item in values})), accepted)


def verify_link_graph_alpha_frontier_lineage(lineage: LinkGraphAlphaFrontierLineage, fixture: LinkGraphAlphaFrontierFixture) -> bool:
    return lineage.accepted and set(lineage.record_ids) == {item.record_id for item in fixture.records} and set(lineage.source_ids) == {item.source_id for item in fixture.sources}


__all__ = ["LinkGraphAlphaFrontierLineage", "LinkGraphAlphaFrontierLineageEdge", "build_link_graph_alpha_frontier_lineage", "verify_link_graph_alpha_frontier_lineage"]
