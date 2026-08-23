"""Release manifest for the research planning surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseFixture
from .validation_release_frontier_lineage import ValidationReleaseLineage
from .validation_release_frontier_quality_gate import ValidationReleaseQualityReport
from .validation_release_frontier_replay import ValidationReleaseReplayReport


@dataclass(frozen=True, slots=True)
class ValidationReleaseManifest:
    release_id: str
    fixture_id: str
    version: str
    accepted: bool
    operation_ids: tuple[str, ...]
    quality_address: str
    lineage_address: str
    replay_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_manifest(fixture: ValidationReleaseFixture, evaluation: ValidationReleaseEvaluation, quality: ValidationReleaseQualityReport, lineage: ValidationReleaseLineage, replay: ValidationReleaseReplayReport, release_id: str = "validation-release-local") -> ValidationReleaseManifest:
    body = {"release_id": release_id, "fixture_id": fixture.fixture_id, "version": fixture.fixture_version, "accepted": quality.accepted and evaluation.accepted and replay.deterministic, "operation_ids": tuple(item.record_id for item in fixture.positive_records), "quality_address": quality.content_address, "lineage_address": lineage.content_address, "replay_address": replay.content_address}
    return ValidationReleaseManifest(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseManifest", "build_validation_release_manifest"]
