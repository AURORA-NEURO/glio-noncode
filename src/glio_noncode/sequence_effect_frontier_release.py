"""Release manifest for the sequence-effect frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_quality_gate import SequenceEffectQualityReport
from .sequence_effect_frontier_runtime import SequenceEffectRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectReleaseManifest:
    release_id: str
    state: str
    fixture_address: str
    quality_address: str
    runtime_address: str
    operation_ids: tuple[str, ...]
    accepted_count: int
    review_count: int
    checks: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.release_id.strip() or not self.operation_ids:
            raise ValueError("release manifest identity and operations are required")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "release_id": self.release_id,
                        "state": self.state,
                        "fixture_address": self.fixture_address,
                        "quality_address": self.quality_address,
                        "runtime_address": self.runtime_address,
                        "operation_ids": self.operation_ids,
                        "accepted_count": self.accepted_count,
                        "review_count": self.review_count,
                        "checks": self.checks,
                    }
                ),
            )

    @property
    def accepted(self) -> bool:
        return self.state == "ready" and all(self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_sequence_effect_release(
    quality: SequenceEffectQualityReport,
    runtime: SequenceEffectRuntimeReport,
    release_id: str = "sequence-effect-release",
) -> SequenceEffectReleaseManifest:
    checks = (
        "quality-accepted" if quality.accepted else "quality-rejected",
        "runtime-accepted" if runtime.accepted else "runtime-rejected",
        "fixture-addressed"
        if quality.evaluation.fixture_address.startswith("sha256:")
        else "fixture-unaddressed",
        "operations-complete"
        if len(quality.metrics.operation_metrics) == 4
        else "operations-incomplete",
        "controls-retained" if quality.evaluation.control_count == 12 else "controls-missing",
    )
    return SequenceEffectReleaseManifest(
        release_id,
        "ready"
        if all(
            item.endswith("accepted")
            or item.endswith("addressed")
            or item.endswith("complete")
            or item.endswith("retained")
            for item in checks
        )
        else "blocked",
        quality.evaluation.fixture_address,
        quality.content_address,
        runtime.content_address,
        tuple(item.operation.value for item in quality.schema.schemas),
        quality.metrics.accepted_records,
        quality.metrics.review_records,
        checks,
    )


__all__ = ["SequenceEffectReleaseManifest", "build_sequence_effect_release"]
