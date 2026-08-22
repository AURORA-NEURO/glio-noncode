"""Named thresholds used by the beta fixture quality surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierThreshold:
    threshold_id: str
    value: float
    comparator: str
    unit: str
    rationale: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.threshold_id or not self.comparator or not self.unit or not self.rationale:
            raise ValidationError("beta threshold is incomplete")
        if self.comparator not in {"eq", "ge", "le"}:
            raise ValidationError("beta threshold comparator is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierThresholdReport:
    thresholds: tuple[CellContextBetaFrontierThreshold, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.thresholds:
            raise ValidationError("beta threshold report is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def get(self, threshold_id: str) -> CellContextBetaFrontierThreshold:
        return next(item for item in self.thresholds if item.threshold_id == threshold_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_beta_frontier_threshold_report() -> CellContextBetaFrontierThresholdReport:
    thresholds = (
        CellContextBetaFrontierThreshold("records", 16, "eq", "records", "closed fixture size"),
        CellContextBetaFrontierThreshold(
            "positive_records", 4, "eq", "records", "one positive path per prior family"
        ),
        CellContextBetaFrontierThreshold(
            "control_records", 12, "eq", "records", "three controls per prior family"
        ),
        CellContextBetaFrontierThreshold(
            "state_match_rate", 1.0, "ge", "ratio", "release requires exact state replay"
        ),
        CellContextBetaFrontierThreshold(
            "issue_floor_rate", 1.0, "ge", "ratio", "release requires issue-floor replay"
        ),
        CellContextBetaFrontierThreshold(
            "domain_refusal_count", 4, "eq", "records", "each family needs an explicit refusal"
        ),
        CellContextBetaFrontierThreshold(
            "ambiguity_control_count", 4, "eq", "records", "each family needs an ambiguity control"
        ),
    )
    return CellContextBetaFrontierThresholdReport(thresholds, len(thresholds) == 7)


__all__ = [
    "CellContextBetaFrontierThreshold",
    "CellContextBetaFrontierThresholdReport",
    "build_cell_context_beta_frontier_threshold_report",
]
