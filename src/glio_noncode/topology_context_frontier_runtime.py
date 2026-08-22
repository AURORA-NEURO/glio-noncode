"""Runtime limits and execution wrapper for topology context."""

from __future__ import annotations

from dataclasses import dataclass

from .topology_context_frontier_pipeline import (
    TopologyContextFrontierPipelineReport,
    run_topology_context_frontier_pipeline,
)
from .topology_context_frontier_public_data import (
    TopologyContextFrontierFixture,
    default_topology_context_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierRuntimeOptions:
    max_records: int = 16
    require_aggregate: bool = True
    run_id: str = "topology-context-frontier-runtime"


def run_topology_context_frontier_runtime(
    options: TopologyContextFrontierRuntimeOptions | None = None,
    *,
    fixture: TopologyContextFrontierFixture | None = None,
) -> TopologyContextFrontierPipelineReport:
    selected = options or TopologyContextFrontierRuntimeOptions()
    value = fixture or default_topology_context_frontier_fixture()
    if selected.max_records < len(value.records):
        raise ValueError("topology runtime record limit is below the fixture size")
    if selected.require_aggregate and value.boundary != "public_aggregate_non_patient":
        raise ValueError("topology runtime requires aggregate data")
    return run_topology_context_frontier_pipeline(value, run_id=selected.run_id)


__all__ = [
    "TopologyContextFrontierRuntimeOptions",
    "run_topology_context_frontier_runtime",
]
