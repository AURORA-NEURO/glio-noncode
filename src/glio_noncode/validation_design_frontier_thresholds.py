"""State and count threshold receipts for the planning surface."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignThresholdReport:
    thresholds: dict[str, Any]
    probes: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_validation_design_threshold_report() -> ValidationDesignThresholdReport:
    thresholds = {"source_count": 5, "record_count": 16, "positive_count": 4, "control_count": 12, "checks_per_record": 5, "total_checks": 80, "operation_count": 4, "construct_budget_minimum": 1}
    probes = tuple({"threshold_id": name, "required": value, "boundary": "inclusive"} for name, value in thresholds.items())
    body = {"thresholds": thresholds, "probes": probes, "accepted": len(probes) == len(thresholds) and all(item["required"] is not None for item in probes)}
    return ValidationDesignThresholdReport(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignThresholdReport", "build_validation_design_threshold_report"]
