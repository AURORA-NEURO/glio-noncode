"""Record-count assertions by control class and operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRecordCounts:
    operation_counts: dict[str, int]
    control_counts: dict[str, int]
    total: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def count_cohort_alpha_frontier_records(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierRecordCounts:
    operation_counts = {operation: sum(record.operation == operation for record in fixture.records) for operation in fixture.operations}
    controls = sorted({record.control_class for record in fixture.records})
    control_counts = {control: sum(record.control_class == control for record in fixture.records) for control in controls}
    body = {"operations": operation_counts, "controls": control_counts, "total": len(fixture.records)}
    return CohortAlphaFrontierRecordCounts(operation_counts, control_counts, len(fixture.records), len(operation_counts) == 4 and all(value == 4 for value in operation_counts.values()) and len(fixture.records) == 16, content_hash(body, prefix="alpha-record-counts"))


__all__ = ["CohortAlphaFrontierRecordCounts", "count_cohort_alpha_frontier_records"]
