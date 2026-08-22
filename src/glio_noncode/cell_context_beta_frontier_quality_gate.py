"""Quality gate for release of the beta prior tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .cell_context_beta_frontier_public_data import (
    CellContextBetaFrontierDataAudit,
    CellContextBetaFrontierFixture,
)
from .cell_context_beta_frontier_reconciliation import CellContextBetaFrontierReconciliation
from .cell_context_beta_frontier_schema import CellContextBetaFrontierSchemaReport
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierQualityCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("beta quality check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierQualityReport:
    fixture_id: str
    checks: tuple[CellContextBetaFrontierQualityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.checks:
            raise ValidationError("beta quality report is incomplete")
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


def build_cell_context_beta_frontier_quality(
    fixture: CellContextBetaFrontierFixture,
    data: CellContextBetaFrontierDataAudit,
    schema: CellContextBetaFrontierSchemaReport,
    evaluation: CellContextBetaFrontierEvaluation,
    reconciliation: CellContextBetaFrontierReconciliation,
) -> CellContextBetaFrontierQualityReport:
    checks = (
        CellContextBetaFrontierQualityCheck(
            "data", data.accepted, data.accepted, True, "aggregate fixture audit passes"
        ),
        CellContextBetaFrontierQualityCheck(
            "schema", schema.accepted, schema.accepted, True, "schema and boundary checks pass"
        ),
        CellContextBetaFrontierQualityCheck(
            "state-replay",
            evaluation.state_match_count == len(evaluation.records),
            evaluation.state_match_count,
            len(evaluation.records),
            "all expected states replay",
        ),
        CellContextBetaFrontierQualityCheck(
            "issue-replay",
            evaluation.issue_match_count == len(evaluation.records),
            evaluation.issue_match_count,
            len(evaluation.records),
            "all issue floors replay",
        ),
        CellContextBetaFrontierQualityCheck(
            "reconciliation",
            reconciliation.accepted,
            reconciliation.accepted,
            True,
            "expected and observed rows reconcile",
        ),
        CellContextBetaFrontierQualityCheck(
            "control-depth",
            len(evaluation.control_rows) == 12,
            len(evaluation.control_rows),
            12,
            "all controls remain visible",
        ),
        CellContextBetaFrontierQualityCheck(
            "content-addresses",
            all(bool(item.content_address) for item in fixture.records),
            all(bool(item.content_address) for item in fixture.records),
            True,
            "records are immutable-addressed",
        ),
        CellContextBetaFrontierQualityCheck(
            "refusal-paths",
            len(evaluation.by_state("out_of_domain")) == 4,
            len(evaluation.by_state("out_of_domain")),
            4,
            "all explicit domain gates refuse transport",
        ),
    )
    return CellContextBetaFrontierQualityReport(
        fixture.fixture_id, checks, all(item.passed for item in checks)
    )


__all__ = [
    "CellContextBetaFrontierQualityCheck",
    "CellContextBetaFrontierQualityReport",
    "build_cell_context_beta_frontier_quality",
]
