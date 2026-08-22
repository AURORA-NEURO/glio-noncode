"""Named thresholds for context-alpha fixture quality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierThreshold:
    threshold_id: str
    value: float
    comparator: str
    unit: str
    rationale: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierThresholdReport:
    thresholds: tuple[CellContextAlphaFrontierThreshold, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def get(self, threshold_id: str) -> CellContextAlphaFrontierThreshold:
        return next(item for item in self.thresholds if item.threshold_id == threshold_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_alpha_frontier_threshold_report() -> CellContextAlphaFrontierThresholdReport:
    thresholds = (
        CellContextAlphaFrontierThreshold("records", 16, "eq", "records", "closed fixture"),
        CellContextAlphaFrontierThreshold(
            "positive_records", 4, "eq", "records", "one positive per operation"
        ),
        CellContextAlphaFrontierThreshold(
            "control_records", 12, "eq", "records", "three controls per operation"
        ),
        CellContextAlphaFrontierThreshold(
            "state_match_rate", 1.0, "ge", "ratio", "exact replay required"
        ),
        CellContextAlphaFrontierThreshold(
            "issue_floor_rate", 1.0, "ge", "ratio", "issue floor replay required"
        ),
        CellContextAlphaFrontierThreshold(
            "domain_refusal_count", 4, "eq", "records", "foreign context refusal per operation"
        ),
        CellContextAlphaFrontierThreshold(
            "delta_control_count",
            3,
            "ge",
            "records",
            "induced, stable, and reduced-like surfaces remain descriptive",
        ),
    )
    return CellContextAlphaFrontierThresholdReport(thresholds, True)


__all__ = [
    "CellContextAlphaFrontierThreshold",
    "CellContextAlphaFrontierThresholdReport",
    "build_cell_context_alpha_frontier_threshold_report",
]
