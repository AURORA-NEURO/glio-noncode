"""Coverage map for positive, incomplete, absent, and foreign controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_public_data import CohortFoundationOperation


@dataclass(frozen=True, slots=True)
class CohortFoundationControlCoverageRow:
    operation: CohortFoundationOperation
    state_counts: dict[str, int]
    issue_codes: tuple[str, ...]
    record_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationControlCoverage:
    coverage_id: str
    rows: tuple[CohortFoundationControlCoverageRow, ...]
    state_classes: tuple[str, ...]
    accepted: bool
    content_address: str

    def row_for(self, operation: CohortFoundationOperation) -> CohortFoundationControlCoverageRow:
        return next(item for item in self.rows if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_control_coverage(evaluation: CohortFoundationEvaluation) -> CohortFoundationControlCoverage:
    state_classes = ("supported", "partial", "absent", "abstained", "out_of_domain")
    rows = []
    for operation in CohortFoundationOperation:
        values = tuple(item for item in evaluation.executions if item.operation is operation)
        counts = {state: sum(item.actual_state == state for item in values) for state in state_classes}
        issues = tuple(sorted({issue for item in values for issue in item.issues}))
        ids = tuple(item.record_id for item in values)
        body = {"operation": operation, "counts": counts, "issues": issues, "ids": ids}
        rows.append(CohortFoundationControlCoverageRow(operation, counts, issues, ids, counts["supported"] == 1 and sum(counts.values()) == 4, content_hash(body)))
    body = {"coverage_id": "cohort-foundation-frontier-control-coverage", "rows": rows, "classes": state_classes}
    return CohortFoundationControlCoverage(body["coverage_id"], tuple(rows), state_classes, all(item.accepted for item in rows), content_hash(body))


__all__ = ["CohortFoundationControlCoverage", "CohortFoundationControlCoverageRow", "build_cohort_foundation_frontier_control_coverage"]
