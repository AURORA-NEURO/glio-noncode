"""Artifact inventory with explicit raw-payload and review boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_bundle import CellContextBetaFrontierBundle
from .cell_context_beta_frontier_exports import (
    export_cell_context_beta_frontier_review_csv,
    render_cell_context_beta_frontier_review_markdown,
)
from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierArtifact:
    artifact_id: str
    media_type: str
    body: str
    contains_raw_payload: bool
    review_safe: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.media_type:
            raise ValueError("beta artifact is incomplete")
        if self.contains_raw_payload and self.review_safe:
            raise ValueError("raw beta payload cannot be review safe")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierArtifactInventory:
    artifacts: tuple[CellContextBetaFrontierArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.artifacts:
            raise ValueError("beta artifact inventory is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_beta_frontier_artifacts(
    bundle: CellContextBetaFrontierBundle, evaluation: CellContextBetaFrontierEvaluation
) -> CellContextBetaFrontierArtifactInventory:
    artifacts = (
        CellContextBetaFrontierArtifact(
            "beta-review-csv",
            "text/csv",
            export_cell_context_beta_frontier_review_csv(evaluation),
            False,
            True,
        ),
        CellContextBetaFrontierArtifact(
            "beta-review-markdown",
            "text/markdown",
            render_cell_context_beta_frontier_review_markdown(evaluation),
            False,
            True,
        ),
        CellContextBetaFrontierArtifact(
            "beta-bundle-address", "text/plain", bundle.content_address, False, True
        ),
    )
    return CellContextBetaFrontierArtifactInventory(artifacts, bundle.accepted)


__all__ = [
    "CellContextBetaFrontierArtifact",
    "CellContextBetaFrontierArtifactInventory",
    "build_cell_context_beta_frontier_artifacts",
]
