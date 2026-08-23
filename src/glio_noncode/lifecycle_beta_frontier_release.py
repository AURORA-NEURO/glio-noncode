"""Release manifest for a research-only lifecycle beta frontier build."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_lineage import LifecycleBetaFrontierLineageReport
from .lifecycle_beta_frontier_quality_gate import LifecycleBetaFrontierQualityReport
from .lifecycle_beta_frontier_replay import LifecycleBetaFrontierReplayReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReleaseManifest:
    release_id: str
    fixture_id: str
    version: str
    research_use_only: bool
    accepted: bool
    artifact_addresses: dict[str, str]
    required_review: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_release(fixture: LifecycleBetaFrontierFixture, evaluation: LifecycleBetaFrontierEvaluation, quality: LifecycleBetaFrontierQualityReport, lineage: LifecycleBetaFrontierLineageReport, replay: LifecycleBetaFrontierReplayReport, *, release_id: str = "lifecycle-beta-frontier-release") -> LifecycleBetaFrontierReleaseManifest:
    artifacts = {"fixture": fixture.content_address, "evaluation": evaluation.content_address, "quality": quality.content_address, "lineage": lineage.content_address, "replay": replay.content_address}
    required = () if quality.accepted and replay.deterministic else ("quality_gate_or_replay_failure",)
    body = {"release_id": release_id, "fixture_id": fixture.fixture_id, "version": fixture.fixture_version, "research_use_only": True, "accepted": not required, "artifact_addresses": artifacts, "required_review": required}
    return LifecycleBetaFrontierReleaseManifest(**body, content_address=content_hash(body))


def write_lifecycle_beta_frontier_release(manifest: LifecycleBetaFrontierReleaseManifest, path: str) -> None:
    from pathlib import Path
    Path(path).write_text(__import__("json").dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


__all__ = ["LifecycleBetaFrontierReleaseManifest", "build_lifecycle_beta_frontier_release", "write_lifecycle_beta_frontier_release"]
