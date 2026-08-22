"""Artifact inventory for review-safe alpha outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_bundle import CellContextAlphaFrontierBundle
from .cell_context_alpha_frontier_exports import (
    export_cell_context_alpha_frontier_review_csv,
    render_cell_context_alpha_frontier_review_markdown,
)
from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierArtifact:
    artifact_id: str
    media_type: str
    body: str
    contains_raw_payload: bool
    review_safe: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.contains_raw_payload and self.review_safe:
            raise ValueError("raw alpha payload cannot be review safe")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierArtifactInventory:
    artifacts: tuple[CellContextAlphaFrontierArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_alpha_frontier_artifacts(
    bundle: CellContextAlphaFrontierBundle, evaluation: CellContextAlphaFrontierEvaluation
) -> CellContextAlphaFrontierArtifactInventory:
    artifacts = (
        CellContextAlphaFrontierArtifact(
            "alpha-review-csv",
            "text/csv",
            export_cell_context_alpha_frontier_review_csv(evaluation),
            False,
            True,
        ),
        CellContextAlphaFrontierArtifact(
            "alpha-review-markdown",
            "text/markdown",
            render_cell_context_alpha_frontier_review_markdown(evaluation),
            False,
            True,
        ),
        CellContextAlphaFrontierArtifact(
            "alpha-bundle-address", "text/plain", bundle.content_address, False, True
        ),
    )
    return CellContextAlphaFrontierArtifactInventory(artifacts, bundle.accepted)


__all__ = [
    "CellContextAlphaFrontierArtifact",
    "CellContextAlphaFrontierArtifactInventory",
    "build_cell_context_alpha_frontier_artifacts",
]
