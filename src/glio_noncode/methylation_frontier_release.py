"""Release manifest for the D07 C05-C08 aggregate plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_runtime import MethylationFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierReleaseManifest:
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


def build_methylation_frontier_release(
    runtime: MethylationFrontierRuntimeReport,
) -> MethylationFrontierReleaseManifest:
    addresses = (
        runtime.data.content_address,
        runtime.schema.content_address,
        runtime.evaluation.content_address,
        runtime.metrics.content_address,
        runtime.lineage.content_address,
        runtime.policy.content_address,
        runtime.quality.content_address,
    )
    return MethylationFrontierReleaseManifest(
        release_id="glio-noncode-d07-c05-c08",
        release_version="2026.08.22",
        fixture_id=runtime.evaluation.fixture_id,
        run_id=runtime.run_id,
        accepted=runtime.accepted,
        artifact_addresses=addresses,
        cautions=(
            (
                "Methylation retrieval preserves measured values and does not "
                "impute missing beta values."
            ),
            "CpG creation or loss is a sequence observation and not proof of a methylation change.",
            "The IDH result is a descriptive aggregate panel context, not a diagnostic classifier.",
        ),
    )


__all__ = ["MethylationFrontierReleaseManifest", "build_methylation_frontier_release"]
