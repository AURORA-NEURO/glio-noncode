"""Pinned thresholds used by the public topology-beta fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierThreshold:
    threshold_id: str
    value: float
    unit: str
    purpose: str
    rationale: str
    calibration_state: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierThresholdReport:
    thresholds: tuple[TopologyBetaFrontierThreshold, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def get(self, threshold_id: str) -> TopologyBetaFrontierThreshold:
        for item in self.thresholds:
            if item.threshold_id == threshold_id:
                return item
        raise KeyError(threshold_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"thresholds": [item.to_dict() for item in self.thresholds], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_threshold_report() -> TopologyBetaFrontierThresholdReport:
    thresholds = (
        TopologyBetaFrontierThreshold("loop_signal_disagreement", 3.0, "signal units", "flag loop and stripe replicate disagreement", "fixture control separates stable and divergent aggregate signals", "fixture_bound"),
        TopologyBetaFrontierThreshold("promoter_signal_disagreement", 3.0, "signal units", "flag promoter capture disagreement", "fixture control separates stable and divergent aggregate signals", "fixture_bound"),
        TopologyBetaFrontierThreshold("contact_signal_scale", 10.0, "signal units", "bound enhancer promoter contact score", "normalization scale is declared with each result", "not_calibrated"),
        TopologyBetaFrontierThreshold("activity_signal_scale", 1.0, "signal units", "bound enhancer activity component", "activity input is retained as a measured component", "not_calibrated"),
        TopologyBetaFrontierThreshold("activity_ambiguity_tolerance", 0.3, "signal units", "flag activity replicate spread", "spread is visible and blocks unqualified support", "fixture_bound"),
        TopologyBetaFrontierThreshold("minimum_quality_score", 1.0, "ratio", "release quality floor", "all declared quality checks must pass", "release_bound"),
    )
    return TopologyBetaFrontierThresholdReport(thresholds, all(item.value >= 0 for item in thresholds))


__all__ = ["TopologyBetaFrontierThreshold", "TopologyBetaFrontierThresholdReport", "build_topology_beta_frontier_threshold_report"]
