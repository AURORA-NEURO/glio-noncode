"""Release thresholds for methylation evidence quality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierThreshold:
    threshold_id: str
    metric_id: str
    floor: float
    ceiling: float
    unit: str
    rationale: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.threshold_id or not self.metric_id or not self.rationale:
            raise ValidationError("threshold identity is incomplete")
        if not 0 <= self.floor <= self.ceiling <= 1:
            raise ValidationError("threshold bounds must be ratios")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def evaluate(self, value: float) -> bool:
        return self.floor <= value <= self.ceiling

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierThresholdResult:
    threshold_id: str
    observed: float
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.threshold_id or not self.detail:
            raise ValidationError("threshold result is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierThresholdReport:
    thresholds: tuple[MethylationFrontierThreshold, ...]
    results: tuple[MethylationFrontierThresholdResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.thresholds or len(self.thresholds) != len(self.results):
            raise ValidationError("threshold report requires paired definitions and results")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_metric(self, metric_id: str) -> MethylationFrontierThreshold | None:
        return next((item for item in self.thresholds if item.metric_id == metric_id), None)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_methylation_frontier_thresholds() -> tuple[MethylationFrontierThreshold, ...]:
    values = (
        (
            "state_match_rate",
            "Expected state agreement",
            "every positive and control path is explicit",
        ),
        (
            "issue_match_rate",
            "Expected issue-path coverage",
            "malformed and bounded paths remain visible",
        ),
        (
            "positive_acceptance",
            "Positive aggregate acceptance",
            "all positive fixture rows must run",
        ),
        (
            "control_acceptance",
            "Control path acceptance",
            "all controls must follow their expected boundary",
        ),
        (
            "source_receipt_rate",
            "Source receipt completeness",
            "every declared source has version and checksum",
        ),
        (
            "content_address_rate",
            "Content receipt completeness",
            "every result can be replayed by address",
        ),
    )
    return tuple(
        MethylationFrontierThreshold(
            threshold_id=f"methylation-threshold-{index:02d}",
            metric_id=metric_id,
            floor=1.0,
            ceiling=1.0,
            unit="ratio",
            rationale=rationale,
        )
        for index, (metric_id, _title, rationale) in enumerate(values, start=1)
    )


def build_methylation_frontier_threshold_report(
    observed: dict[str, float] | None = None,
) -> MethylationFrontierThresholdReport:
    """Evaluate release floors while retaining every observed ratio."""

    values = observed or {
        threshold.metric_id: 1.0 for threshold in default_methylation_frontier_thresholds()
    }
    thresholds = default_methylation_frontier_thresholds()
    results = tuple(
        MethylationFrontierThresholdResult(
            threshold_id=threshold.threshold_id,
            observed=float(values.get(threshold.metric_id, 0.0)),
            passed=threshold.evaluate(float(values.get(threshold.metric_id, 0.0))),
            detail=(
                f"{threshold.metric_id} observed against [{threshold.floor}, {threshold.ceiling}]"
            ),
        )
        for threshold in thresholds
    )
    return MethylationFrontierThresholdReport(
        thresholds, results, all(result.passed for result in results)
    )


__all__ = [
    "MethylationFrontierThreshold",
    "MethylationFrontierThresholdReport",
    "MethylationFrontierThresholdResult",
    "build_methylation_frontier_threshold_report",
    "default_methylation_frontier_thresholds",
]
