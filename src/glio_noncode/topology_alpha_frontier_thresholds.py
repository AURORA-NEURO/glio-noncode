"""Pinned thresholds for alpha orientation, channel, and state checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierThreshold:
    threshold_id: str
    value: float
    unit: str
    purpose: str
    rationale: str
    calibration_state: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierThresholdReport:
    thresholds: tuple[TopologyAlphaFrontierThreshold, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def get(self, threshold_id: str) -> TopologyAlphaFrontierThreshold:
        for item in self.thresholds:
            if item.threshold_id == threshold_id:
                return item
        raise KeyError(threshold_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"thresholds": [item.to_dict() for item in self.thresholds], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_threshold_report() -> TopologyAlphaFrontierThresholdReport:
    values = (TopologyAlphaFrontierThreshold("motif_minimum_score", 0.5, "score", "retain boundary motifs", "low-scoring motifs are omitted from orientation labels", "fixture_bound"), TopologyAlphaFrontierThreshold("ctcf_disruption_threshold", 0.2, "delta", "label channel disruption", "declared deltas remain visible", "fixture_bound"), TopologyAlphaFrontierThreshold("idh_dysfunction_threshold", 0.2, "index", "label insulator loss candidate", "state comparison retains methylation separately", "fixture_bound"), TopologyAlphaFrontierThreshold("minimum_quality_score", 1.0, "ratio", "release quality floor", "all quality checks must pass", "release_bound"))
    return TopologyAlphaFrontierThresholdReport(values, all(item.value >= 0 for item in values))


__all__ = ["TopologyAlphaFrontierThreshold", "TopologyAlphaFrontierThresholdReport", "build_topology_alpha_frontier_threshold_report"]
