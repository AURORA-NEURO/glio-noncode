"""Runtime boundary for the aggregate context-alpha pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_pipeline import (
    CellContextAlphaFrontierPipelineReport,
    run_cell_context_alpha_frontier_pipeline,
)
from .cell_context_alpha_frontier_public_data import (
    CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY,
    CellContextAlphaFrontierFixture,
)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierRuntimeOptions:
    run_id: str = "cell-context-alpha-frontier-runtime"
    context_key: str = CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY
    max_records: int = 16
    require_aggregate: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "context_key": self.context_key,
            "max_records": self.max_records,
            "require_aggregate": self.require_aggregate,
        }


def run_cell_context_alpha_frontier_runtime(
    options: CellContextAlphaFrontierRuntimeOptions | None = None,
    *,
    fixture: CellContextAlphaFrontierFixture,
) -> CellContextAlphaFrontierPipelineReport:
    options = options or CellContextAlphaFrontierRuntimeOptions()
    if fixture.context_key != options.context_key or len(fixture.records) > options.max_records:
        raise ValueError("alpha fixture does not satisfy runtime bounds")
    if options.require_aggregate and fixture.evidence_boundary != "public_aggregate_non_patient":
        raise ValueError("alpha runtime requires aggregate evidence")
    return run_cell_context_alpha_frontier_pipeline(fixture, options.run_id)


__all__ = ["CellContextAlphaFrontierRuntimeOptions", "run_cell_context_alpha_frontier_runtime"]
