"""Coverage accounting for positive and boundary controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha import CohortAlphaState
from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCoverageCell:
    operation: str
    control_class: str
    expected_state: str
    observed_count: int
    accepted_count: int
    coverage_percent: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierControlCoverage:
    cells: tuple[CohortAlphaFrontierCoverageCell, ...]
    operations: tuple[str, ...]
    control_classes: tuple[str, ...]
    supported_paths: int
    boundary_paths: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_control_coverage(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierControlCoverage:
    cells: list[CohortAlphaFrontierCoverageCell] = []
    for operation in sorted(fixture.operations):
        for control_class in sorted({record.control_class for record in fixture.records if record.operation == operation}):
            records = tuple(record for record in fixture.records if record.operation == operation and record.control_class == control_class)
            rows = tuple(row for row in evaluation.rows if row.operation == operation and row.record_id in {record.record_id for record in records})
            accepted = sum(row.accepted for row in rows)
            cells.append(CohortAlphaFrontierCoverageCell(operation, control_class, records[0].expected_state.value, len(rows), accepted, round(100 * accepted / max(1, len(rows)), 2), content_hash({"operation": operation, "control_class": control_class, "rows": rows}, prefix="alpha-coverage-cell")))
    supported = sum(record.expected_state is CohortAlphaState.SUPPORTED for record in fixture.records)
    boundary = len(fixture.records) - supported
    values = tuple(cells)
    return CohortAlphaFrontierControlCoverage(values, fixture.operations, tuple(sorted({record.control_class for record in fixture.records})), supported, boundary, len(values) == 16 and all(item.observed_count >= 1 and item.coverage_percent == 100.0 for item in values), content_hash(values, prefix="alpha-coverage"))


__all__ = ["CohortAlphaFrontierControlCoverage", "CohortAlphaFrontierCoverageCell", "build_cohort_alpha_frontier_control_coverage"]
