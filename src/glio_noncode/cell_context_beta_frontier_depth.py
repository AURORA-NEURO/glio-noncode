"""Depth audit for context, source, candidate, uncertainty, and refusal detail."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .cell_context_beta_frontier_public_data import CellContextBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierDepthDimension:
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
class CellContextBetaFrontierDepthReport:
    dimensions: tuple[CellContextBetaFrontierDepthDimension, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.dimensions:
            raise ValueError("beta depth report is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def mean_depth(self) -> float:
        return round(sum(item.observed for item in self.dimensions) / len(self.dimensions), 6)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"mean_depth": self.mean_depth}


def audit_cell_context_beta_frontier_depth(
    fixture: CellContextBetaFrontierFixture, evaluation: CellContextBetaFrontierEvaluation
) -> CellContextBetaFrontierDepthReport:
    dimensions = (
        CellContextBetaFrontierDepthDimension(
            "context-gates",
            1.0
            if len({item.payload.get("target_context_key") for item in fixture.records}) >= 4
            else 0.0,
            1.0,
            len({item.payload.get("target_context_key") for item in fixture.records}) >= 4,
            tuple(
                sorted({str(item.payload.get("target_context_key")) for item in fixture.records})
            ),
            "four target context families are exercised",
        ),
        CellContextBetaFrontierDepthDimension(
            "candidate-alternatives",
            sum(bool(item.adapter.measurements.get("candidate_ids")) for item in evaluation.records)
            / len(evaluation.records),
            0.75,
            sum(bool(item.adapter.measurements.get("candidate_ids")) for item in evaluation.records)
            / len(evaluation.records)
            >= 0.75,
            tuple(
                item.record_id
                for item in evaluation.records
                if len(item.adapter.measurements.get("candidate_ids", ())) > 1
            ),
            "candidate alternatives remain visible",
        ),
        CellContextBetaFrontierDepthDimension(
            "uncertainty",
            sum(
                float(item.adapter.measurements.get("uncertainty", 1.0)) < 1.0
                for item in evaluation.records
            )
            / len(evaluation.records),
            0.5,
            sum(
                float(item.adapter.measurements.get("uncertainty", 1.0)) < 1.0
                for item in evaluation.records
            )
            / len(evaluation.records)
            >= 0.5,
            tuple(
                item.record_id
                for item in evaluation.records
                if float(item.adapter.measurements.get("uncertainty", 1.0)) < 1.0
            ),
            "bounded uncertainty is emitted",
        ),
        CellContextBetaFrontierDepthDimension(
            "refusal-paths",
            sum(item.observed_state == "out_of_domain" for item in evaluation.records) / 4,
            1.0,
            sum(item.observed_state == "out_of_domain" for item in evaluation.records) >= 4,
            tuple(
                item.record_id
                for item in evaluation.records
                if item.observed_state == "out_of_domain"
            ),
            "each gate has an explicit refusal",
        ),
        CellContextBetaFrontierDepthDimension(
            "quarantine-paths",
            sum(
                "invalid_context_prior_row" in item.observed_issue_codes
                for item in evaluation.records
            )
            / 4,
            1.0,
            sum(
                "invalid_context_prior_row" in item.observed_issue_codes
                for item in evaluation.records
            )
            >= 4,
            tuple(item.record_id for item in evaluation.records if item.observed_issue_codes),
            "each operation exposes parser quarantine",
        ),
        CellContextBetaFrontierDepthDimension(
            "source-version-retention",
            sum(
                bool(item.adapter.measurements.get("source_versions"))
                for item in evaluation.records
            )
            / len(evaluation.records),
            1.0,
            all(
                bool(item.adapter.measurements.get("source_versions"))
                for item in evaluation.records
            ),
            tuple(
                sorted(
                    {
                        version
                        for item in evaluation.records
                        for version in item.adapter.measurements.get("source_versions", ())
                    }
                )
            ),
            "source versions survive execution",
        ),
    )
    return CellContextBetaFrontierDepthReport(dimensions, all(item.passed for item in dimensions))


__all__ = [
    "CellContextBetaFrontierDepthDimension",
    "CellContextBetaFrontierDepthReport",
    "audit_cell_context_beta_frontier_depth",
]
