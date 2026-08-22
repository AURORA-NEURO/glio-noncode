"""Named thresholds and their release rationale."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierThreshold:
    threshold_id: str
    value: float
    comparator: str
    unit: str
    rationale: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.threshold_id or not self.unit or not self.rationale:
            raise ValidationError("threshold is incomplete")
        if self.comparator not in {">=", "<=", "=="}:
            raise ValidationError("threshold comparator is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierThresholdReport:
    thresholds: tuple[ChromatinContextFrontierThreshold, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.thresholds) != 10:
            raise ValidationError("threshold report requires ten thresholds")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def get(self, threshold_id: str) -> ChromatinContextFrontierThreshold:
        for item in self.thresholds:
            if item.threshold_id == threshold_id:
                return item
        raise KeyError(threshold_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_context_frontier_threshold_report() -> ChromatinContextFrontierThresholdReport:
    items = (
        ChromatinContextFrontierThreshold(
            "positive_support_rate", 1.0, ">=", "ratio", "every positive fixture path must support"
        ),
        ChromatinContextFrontierThreshold(
            "state_match_rate",
            1.0,
            "==",
            "ratio",
            "fixture state expectations must be deterministic",
        ),
        ChromatinContextFrontierThreshold(
            "issue_floor_rate", 1.0, "==", "ratio", "expected parser issue floors must be visible"
        ),
        ChromatinContextFrontierThreshold(
            "source_receipt_rate", 1.0, "==", "ratio", "every source must have a content receipt"
        ),
        ChromatinContextFrontierThreshold(
            "control_count", 12.0, "==", "rows", "controls retain refusal and uncertainty coverage"
        ),
        ChromatinContextFrontierThreshold(
            "operation_count", 4.0, "==", "operations", "all four Domain 07 operations must execute"
        ),
        ChromatinContextFrontierThreshold(
            "runtime_stage_count", 10.0, "==", "stages", "runtime contract has ten visible stages"
        ),
        ChromatinContextFrontierThreshold(
            "source_count",
            5.0,
            "==",
            "sources",
            "five independent public source receipts are linked",
        ),
        ChromatinContextFrontierThreshold(
            "review_minimum", 1.0, ">=", "queue_items", "uncertain paths cannot disappear"
        ),
        ChromatinContextFrontierThreshold(
            "refusal_minimum",
            1.0,
            ">=",
            "queue_items",
            "foreign contexts must produce refusal coverage",
        ),
    )
    return ChromatinContextFrontierThresholdReport(items, True)


__all__ = [
    "ChromatinContextFrontierThreshold",
    "ChromatinContextFrontierThresholdReport",
    "build_chromatin_context_frontier_threshold_report",
]
