"""Canonical JSON, CSV, and Markdown export envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_artifacts import CausalAlphaFrontierArtifactInventory
from .causal_alpha_frontier_bundle import CausalAlphaFrontierReleaseBundle
from .causal_alpha_frontier_controls import CausalAlphaFrontierControlCoverage
from .causal_alpha_frontier_diagnostics import CausalAlphaFrontierDiagnosticReport
from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .causal_alpha_frontier_release import CausalAlphaFrontierReleaseManifest
from .causal_alpha_frontier_projections import CausalAlphaFrontierProjectionReport
from .causal_alpha_frontier_traces import CausalAlphaFrontierTraceLedger
from .causal_alpha_frontier_views import CausalAlphaFrontierReviewView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierExportEnvelope:
    export_id: str
    media_type: str
    payload: Any
    source_address: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"export_id": self.export_id, "media_type": self.media_type, "payload": jsonable(self.payload), "source_address": self.source_address}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierExportInventory:
    fixture_id: str
    envelopes: tuple[CausalAlphaFrontierExportEnvelope, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def by_id(self, export_id: str) -> CausalAlphaFrontierExportEnvelope:
        return next(item for item in self.envelopes if item.export_id == export_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "envelopes": [item.to_dict() for item in self.envelopes], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_exports(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, view: CausalAlphaFrontierReviewView, bundle: CausalAlphaFrontierReleaseBundle, release: CausalAlphaFrontierReleaseManifest, artifacts: CausalAlphaFrontierArtifactInventory, controls: CausalAlphaFrontierControlCoverage | None = None, traces: CausalAlphaFrontierTraceLedger | None = None, projections: CausalAlphaFrontierProjectionReport | None = None, diagnostics: CausalAlphaFrontierDiagnosticReport | None = None) -> CausalAlphaFrontierExportInventory:
    envelopes = (
        CausalAlphaFrontierExportEnvelope("fixture", "application/json", fixture.to_dict(), fixture.content_address),
        CausalAlphaFrontierExportEnvelope("evaluation", "application/json", evaluation.to_dict(), evaluation.content_address),
        CausalAlphaFrontierExportEnvelope("controls", "application/json", controls.to_dict() if controls else {}, controls.content_address if controls else ""),
        CausalAlphaFrontierExportEnvelope("traces", "application/json", traces.to_dict() if traces else {}, traces.content_address if traces else ""),
        CausalAlphaFrontierExportEnvelope("projections", "application/json", projections.to_dict() if projections else {}, projections.content_address if projections else ""),
        CausalAlphaFrontierExportEnvelope("diagnostics", "application/json", diagnostics.to_dict() if diagnostics else {}, diagnostics.content_address if diagnostics else ""),
        CausalAlphaFrontierExportEnvelope("summary", "application/json", {"fixture_id": fixture.fixture_id, "accepted": evaluation.accepted, "record_count": len(evaluation.evaluation.results), "release_state": release.state, "artifact_count": len(artifacts.artifacts)}, bundle.content_address),
        CausalAlphaFrontierExportEnvelope("review-csv", "text/csv", view.to_markdown(), view.content_address),
        CausalAlphaFrontierExportEnvelope("review-markdown", "text/markdown", view.to_markdown(), view.content_address),
        CausalAlphaFrontierExportEnvelope("release", "application/json", release.to_dict(), release.content_address),
    )
    return CausalAlphaFrontierExportInventory(fixture.fixture_id, envelopes, len(envelopes) == 10 and all(item.content_address for item in envelopes))


__all__ = ["CausalAlphaFrontierExportEnvelope", "CausalAlphaFrontierExportInventory", "build_causal_alpha_frontier_exports"]
