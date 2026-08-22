"""Composed quality gate for C09-C12 aggregate outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .cell_context_alpha_frontier_public_data import (
    CellContextAlphaFrontierDataAudit,
    CellContextAlphaFrontierFixture,
)
from .cell_context_alpha_frontier_reconciliation import CellContextAlphaFrontierReconciliation
from .cell_context_alpha_frontier_schema import CellContextAlphaFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierQualityCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierQualityReport:
    fixture_id: str
    checks: tuple[CellContextAlphaFrontierQualityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValueError("alpha quality report is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


def build_cell_context_alpha_frontier_quality(
    fixture: CellContextAlphaFrontierFixture,
    data: CellContextAlphaFrontierDataAudit,
    schema: CellContextAlphaFrontierSchemaReport,
    evaluation: CellContextAlphaFrontierEvaluation,
    reconciliation: CellContextAlphaFrontierReconciliation,
) -> CellContextAlphaFrontierQualityReport:
    checks = (
        CellContextAlphaFrontierQualityCheck(
            "data", data.accepted, data.accepted, True, "data boundary passes"
        ),
        CellContextAlphaFrontierQualityCheck(
            "schema", schema.accepted, schema.accepted, True, "schema checks pass"
        ),
        CellContextAlphaFrontierQualityCheck(
            "state-replay",
            evaluation.state_match_count == len(evaluation.records),
            evaluation.state_match_count,
            len(evaluation.records),
            "all alpha states replay",
        ),
        CellContextAlphaFrontierQualityCheck(
            "issue-replay",
            evaluation.issue_match_count == len(evaluation.records),
            evaluation.issue_match_count,
            len(evaluation.records),
            "all alpha issue floors replay",
        ),
        CellContextAlphaFrontierQualityCheck(
            "reconciliation",
            reconciliation.accepted,
            reconciliation.accepted,
            True,
            "expected paths reconcile",
        ),
        CellContextAlphaFrontierQualityCheck(
            "control-depth",
            len(evaluation.control_rows) == 12,
            len(evaluation.control_rows),
            12,
            "twelve controls remain visible",
        ),
        CellContextAlphaFrontierQualityCheck(
            "domain-refusals",
            len(evaluation.by_state("out_of_domain")) == 4,
            len(evaluation.by_state("out_of_domain")),
            4,
            "four foreign-context refusals remain visible",
        ),
        CellContextAlphaFrontierQualityCheck(
            "delta-surface",
            any(
                item.operation == "treatment_induced_state_prior"
                and item.observed_state == "supported"
                for item in evaluation.records
            ),
            True,
            True,
            "treatment delta controls are present",
        ),
    )
    return CellContextAlphaFrontierQualityReport(
        fixture.fixture_id, checks, all(item.passed for item in checks)
    )


__all__ = [
    "CellContextAlphaFrontierQualityCheck",
    "CellContextAlphaFrontierQualityReport",
    "build_cell_context_alpha_frontier_quality",
]
