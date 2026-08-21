"""Runtime orchestration for a C13-C16 public aggregate run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .frontier_atlas_public_data import FrontierAtlasFixture, default_frontier_atlas_fixture
from .frontier_atlas_quality_gate import FrontierAtlasQualityReport, run_frontier_atlas_quality_gate
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class FrontierAtlasRuntimeOptions:
    run_id: str
    fail_on_review: bool = False
    requested_context_key: str | None = None
    source_mode: str = "public_aggregate_fixture"

    def __post_init__(self) -> None:
        require_non_empty(self.run_id, "run_id")
        if self.source_mode != "public_aggregate_fixture":
            raise ValueError("unsupported frontier atlas source mode")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasRuntimeResult:
    run_id: str
    started_at: str
    completed_at: str
    source_mode: str
    requested_context_key: str | None
    quality: FrontierAtlasQualityReport
    status: str
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def run_frontier_atlas_pipeline(
    options: FrontierAtlasRuntimeOptions | None = None,
    *,
    fixture: FrontierAtlasFixture | None = None,
) -> FrontierAtlasRuntimeResult:
    selected_options = options or FrontierAtlasRuntimeOptions(run_id="frontier-atlas-local")
    selected_fixture = fixture or default_frontier_atlas_fixture()
    started = datetime.now(UTC).isoformat()
    quality = run_frontier_atlas_quality_gate(selected_fixture)
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
    return FrontierAtlasRuntimeResult(**body, content_address=content_hash(body))


__all__ = [
    "FrontierAtlasRuntimeOptions",
    "FrontierAtlasRuntimeResult",
    "run_frontier_atlas_pipeline",
]
