"""Cross-operation evidence matrix used for review navigation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierEvidenceCell:
    operation: str
    dimension: str
    value: str
    source_count: int
    row_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierEvidenceMatrix:
    cells: tuple[CohortBetaFrontierEvidenceCell, ...]
    accepted: bool
    content_address: str

    def cells_for(self, operation: str) -> tuple[CohortBetaFrontierEvidenceCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_evidence_matrix(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierEvidenceMatrix:
    cells = []
    for operation in ("C05", "C06", "C07", "C08"):
        records = tuple(record for record in fixture.records if record.operation == operation)
        rows = tuple(row for row in evaluation.rows if row.operation == operation)
        source_count = len({source for record in records for source in record.source_ids})
        dimensions = (("coverage", str(len(rows)), source_count), ("supported", str(sum(row.observed_state.value == "supported" for row in rows)), source_count), ("controls", str(sum(row.observed_state.value != "supported" for row in rows)), source_count), ("foreign_isolation", str(sum(row.observed_state.value == "out_of_domain" for row in rows)), source_count))
        for dimension, value, source_count in dimensions:
            cells.append(CohortBetaFrontierEvidenceCell(operation, dimension, value, source_count, len(rows), len(rows) == 4, content_hash({"operation": operation, "dimension": dimension, "value": value}, prefix="evidence-cell")))
    values = tuple(cells)
    return CohortBetaFrontierEvidenceMatrix(values, len(values) == 16 and all(item.accepted for item in values), content_hash({"fixture": fixture.fixture_id, "cells": values}, prefix="evidence-matrix"))


__all__ = ["CohortBetaFrontierEvidenceCell", "CohortBetaFrontierEvidenceMatrix", "build_cohort_beta_frontier_evidence_matrix"]
