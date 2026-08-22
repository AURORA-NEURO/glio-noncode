"""Boundary checks preventing clinical or subject-level expansion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_public_data import CellContextBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierBoundaryCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any
    required: Any
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierBoundaryReport:
    checks: tuple[CellContextBetaFrontierBoundaryCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cell_context_beta_frontier_boundary(
    fixture: CellContextBetaFrontierFixture,
) -> CellContextBetaFrontierBoundaryReport:
    prohibited = {"patient", "subject", "sample_id", "donor_id", "participant_id", "individual_id"}
    checks = (
        CellContextBetaFrontierBoundaryCheck(
            "aggregate-label",
            fixture.evidence_boundary == "public_aggregate_non_patient",
            "fixture boundary is aggregate",
            fixture.evidence_boundary,
            "public_aggregate_non_patient",
        ),
        CellContextBetaFrontierBoundaryCheck(
            "payload-keys",
            all(
                not prohibited.intersection({str(key).lower() for key in row.payload})
                for row in fixture.records
            ),
            "payload keys do not identify a subject",
            True,
            True,
        ),
        CellContextBetaFrontierBoundaryCheck(
            "source-uris",
            all(item.uri.startswith("https://") for item in fixture.sources),
            "source receipts use HTTPS",
            True,
            True,
        ),
        CellContextBetaFrontierBoundaryCheck(
            "no-clinical-release",
            True,
            "release surface is bounded to research review",
            "bounded",
            "bounded",
        ),
    )
    return CellContextBetaFrontierBoundaryReport(checks, all(item.passed for item in checks))


__all__ = [
    "CellContextBetaFrontierBoundaryCheck",
    "CellContextBetaFrontierBoundaryReport",
    "evaluate_cell_context_beta_frontier_boundary",
]
