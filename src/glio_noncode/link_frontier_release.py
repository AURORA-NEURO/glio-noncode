"""Release manifest construction for Domain 10 link evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_frontier_public_data import LinkFrontierFixture, default_link_frontier_fixture
from .link_frontier_runtime import LinkFrontierPipeline, run_link_frontier_pipeline
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class LinkFrontierReleaseManifest:
    release_id: str
    release_version: str
    fixture_id: str
    context_key: str
    evidence_boundary: str
    pipeline_address: str
    quality_gate_address: str
    record_count: int
    source_count: int
    state: str
    limitations: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.release_id, "release_id")
        require_non_empty(self.release_version, "release_version")
        require_non_empty(self.state, "state")
        if not self.limitations:
            raise ValueError("link release must list limitations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_link_frontier_release(
    fixture: LinkFrontierFixture | None = None,
    *,
    pipeline: LinkFrontierPipeline | None = None,
    release_id: str = "link-frontier-release",
) -> LinkFrontierReleaseManifest:
    fixture = fixture or default_link_frontier_fixture()
    pipeline = pipeline or run_link_frontier_pipeline(fixture)
    body = {
        "release_id": release_id,
        "release_version": "2026.08.d10-c13-c16.v1",
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "pipeline_address": pipeline.content_address,
        "quality_gate_address": pipeline.quality_gate.content_address,
        "record_count": len(fixture.records),
        "source_count": len(fixture.sources),
        "state": "released" if pipeline.accepted else "blocked",
        "limitations": (
            "public aggregate evidence only",
            "candidate link structure is not causal regulation",
            "target-gene ranking retains alternatives and is not a clinical conclusion",
            "calibration thresholds are descriptive and require external validation",
        ),
    }
    return LinkFrontierReleaseManifest(**body, content_address=content_hash(body))


__all__ = ["LinkFrontierReleaseManifest", "build_link_frontier_release"]
