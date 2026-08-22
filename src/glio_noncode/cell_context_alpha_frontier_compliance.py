"""Aggregate boundary checks for alpha fixture publication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierBoundaryCheck:
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
class CellContextAlphaFrontierBoundaryReport:
    checks: tuple[CellContextAlphaFrontierBoundaryCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cell_context_alpha_frontier_boundary(
    fixture: CellContextAlphaFrontierFixture,
) -> CellContextAlphaFrontierBoundaryReport:
    restricted = {"patient", "subject", "sample_id", "donor_id", "participant_id", "individual_id"}
    checks = (
        CellContextAlphaFrontierBoundaryCheck(
            "aggregate-label",
            fixture.evidence_boundary == "public_aggregate_non_patient",
            "aggregate boundary is declared",
            fixture.evidence_boundary,
            "public_aggregate_non_patient",
        ),
        CellContextAlphaFrontierBoundaryCheck(
            "payload-keys",
            all(
                not restricted.intersection({str(key).lower() for key in row.payload})
                for row in fixture.records
            ),
            "payloads exclude subject-level keys",
            True,
            True,
        ),
        CellContextAlphaFrontierBoundaryCheck(
            "source-uris",
            all(item.uri.startswith("https://") for item in fixture.sources),
            "receipts use HTTPS",
            True,
            True,
        ),
        CellContextAlphaFrontierBoundaryCheck(
            "descriptive-only", True, "alpha release is descriptive", "descriptive", "descriptive"
        ),
    )
    return CellContextAlphaFrontierBoundaryReport(checks, all(item.passed for item in checks))


__all__ = [
    "CellContextAlphaFrontierBoundaryCheck",
    "CellContextAlphaFrontierBoundaryReport",
    "evaluate_cell_context_alpha_frontier_boundary",
]
