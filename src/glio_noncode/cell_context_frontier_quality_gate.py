"""Quality gate for the Domain 08 C01-C04 aggregate release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .cell_context_frontier_metrics import CellContextFrontierMetrics
from .cell_context_frontier_public_data import (
    CELL_CONTEXT_FRONTIER_BOUNDARY,
    CellContextFrontierFixture,
    CellContextFrontierOperation,
)
from .cell_context_frontier_reconciliation import CellContextFrontierReconciliation
from .cell_context_frontier_schema import CellContextFrontierSchemaReport
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierQualityCheck:
    check_id: str
    passed: bool
    severity: str
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.check_id
            or not self.detail
            or self.severity not in {"info", "warning", "error"}
        ):
            raise ValidationError("cell quality check is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierQualityReport:
    checks: tuple[CellContextFrontierQualityCheck, ...]
    accepted: bool
    passed_count: int
    failed_check_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("cell quality report is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "warning" and not item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"warning_count": self.warning_count}


def build_cell_context_frontier_quality(
    fixture: CellContextFrontierFixture,
    data: Any,
    schema: CellContextFrontierSchemaReport,
    evaluation: CellContextFrontierEvaluation,
    metrics: CellContextFrontierMetrics,
    reconciliation: CellContextFrontierReconciliation,
) -> CellContextFrontierQualityReport:
    checks = (
        CellContextFrontierQualityCheck(
            "data_audit", data.accepted, "error", "aggregate data audit passes"
        ),
        CellContextFrontierQualityCheck(
            "schema", schema.accepted, "error", "schema and boundary checks pass"
        ),
        CellContextFrontierQualityCheck(
            "fixture_identity", bool(fixture.fixture_id), "error", "fixture identity is present"
        ),
        CellContextFrontierQualityCheck(
            "source_count", len(fixture.sources) == 5, "error", "five source receipts are present"
        ),
        CellContextFrontierQualityCheck(
            "record_count",
            len(fixture.records) == 16,
            "error",
            "sixteen fixture records are present",
        ),
        CellContextFrontierQualityCheck(
            "positive_count",
            len(fixture.positive_records) == 4,
            "error",
            "four positive rows are present",
        ),
        CellContextFrontierQualityCheck(
            "control_count",
            len(fixture.control_records) == 12,
            "error",
            "twelve control rows are present",
        ),
        CellContextFrontierQualityCheck(
            "operation_balance",
            all(len(fixture.operation_records(item)) == 4 for item in CellContextFrontierOperation),
            "error",
            "each operation has four rows",
        ),
        CellContextFrontierQualityCheck(
            "evaluation", evaluation.accepted, "error", "all expected paths evaluate"
        ),
        CellContextFrontierQualityCheck(
            "state_matches", evaluation.state_match_count == 16, "error", "all states match"
        ),
        CellContextFrontierQualityCheck(
            "issue_matches", evaluation.issue_match_count == 16, "error", "all issue floors match"
        ),
        CellContextFrontierQualityCheck(
            "metrics", metrics.accepted, "error", "metrics meet release floors"
        ),
        CellContextFrontierQualityCheck(
            "reconciliation",
            reconciliation.accepted,
            "error",
            "expected and observed paths reconcile",
        ),
        CellContextFrontierQualityCheck(
            "positive_states",
            all(item.observed_state == "supported" for item in evaluation.positive_rows),
            "error",
            "positive paths are supported",
        ),
        CellContextFrontierQualityCheck(
            "ambiguity",
            any(item.observed_state == "ambiguous" for item in evaluation.control_rows),
            "warning",
            "ambiguous candidates remain visible",
        ),
        CellContextFrontierQualityCheck(
            "contradiction",
            any(item.observed_state == "contradictory" for item in evaluation.control_rows),
            "warning",
            "age conflict remains visible",
        ),
        CellContextFrontierQualityCheck(
            "abstention",
            any(item.observed_state == "abstained" for item in evaluation.control_rows),
            "warning",
            "missing molecular support remains abstained",
        ),
        CellContextFrontierQualityCheck(
            "partial",
            any(item.observed_state == "partial" for item in evaluation.control_rows),
            "warning",
            "malformed input remains partial",
        ),
        CellContextFrontierQualityCheck(
            "foreign_context",
            any(item.observed_state == "out_of_domain" for item in evaluation.control_rows),
            "warning",
            "foreign context remains out of domain",
        ),
        CellContextFrontierQualityCheck(
            "receipts",
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "error",
            "adapter results have receipts",
        ),
        CellContextFrontierQualityCheck(
            "source_receipts",
            all(item.content_address.startswith("sha256:") for item in fixture.sources),
            "error",
            "source receipts have addresses",
        ),
        CellContextFrontierQualityCheck(
            "boundary",
            fixture.evidence_boundary == CELL_CONTEXT_FRONTIER_BOUNDARY,
            "error",
            "aggregate boundary is locked",
        ),
        CellContextFrontierQualityCheck(
            "context_lock",
            all(item.context_key == fixture.context_key for item in fixture.records),
            "error",
            "context keys are locked",
        ),
        CellContextFrontierQualityCheck(
            "limitations",
            all(item.adapter.warnings for item in evaluation.records),
            "warning",
            "limitations are visible",
        ),
    )
    failed = tuple(item.check_id for item in checks if not item.passed and item.severity == "error")
    return CellContextFrontierQualityReport(
        checks, not failed, sum(item.passed for item in checks), failed
    )


__all__ = [
    "CellContextFrontierQualityCheck",
    "CellContextFrontierQualityReport",
    "build_cell_context_frontier_quality",
]
