"""Invariant checks for graph cardinality, context, and evidence closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture, LinkGraphAlphaFrontierOperation
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierInvariantReport:
    results: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"results": [item.to_dict() for item in self.results], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_link_graph_alpha_frontier_invariants(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierInvariantReport:
    source_ids = {source.source_id for source in fixture.sources}
    results = (
        check("record_count", len(fixture.records) == 16, "fixture contains the declared 16 records"),
        check("operation_count", all(len(fixture.operation_records(operation)) == 4 for operation in LinkGraphAlphaFrontierOperation), "each operation has four records"),
        check("positive_count", len(fixture.positive_records) == 4, "each operation has one positive record"),
        check("control_count", len(fixture.control_records) == 12, "each operation has three controls"),
        check("source_closure", all(set(record.source_ids) <= source_ids for record in fixture.records), "record receipts resolve"),
        check("replay_closure", len(evaluation.rows) == len(fixture.records) and evaluation.accepted, "replay covers every record"),
        check("foreign_controls", all(record.context_key == fixture.foreign_context_key for record in fixture.records if record.record_id.endswith("C3")), "C3 controls use the foreign context"),
    )
    return LinkGraphAlphaFrontierInvariantReport(results, all(item.passed for item in results))


__all__ = ["LinkGraphAlphaFrontierInvariantReport", "run_link_graph_alpha_frontier_invariants"]
