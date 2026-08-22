"""Runtime orchestration for Domain 09 topology frontier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .topology_frontier_public_data import (
    TopologyFrontierFixture,
    default_topology_frontier_fixture,
)
from .topology_frontier_quality_gate import (
    TopologyFrontierQualityReport,
    run_topology_frontier_quality_gate,
)


@dataclass(frozen=True, slots=True)
class TopologyFrontierRuntimeOptions:
    run_id: str = "topology-frontier-default"
    fixture_id: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.run_id, "run_id")


@dataclass(frozen=True, slots=True)
class TopologyFrontierRuntimeResult:
    run_id: str
    fixture_id: str
    fixture_version: str
    status: str
    quality: TopologyFrontierQualityReport
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.status == "accepted" and self.quality.accepted

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def run_topology_frontier_pipeline(
    options: TopologyFrontierRuntimeOptions | None = None,
    *,
    fixture: TopologyFrontierFixture | None = None,
) -> TopologyFrontierRuntimeResult:
    selected_options = options or TopologyFrontierRuntimeOptions()
    selected = fixture or default_topology_frontier_fixture()
    quality = run_topology_frontier_quality_gate(selected)
    status = "accepted" if quality.accepted else "rejected"
    body = {
        "run_id": selected_options.run_id,
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "status": status,
        "quality": quality,
    }
    return TopologyFrontierRuntimeResult(**body, content_address=content_hash(body))


__all__ = [
    "TopologyFrontierRuntimeOptions",
    "TopologyFrontierRuntimeResult",
    "run_topology_frontier_pipeline",
]
