"""Release decision and manifest for the C09-C12 aggregate plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_runtime import SequenceRegulationRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationReleaseManifest:
    release_id: str
    release_version: str
    fixture_id: str
    run_id: str
    accepted: bool
    artifact_addresses: tuple[str, ...]
    cautions: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.release_id or not self.release_version or not self.artifact_addresses:
            raise ValidationError("release manifest is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_regulation_release(
    runtime: SequenceRegulationRuntimeReport,
) -> SequenceRegulationReleaseManifest:
    addresses = (
        runtime.data.content_address,
        runtime.schema.content_address,
        runtime.evaluation.content_address,
        runtime.metrics.content_address,
        runtime.lineage.content_address,
        runtime.policy.content_address,
        runtime.quality.content_address,
    )
    return SequenceRegulationReleaseManifest(
        release_id="glio-noncode-d06-c09-c12",
        release_version="2026.08.22",
        fixture_id=runtime.evaluation.fixture_id,
        run_id=runtime.run_id,
        accepted=runtime.accepted,
        artifact_addresses=addresses,
        cautions=(
            "Sequence scores and motif paths are observations, not calibrated effect estimates.",
            "Aggregate controls do not establish clinical, causal, or subject-specific claims.",
            "Context mismatches and ambiguous bases remain visible in result states.",
        ),
    )


__all__ = ["SequenceRegulationReleaseManifest", "build_sequence_regulation_release"]
