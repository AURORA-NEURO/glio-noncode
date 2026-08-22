"""Depth ledger for context, margins, deltas, issues, and source versions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierDepthDimension:
    dimension_id: str
    observed: float
    target: float
    passed: bool
    evidence: tuple[str, ...]
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierDepthReport:
    dimensions: tuple[CellContextAlphaFrontierDepthDimension, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def mean_depth(self) -> float:
        return round(sum(item.observed for item in self.dimensions) / len(self.dimensions), 6)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"mean_depth": self.mean_depth}


def audit_cell_context_alpha_frontier_depth(
    fixture: CellContextAlphaFrontierFixture, evaluation: CellContextAlphaFrontierEvaluation
) -> CellContextAlphaFrontierDepthReport:
    dimensions = (
        CellContextAlphaFrontierDepthDimension(
            "operation-families",
            len({item.operation for item in fixture.records}) / 4,
            1.0,
            len({item.operation for item in fixture.records}) == 4,
            tuple(sorted({item.operation for item in fixture.records})),
            "all four alpha families are exercised",
        ),
        CellContextAlphaFrontierDepthDimension(
            "candidate-or-label-results",
            sum(bool(item.adapter.measurements.get("candidate_ids")) for item in evaluation.records)
            / 16,
            0.5,
            sum(bool(item.adapter.measurements.get("candidate_ids")) for item in evaluation.records)
            / 16
            >= 0.5,
            tuple(
                item.record_id
                for item in evaluation.records
                if item.adapter.measurements.get("candidate_ids")
            ),
            "candidate and label dimensions are retained",
        ),
        CellContextAlphaFrontierDepthDimension(
            "issue-controls",
            sum(bool(item.observed_issue_codes) for item in evaluation.records) / 4,
            1.0,
            sum(bool(item.observed_issue_codes) for item in evaluation.records) >= 4,
            tuple(item.record_id for item in evaluation.records if item.observed_issue_codes),
            "each family exposes an issue control",
        ),
        CellContextAlphaFrontierDepthDimension(
            "ambiguity-controls",
            sum(item.observed_state == "ambiguous" for item in evaluation.records) / 3,
            1.0,
            sum(item.observed_state == "ambiguous" for item in evaluation.records) >= 3,
            tuple(
                item.record_id for item in evaluation.records if item.observed_state == "ambiguous"
            ),
            "niche, territory, and phase ambiguity remain visible",
        ),
        CellContextAlphaFrontierDepthDimension(
            "domain-controls",
            sum(item.observed_state == "out_of_domain" for item in evaluation.records) / 4,
            1.0,
            sum(item.observed_state == "out_of_domain" for item in evaluation.records) == 4,
            tuple(
                item.record_id
                for item in evaluation.records
                if item.observed_state == "out_of_domain"
            ),
            "each operation refuses foreign context",
        ),
        CellContextAlphaFrontierDepthDimension(
            "delta-controls",
            sum(
                any(
                    value.get("support_delta") is not None
                    for value in item.adapter.measurements.get("results", ())
                    if isinstance(value, dict)
                )
                for item in evaluation.records
            )
            / 3,
            0.5,
            sum(
                any(
                    value.get("support_delta") is not None
                    for value in item.adapter.measurements.get("results", ())
                    if isinstance(value, dict)
                )
                for item in evaluation.records
            )
            >= 2,
            tuple(
                item.record_id
                for item in evaluation.records
                if any(
                    value.get("support_delta") is not None
                    for value in item.adapter.measurements.get("results", ())
                    if isinstance(value, dict)
                )
            ),
            "treatment delta values remain explicit",
        ),
    )
    return CellContextAlphaFrontierDepthReport(dimensions, all(item.passed for item in dimensions))


__all__ = [
    "CellContextAlphaFrontierDepthDimension",
    "CellContextAlphaFrontierDepthReport",
    "audit_cell_context_alpha_frontier_depth",
]
