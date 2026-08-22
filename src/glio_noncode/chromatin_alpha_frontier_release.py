"""Release manifest for the C09-C12 chromatin-alpha evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_runtime import ChromatinAlphaFrontierRuntimeReport
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReleaseManifest:
    release_id: str
    release_version: str
    fixture_id: str
    run_id: str
    accepted: bool
    artifact_addresses: tuple[str, ...]
    cautions: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.release_id
            or not self.release_version
            or not self.fixture_id
            or not self.artifact_addresses
        ):
            raise ValidationError("release manifest is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_alpha_frontier_release(
    runtime: ChromatinAlphaFrontierRuntimeReport,
) -> ChromatinAlphaFrontierReleaseManifest:
    addresses = (
        runtime.data.content_address,
        runtime.schema.content_address,
        runtime.evaluation.content_address,
        runtime.metrics.content_address,
        runtime.lineage.content_address,
        runtime.policy.content_address,
        runtime.reconciliation.content_address,
        runtime.quality.content_address,
    )
    return ChromatinAlphaFrontierReleaseManifest(
        release_id="glio-noncode-d07-c09-c12",
        release_version="2026.08.22",
        fixture_id=runtime.evaluation.fixture_id,
        run_id=runtime.run_id,
        accepted=runtime.accepted,
        artifact_addresses=addresses,
        cautions=(
            "Chromatin state labels summarize observed intervals and are not activity claims.",
            "Allele-specific deltas are descriptive signal differences and not causal effects.",
            (
                "Purity and correction outputs require declared references and remain "
                "research-use summaries."
            ),
        ),
    )


__all__ = ["ChromatinAlphaFrontierReleaseManifest", "build_chromatin_alpha_frontier_release"]
