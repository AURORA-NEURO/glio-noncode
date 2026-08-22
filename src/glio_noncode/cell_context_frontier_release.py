"""Release manifest for the Domain 08 context plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_runtime import CellContextFrontierRuntimeReport
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierReleaseManifest:
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
        if not self.release_id or not self.run_id or not self.supported_operations:
            raise ValidationError("cell release identity is incomplete")
        if self.release_status not in {"release_candidate", "held", "rejected"}:
            raise ValidationError("cell release status is invalid")
        if not self.limitations:
            raise ValidationError("cell release requires limitations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_frontier_release(
    runtime: CellContextFrontierRuntimeReport, *, release_id: str = "glio-noncode-d08-c01-c04"
) -> CellContextFrontierReleaseManifest:
    release_ready = runtime.accepted and runtime.quality.accepted
    return CellContextFrontierReleaseManifest(
        release_id,
        runtime.run_id,
        "release_candidate" if release_ready else "held",
        tuple(item.operation.value for item in runtime.contracts.contracts),
        tuple(
            sorted(
                {
                    item.observed_state
                    for item in runtime.evaluation.control_rows
                    if item.observed_state == "out_of_domain"
                }
            )
        ),
        tuple(
            sorted(
                {
                    item.observed_state
                    for item in runtime.evaluation.control_rows
                    if item.observed_state in {"ambiguous", "contradictory", "partial", "abstained"}
                }
            )
        ),
        len(runtime.data.checks),
        len(runtime.evaluation.records),
        runtime.quality.passed_count,
        runtime.quality.failed_check_ids,
        (
            "Context taxonomy observations are descriptive public aggregate evidence.",
            "Exact context gating does not establish disease, prognosis, or treatment.",
            "External calibration, subgroup transport, and OOD evaluation remain open.",
        ),
        release_ready,
    )


__all__ = ["CellContextFrontierReleaseManifest", "build_cell_context_frontier_release"]
