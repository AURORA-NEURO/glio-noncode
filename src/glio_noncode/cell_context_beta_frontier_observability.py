"""Compact trace events for replaying the beta execution path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierTraceEvent:
    event_id: str
    stage: str
    record_id: str
    state: str
    issue_count: int
    occurred_at: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierObservabilityReport:
    run_id: str
    events: tuple[CellContextBetaFrontierTraceEvent, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.run_id or not self.events:
            raise ValueError("beta observability report requires run and events")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_beta_frontier_trace(
    evaluation: CellContextBetaFrontierEvaluation, run_id: str = "cell-context-beta-frontier"
) -> CellContextBetaFrontierObservabilityReport:
    stamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    events = tuple(
        CellContextBetaFrontierTraceEvent(
            f"{run_id}:{index:03d}",
            "execute",
            row.record_id,
            row.observed_state,
            len(row.observed_issue_codes),
            stamp,
        )
        for index, row in enumerate(evaluation.records, 1)
    )
    return CellContextBetaFrontierObservabilityReport(run_id, events, evaluation.accepted)


__all__ = [
    "CellContextBetaFrontierObservabilityReport",
    "CellContextBetaFrontierTraceEvent",
    "build_cell_context_beta_frontier_trace",
]
