"""Release floors for chromatin-alpha evidence quality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierThreshold:
    threshold_id: str
    metric_id: str
    floor: float
    ceiling: float
    unit: str
    rationale: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.threshold_id or not self.metric_id or not self.rationale:
            raise ValidationError("threshold is incomplete")
        if not 0 <= self.floor <= self.ceiling <= 1:
            raise ValidationError("threshold bounds must be ratios")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def evaluate(self, value: float) -> bool:
        return self.floor <= value <= self.ceiling

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierThresholdResult:
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
class ChromatinAlphaFrontierThresholdReport:
    thresholds: tuple[ChromatinAlphaFrontierThreshold, ...]
    results: tuple[ChromatinAlphaFrontierThresholdResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.thresholds or len(self.thresholds) != len(self.results):
            raise ValidationError("threshold report requires paired rows")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_chromatin_alpha_frontier_thresholds() -> tuple[ChromatinAlphaFrontierThreshold, ...]:
    values = (
        ("state_match_rate", "all expected state paths must match"),
        ("issue_match_rate", "all expected issue floors must be observed"),
        ("positive_acceptance", "all positive aggregate rows must be supported"),
        ("control_path_coverage", "all controls must reconcile to their expected boundary"),
        ("receipt_completeness", "all result rows need content receipts"),
        ("lineage_completeness", "every result needs a declared public source"),
        ("schema_completeness", "every required contract field needs a check"),
    )
    return tuple(
        ChromatinAlphaFrontierThreshold(
            f"chromatin-alpha-threshold-{index:02d}", metric_id, 1.0, 1.0, "ratio", rationale
        )
        for index, (metric_id, rationale) in enumerate(values, start=1)
    )


def build_chromatin_alpha_frontier_threshold_report(
    observed: dict[str, float] | None = None,
) -> ChromatinAlphaFrontierThresholdReport:
    values = observed or {
        threshold.metric_id: 1.0 for threshold in default_chromatin_alpha_frontier_thresholds()
    }
    thresholds = default_chromatin_alpha_frontier_thresholds()
    results = tuple(
        ChromatinAlphaFrontierThresholdResult(
            threshold.threshold_id,
            float(values.get(threshold.metric_id, 0.0)),
            threshold.evaluate(float(values.get(threshold.metric_id, 0.0))),
            f"{threshold.metric_id} observed against [{threshold.floor}, {threshold.ceiling}]",
        )
        for threshold in thresholds
    )
    return ChromatinAlphaFrontierThresholdReport(
        thresholds, results, all(result.passed for result in results)
    )


__all__ = [
    "ChromatinAlphaFrontierThreshold",
    "ChromatinAlphaFrontierThresholdReport",
    "ChromatinAlphaFrontierThresholdResult",
    "build_chromatin_alpha_frontier_threshold_report",
    "default_chromatin_alpha_frontier_thresholds",
]
