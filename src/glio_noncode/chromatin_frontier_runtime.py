"""Runtime boundary for Domain 07 public aggregate evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .chromatin_frontier_public_data import (
    ChromatinFrontierFixture,
    default_chromatin_frontier_fixture,
)
from .chromatin_frontier_quality_gate import (
    ChromatinFrontierQualityReport,
    run_chromatin_frontier_quality_gate,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ChromatinFrontierRuntimeOptions:
    run_id: str
    fail_on_review: bool = False
    requested_context_key: str | None = None
    source_mode: str = "public_aggregate_fixture"

    def __post_init__(self) -> None:
        require_non_empty(self.run_id, "run_id")
        if self.source_mode != "public_aggregate_fixture":
            raise ValueError("unsupported chromatin frontier source mode")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierRuntimeResult:
    run_id: str
    started_at: str
    completed_at: str
    source_mode: str
    requested_context_key: str | None
    quality: ChromatinFrontierQualityReport
    status: str
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def run_chromatin_frontier_pipeline(
    options: ChromatinFrontierRuntimeOptions | None = None,
    *,
    fixture: ChromatinFrontierFixture | None = None,
) -> ChromatinFrontierRuntimeResult:
    selected_options = options or ChromatinFrontierRuntimeOptions(run_id="chromatin-frontier-local")
    selected_fixture = fixture or default_chromatin_frontier_fixture()
    started = datetime.now(UTC).isoformat()
    quality = run_chromatin_frontier_quality_gate(selected_fixture)
    context_ok = selected_options.requested_context_key in {None, selected_fixture.context_key}
    status = (
        "accepted"
        if quality.accepted
        and context_ok
        and not (selected_options.fail_on_review and quality.bundle.metrics.review_records)
        else "rejected"
    )
    completed = datetime.now(UTC).isoformat()
    body = {
        "run_id": selected_options.run_id,
        "started_at": started,
        "completed_at": completed,
        "source_mode": selected_options.source_mode,
        "requested_context_key": selected_options.requested_context_key,
        "quality": quality,
        "status": status,
    }
    return ChromatinFrontierRuntimeResult(**body, content_address=content_hash(body))


__all__ = [
    "ChromatinFrontierRuntimeOptions",
    "ChromatinFrontierRuntimeResult",
    "run_chromatin_frontier_pipeline",
]
