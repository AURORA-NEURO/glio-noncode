"""Source, record, operation, and result provenance matrix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierProvenanceCell:
    record_id: str
    source_ids: tuple[str, ...]
    operation: str
    context_key: str
    observed_state: str
    result_address: str
    complete: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierProvenanceMatrix:
    fixture_id: str
    cells: tuple[LinkGraphFoundationFrontierProvenanceCell, ...]
    source_count: int
    complete: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def incomplete_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.cells if not item.complete)

    def for_source(self, source_id: str) -> tuple[LinkGraphFoundationFrontierProvenanceCell, ...]:
        return tuple(item for item in self.cells if source_id in item.source_ids)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cells": [item.to_dict() for item in self.cells], "source_count": self.source_count, "incomplete_record_ids": self.incomplete_record_ids, "complete": self.complete}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_provenance_matrix(fixture: LinkGraphFoundationFrontierFixture | None = None, evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierProvenanceMatrix:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_foundation_frontier_fixture_eval", fromlist=["evaluate_link_graph_foundation_frontier_fixture"]).evaluate_link_graph_foundation_frontier_fixture(value)
    sources = {source.source_id for source in value.sources}
    cells = tuple(LinkGraphFoundationFrontierProvenanceCell(record.record_id, record.source_ids, record.operation.value, record.context_key, next(row.observed_state for row in replay.rows if row.record_id == record.record_id), next(row.adapter.content_address for row in replay.rows if row.record_id == record.record_id), bool(record.source_ids) and set(record.source_ids) <= sources) for record in value.records)
    return LinkGraphFoundationFrontierProvenanceMatrix(value.fixture_id, cells, len(sources), bool(cells) and all(cell.complete for cell in cells))


def provenance_matrix_summary(matrix: LinkGraphFoundationFrontierProvenanceMatrix) -> dict[str, Any]:
    return {"fixture_id": matrix.fixture_id, "cell_count": len(matrix.cells), "source_count": matrix.source_count, "complete_count": sum(item.complete for item in matrix.cells), "incomplete_count": len(matrix.incomplete_record_ids), "complete": matrix.complete}


__all__ = ["LinkGraphFoundationFrontierProvenanceCell", "LinkGraphFoundationFrontierProvenanceMatrix", "build_link_graph_foundation_frontier_provenance_matrix", "provenance_matrix_summary"]
