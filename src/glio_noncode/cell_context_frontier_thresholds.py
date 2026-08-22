"""Named release thresholds for Domain 08 context evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierThreshold:
    threshold_id: str
    value: float
    comparator: str
    unit: str
    rationale: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.threshold_id or not self.unit or not self.rationale:
            raise ValidationError("cell threshold is incomplete")
        if self.comparator not in {">=", "<=", "=="}:
            raise ValidationError("cell threshold comparator is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierThresholdReport:
    thresholds: tuple[CellContextFrontierThreshold, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.thresholds) != 10:
            raise ValidationError("cell threshold report requires ten rows")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def get(self, threshold_id: str) -> CellContextFrontierThreshold:
        for item in self.thresholds:
            if item.threshold_id == threshold_id:
                return item
        raise KeyError(threshold_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_frontier_threshold_report() -> CellContextFrontierThresholdReport:
    values = (
        ("positive_support_rate", 1.0, ">=", "ratio", "positive paths must support"),
        ("state_match_rate", 1.0, "==", "ratio", "states must reconcile"),
        ("issue_floor_rate", 1.0, "==", "ratio", "parser issue floors must reconcile"),
        ("operation_count", 4.0, "==", "operations", "four context operations must run"),
        ("record_count", 16.0, "==", "rows", "sixteen fixture rows are required"),
        ("control_count", 12.0, "==", "rows", "controls preserve refusal paths"),
        ("source_count", 5.0, "==", "sources", "five source receipts are linked"),
        ("runtime_stage_count", 10.0, "==", "stages", "ten runtime stages remain visible"),
        ("review_minimum", 1.0, ">=", "queue_items", "uncertain rows cannot disappear"),
        ("refusal_minimum", 1.0, ">=", "queue_items", "foreign contexts must be refused"),
    )
    return CellContextFrontierThresholdReport(
        tuple(CellContextFrontierThreshold(*item) for item in values), True
    )


__all__ = [
    "CellContextFrontierThreshold",
    "CellContextFrontierThresholdReport",
    "build_cell_context_frontier_threshold_report",
]
