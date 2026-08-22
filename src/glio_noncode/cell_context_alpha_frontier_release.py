"""Bounded release manifest for context-alpha priors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierFixture
from .cell_context_alpha_frontier_quality_gate import CellContextAlphaFrontierQualityReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierReleaseManifest:
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
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def publishable(self) -> bool:
        return self.quality_accepted and self.evaluation_accepted

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"publishable": self.publishable}


def build_cell_context_alpha_frontier_release(
    fixture: CellContextAlphaFrontierFixture,
    evaluation: CellContextAlphaFrontierEvaluation,
    quality: CellContextAlphaFrontierQualityReport,
) -> CellContextAlphaFrontierReleaseManifest:
    return CellContextAlphaFrontierReleaseManifest(
        "d08-c09-c12-alpha-release",
        fixture.fixture_id,
        fixture.fixture_version,
        fixture.evidence_boundary,
        len(fixture.records),
        quality.accepted,
        evaluation.accepted,
        ("research-review", "descriptive-comparison", "fixture-replay"),
        ("diagnosis", "prognosis", "treatment-response-claim", "localization-claim"),
    )


__all__ = ["CellContextAlphaFrontierReleaseManifest", "build_cell_context_alpha_frontier_release"]
