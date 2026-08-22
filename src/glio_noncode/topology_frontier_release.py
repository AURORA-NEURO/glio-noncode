"""Release manifest construction for Domain 09 topology evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .topology_frontier_quality_gate import TopologyFrontierQualityReport


@dataclass(frozen=True, slots=True)
class TopologyFrontierReleaseManifest:
    release_id: str
    fixture_id: str
    fixture_version: str
    run_id: str
    context_key: str
    evidence_boundary: str
    release_state: str
    source_ids: tuple[str, ...]
    record_count: int
    positive_count: int
    control_count: int
    bundle_address: str
    record_address: str
    release_address: str

    def __post_init__(self) -> None:
        for name in ("release_id", "fixture_id", "fixture_version", "run_id", "context_key", "evidence_boundary", "release_state", "bundle_address", "record_address", "release_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_topology_frontier_release(
    quality: TopologyFrontierQualityReport,
    *,
    run_id: str,
    release_id: str,
) -> TopologyFrontierReleaseManifest:
    if not quality.accepted:
        raise ValidationError("topology release requires an accepted quality report")
    bundle = quality.bundle
    body = {
        "release_id": release_id,
        "fixture_id": bundle.fixture_id,
        "fixture_version": bundle.fixture_version,
        "run_id": run_id,
        "context_key": bundle.context_key,
        "evidence_boundary": bundle.evidence_boundary,
        "release_state": "accepted",
        "source_ids": bundle.source_ids,
        "record_count": len(bundle.record_ids),
        "positive_count": bundle.metrics.total_positive,
        "control_count": bundle.metrics.total_controls,
        "bundle_address": bundle.bundle_address,
        "record_address": bundle.evaluation.content_address,
    }
    return TopologyFrontierReleaseManifest(**body, release_address=content_hash(body))


__all__ = [
    "TopologyFrontierReleaseManifest",
    "build_topology_frontier_release",
]
