"""Release manifest and promotion decision for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_runtime import ChromatinContextFrontierRuntimeReport
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierReleaseManifest:
    release_id: str
    run_id: str
    release_status: str
    supported_operations: tuple[str, ...]
    refusal_paths: tuple[str, ...]
    review_paths: tuple[str, ...]
    source_count: int
    record_count: int
    quality_passed_count: int
    quality_failed_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.release_id or not self.run_id:
            raise ValidationError("release identity is required")
        if self.release_status not in {"release_candidate", "held", "rejected"}:
            raise ValidationError("release status is invalid")
        if not self.supported_operations or not self.limitations:
            raise ValidationError("release manifest is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_context_frontier_release(
    runtime: ChromatinContextFrontierRuntimeReport,
    *,
    release_id: str = "glio-noncode-d07-c01-c04",
) -> ChromatinContextFrontierReleaseManifest:
    supported = tuple(item.operation.value for item in runtime.contracts.contracts)
    refusals = tuple(
        sorted(
            {
                item.observed_state
                for item in runtime.evaluation.control_rows
                if item.observed_state == "out_of_domain"
            }
        )
    )
    review = tuple(
        sorted(
            {
                item.observed_state
                for item in runtime.evaluation.control_rows
                if item.observed_state in {"partial", "ambiguous", "abstained", "invalid"}
            }
        )
    )
    accepted = runtime.accepted and runtime.quality.accepted
    return ChromatinContextFrontierReleaseManifest(
        release_id=release_id,
        run_id=runtime.run_id,
        release_status="release_candidate" if accepted else "held",
        supported_operations=supported,
        refusal_paths=refusals,
        review_paths=review,
        source_count=len(runtime.data.checks),
        record_count=len(runtime.evaluation.records),
        quality_passed_count=runtime.quality.passed_count,
        quality_failed_ids=runtime.quality.failed_check_ids,
        limitations=(
            "Public aggregate fixtures prove deterministic plumbing, not clinical validity.",
            "Coordinate overlap does not infer enhancer function or target linkage.",
            "Cross-assay calibration and external transport remain open evidence work.",
        ),
        accepted=accepted,
    )


__all__ = [
    "ChromatinContextFrontierReleaseManifest",
    "build_chromatin_context_frontier_release",
]
