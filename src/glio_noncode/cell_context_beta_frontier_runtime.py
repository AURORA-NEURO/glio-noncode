"""Runtime wrapper with bounded record and context limits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_pipeline import (
    CellContextBetaFrontierPipelineReport,
    run_cell_context_beta_frontier_pipeline,
)
from .cell_context_beta_frontier_public_data import (
    CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
    CellContextBetaFrontierFixture,
)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierRuntimeOptions:
    run_id: str = "cell-context-beta-frontier-runtime"
    context_key: str = CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY
    max_records: int = 16
    require_aggregate: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "context_key": self.context_key,
            "max_records": self.max_records,
            "require_aggregate": self.require_aggregate,
        }


def run_cell_context_beta_frontier_runtime(
    options: CellContextBetaFrontierRuntimeOptions | None = None,
    *,
    fixture: CellContextBetaFrontierFixture,
) -> CellContextBetaFrontierPipelineReport:
    options = options or CellContextBetaFrontierRuntimeOptions()
    if fixture.context_key != options.context_key:
        raise ValueError("beta fixture context does not match runtime context")
    if len(fixture.records) > options.max_records:
        raise ValueError("beta fixture exceeds runtime record limit")
    if options.require_aggregate and fixture.evidence_boundary != "public_aggregate_non_patient":
        raise ValueError("beta runtime requires aggregate evidence")
    return run_cell_context_beta_frontier_pipeline(fixture, options.run_id)


__all__ = ["CellContextBetaFrontierRuntimeOptions", "run_cell_context_beta_frontier_runtime"]
