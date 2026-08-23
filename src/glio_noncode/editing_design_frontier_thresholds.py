"""Count and boundary thresholds for the C05-C08 design fixture."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignThresholdReport:
    thresholds: dict[str, Any]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_editing_design_threshold_report() -> EditingDesignThresholdReport:
    thresholds = {"source_count": 5, "record_count": 16, "positive_count": 4, "control_count": 12, "operation_count": 4, "checks_per_record": 5, "total_checks": 80, "min_guide_length": 1, "min_construct_budget": 1}
    body = {"thresholds": thresholds, "accepted": len(thresholds) == 9 and all(value > 0 for value in thresholds.values())}
    return EditingDesignThresholdReport(**body, content_address=content_hash(body))

__all__ = ["EditingDesignThresholdReport", "build_editing_design_threshold_report"]
