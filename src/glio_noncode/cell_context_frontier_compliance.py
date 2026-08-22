"""Aggregate-boundary compliance checks for context evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .cell_context_frontier_public_data import (
    CELL_CONTEXT_FRONTIER_BOUNDARY,
    CellContextFrontierFixture,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierBoundaryCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("cell boundary check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierBoundaryReport:
    checks: tuple[CellContextFrontierBoundaryCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("cell boundary report is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cell_context_frontier_boundary(
    fixture: CellContextFrontierFixture, evaluation: CellContextFrontierEvaluation
) -> CellContextFrontierBoundaryReport:
    forbidden = {"patient", "subject", "sample_id", "donor_id", "participant_id", "individual_id"}
    checks = (
        CellContextFrontierBoundaryCheck(
            "boundary_label",
            fixture.evidence_boundary == CELL_CONTEXT_FRONTIER_BOUNDARY,
            "aggregate boundary is exact",
            fixture.evidence_boundary,
            CELL_CONTEXT_FRONTIER_BOUNDARY,
        ),
        CellContextFrontierBoundaryCheck(
            "public_sources",
            all(item.public_aggregate for item in fixture.sources),
            "all sources are public aggregate receipts",
        ),
        CellContextFrontierBoundaryCheck(
            "no_restricted_keys",
            all(
                not {str(key).lower() for key in item.payload} & forbidden
                for item in fixture.records
            ),
            "payloads contain no subject-level keys",
        ),
        CellContextFrontierBoundaryCheck(
            "context_lock",
            all(item.record.context_key == fixture.context_key for item in evaluation.records),
            "evaluation rows retain context lock",
        ),
        CellContextFrontierBoundaryCheck(
            "foreign_refusal",
            any(item.observed_state == "out_of_domain" for item in evaluation.control_rows),
            "foreign rows produce refusal states",
        ),
        CellContextFrontierBoundaryCheck(
            "no_clinical_shortcut",
            all("diagnosis" not in item.adapter.measurements for item in evaluation.records),
            "no clinical conclusion is synthesized",
        ),
        CellContextFrontierBoundaryCheck(
            "uncertainty_visible",
            any(
                item.observed_state in {"ambiguous", "contradictory", "partial", "abstained"}
                for item in evaluation.control_rows
            ),
            "uncertainty remains visible",
        ),
    )
    failed = tuple(item.check_id for item in checks if not item.passed)
    return CellContextFrontierBoundaryReport(checks, not failed, failed)


__all__ = [
    "CellContextFrontierBoundaryCheck",
    "CellContextFrontierBoundaryReport",
    "evaluate_cell_context_frontier_boundary",
]
