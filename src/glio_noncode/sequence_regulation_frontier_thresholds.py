"""Named thresholds for release review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationThreshold:
    threshold_id: str
    value: float
    comparator: str
    detail: str

    def __post_init__(self) -> None:
        if not self.threshold_id or self.comparator not in {"eq", "gte", "lte"} or not self.detail:
            raise ValidationError("threshold is invalid")
        if not 0 <= self.value <= 1:
            raise ValidationError("threshold value must be bounded")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationThresholdReport:
    thresholds: tuple[SequenceRegulationThreshold, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.thresholds:
            raise ValidationError("threshold report requires thresholds")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_regulation_threshold_report() -> SequenceRegulationThresholdReport:
    thresholds = (
        SequenceRegulationThreshold(
            "state_match_rate", 1.0, "eq", "all expected states must match"
        ),
        SequenceRegulationThreshold(
            "issue_match_rate", 1.0, "eq", "all expected issue paths must match"
        ),
        SequenceRegulationThreshold(
            "positive_acceptance", 1.0, "gte", "all positive cases must pass"
        ),
        SequenceRegulationThreshold(
            "control_acceptance", 1.0, "gte", "all controls must pass their expected boundary path"
        ),
        SequenceRegulationThreshold(
            "receipt_coverage", 1.0, "eq", "all outputs must have receipts"
        ),
        SequenceRegulationThreshold(
            "context_coverage", 1.0, "eq", "all records must carry context"
        ),
    )
    return SequenceRegulationThresholdReport(
        thresholds, all(0 <= threshold.value <= 1 for threshold in thresholds)
    )


__all__ = [
    "SequenceRegulationThreshold",
    "SequenceRegulationThresholdReport",
    "build_sequence_regulation_threshold_report",
]
