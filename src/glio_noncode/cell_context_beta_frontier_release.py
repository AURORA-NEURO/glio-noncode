"""Release manifest for a bounded beta prior tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .cell_context_beta_frontier_public_data import CellContextBetaFrontierFixture
from .cell_context_beta_frontier_quality_gate import CellContextBetaFrontierQualityReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierReleaseManifest:
    release_id: str
    fixture_id: str
    fixture_version: str
    boundary: str
    record_count: int
    quality_accepted: bool
    evaluation_accepted: bool
    allowed_consumers: tuple[str, ...]
    prohibited_interpretations: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.release_id or not self.allowed_consumers or not self.prohibited_interpretations:
            raise ValueError("beta release manifest is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def publishable(self) -> bool:
        return self.quality_accepted and self.evaluation_accepted

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"publishable": self.publishable}


def build_cell_context_beta_frontier_release(
    fixture: CellContextBetaFrontierFixture,
    evaluation: CellContextBetaFrontierEvaluation,
    quality: CellContextBetaFrontierQualityReport,
) -> CellContextBetaFrontierReleaseManifest:
    return CellContextBetaFrontierReleaseManifest(
        "d08-c05-c08-beta-release",
        fixture.fixture_id,
        fixture.fixture_version,
        fixture.evidence_boundary,
        len(fixture.records),
        quality.accepted,
        evaluation.accepted,
        ("research-review", "fixture-replay", "quality-audit"),
        ("diagnosis", "prognosis", "treatment-selection", "calibrated-probability"),
    )


__all__ = ["CellContextBetaFrontierReleaseManifest", "build_cell_context_beta_frontier_release"]
