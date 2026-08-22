"""Integrity checks over receipts, contexts, states, and control coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .cell_context_frontier_public_data import CellContextFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierIntegrityCheck:
    check_id: str
    passed: bool
    severity: str
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.check_id
            or not self.detail
            or self.severity not in {"info", "warning", "error"}
        ):
            raise ValidationError("cell integrity check is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierIntegrityReport:
    checks: tuple[CellContextFrontierIntegrityCheck, ...]
    accepted: bool
    error_count: int
    warning_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("cell integrity report is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_ids": list(self.failed_ids)}


def evaluate_cell_context_frontier_integrity(
    fixture: CellContextFrontierFixture, evaluation: CellContextFrontierEvaluation
) -> CellContextFrontierIntegrityReport:
    checks = (
        CellContextFrontierIntegrityCheck(
            "fixture_address",
            fixture.content_address.startswith("sha256:"),
            "error",
            fixture.content_address[:7],
            "sha256:",
            "fixture has content address",
        ),
        CellContextFrontierIntegrityCheck(
            "source_addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.sources),
            "error",
            len(fixture.sources),
            5,
            "source receipts have content addresses",
        ),
        CellContextFrontierIntegrityCheck(
            "record_addresses",
            all(item.record.content_address.startswith("sha256:") for item in evaluation.records),
            "error",
            len(evaluation.records),
            16,
            "records have content addresses",
        ),
        CellContextFrontierIntegrityCheck(
            "result_addresses",
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "error",
            len(evaluation.records),
            16,
            "adapter results have content addresses",
        ),
        CellContextFrontierIntegrityCheck(
            "unique_records",
            len({item.record_id for item in evaluation.records}),
            "error",
            len({item.record_id for item in evaluation.records}),
            16,
            "result IDs are unique",
        ),
        CellContextFrontierIntegrityCheck(
            "positive_controls",
            (len(evaluation.positive_rows), len(evaluation.control_rows)),
            "error",
            (4, 12),
            (4, 12),
            "positive and control counts are stable",
        ),
        CellContextFrontierIntegrityCheck(
            "state_reconciliation",
            evaluation.state_match_count,
            "error",
            evaluation.state_match_count,
            16,
            "states reconcile",
        ),
        CellContextFrontierIntegrityCheck(
            "issue_reconciliation",
            evaluation.issue_match_count,
            "error",
            evaluation.issue_match_count,
            16,
            "issue floors reconcile",
        ),
        CellContextFrontierIntegrityCheck(
            "uncertainty_paths",
            sum(
                item.observed_state in {"ambiguous", "contradictory", "partial", "abstained"}
                for item in evaluation.control_rows
            ),
            "warning",
            sum(
                item.observed_state in {"ambiguous", "contradictory", "partial", "abstained"}
                for item in evaluation.control_rows
            ),
            1,
            "uncertainty remains visible",
        ),
        CellContextFrontierIntegrityCheck(
            "foreign_paths",
            sum(item.observed_state == "out_of_domain" for item in evaluation.control_rows),
            "warning",
            sum(item.observed_state == "out_of_domain" for item in evaluation.control_rows),
            1,
            "foreign context remains visible",
        ),
    )
    errors = sum(not item.passed and item.severity == "error" for item in checks)
    warnings = sum(not item.passed and item.severity == "warning" for item in checks)
    return CellContextFrontierIntegrityReport(checks, errors == 0, errors, warnings)


__all__ = [
    "CellContextFrontierIntegrityCheck",
    "CellContextFrontierIntegrityReport",
    "evaluate_cell_context_frontier_integrity",
]
