"""Aggregate boundary and policy compliance checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import ChromatinContextFrontierEvaluation
from .chromatin_context_frontier_public_data import (
    CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
    ChromatinContextFrontierFixture,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierBoundaryCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("boundary check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierBoundaryReport:
    checks: tuple[ChromatinContextFrontierBoundaryCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("boundary report requires checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_chromatin_context_frontier_boundary(
    fixture: ChromatinContextFrontierFixture,
    evaluation: ChromatinContextFrontierEvaluation,
) -> ChromatinContextFrontierBoundaryReport:
    forbidden_keys = {
        "patient",
        "subject",
        "sample_id",
        "donor_id",
        "participant_id",
        "individual_id",
    }
    checks = (
        ChromatinContextFrontierBoundaryCheck(
            "boundary_label",
            fixture.evidence_boundary == CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
            "aggregate boundary label is exact",
            fixture.evidence_boundary,
            CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
        ),
        ChromatinContextFrontierBoundaryCheck(
            "public_sources",
            all(item.public_aggregate for item in fixture.sources),
            "all sources are public aggregate receipts",
        ),
        ChromatinContextFrontierBoundaryCheck(
            "no_subject_keys",
            all(
                not {str(key).lower() for key in item.payload} & forbidden_keys
                for item in fixture.records
            ),
            "payloads contain no subject-level keys",
        ),
        ChromatinContextFrontierBoundaryCheck(
            "context_lock",
            all(item.record.context_key == fixture.context_key for item in evaluation.records),
            "all evaluation rows retain context lock",
        ),
        ChromatinContextFrontierBoundaryCheck(
            "foreign_refusal",
            any(item.observed_state == "out_of_domain" for item in evaluation.records),
            "foreign contexts produce visible refusal states",
        ),
        ChromatinContextFrontierCheck(
            "no_activity_shortcut",
            all("target" not in item.adapter.measurements for item in evaluation.records),
            "no target linkage is silently synthesized",
        ),
    )
    failed = tuple(item.check_id for item in checks if not item.passed)
    return ChromatinContextFrontierBoundaryReport(checks, not failed, failed)


# Keep the boundary check constructor distinct from data-level checks so call
# sites cannot accidentally mix release evidence with parser diagnostics.
ChromatinContextFrontierCheck = ChromatinContextFrontierBoundaryCheck


__all__ = [
    "ChromatinContextFrontierBoundaryCheck",
    "ChromatinContextFrontierBoundaryReport",
    "evaluate_chromatin_context_frontier_boundary",
]
