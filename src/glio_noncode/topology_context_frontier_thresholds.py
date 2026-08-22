"""Pinned thresholds for topology context quality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierThreshold:
    threshold_id: str
    value: float
    unit: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierThresholdReport:
    thresholds: tuple[TopologyContextFrontierThreshold, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "thresholds": [item.to_dict() for item in self.thresholds],
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_threshold_report() -> TopologyContextFrontierThresholdReport:
    thresholds = (
        TopologyContextFrontierThreshold(
            "state-match-floor", 1.0, "fraction", "every fixture expectation must replay"
        ),
        TopologyContextFrontierThreshold(
            "issue-match-floor", 0.75, "fraction", "control issue floors must remain visible"
        ),
        TopologyContextFrontierThreshold(
            "boundary-tolerance", 50.0, "base-pairs", "nearby boundary calls are clustered"
        ),
        TopologyContextFrontierThreshold(
            "minimum-source-count", 4.0, "receipts", "four public receipts close the tranche"
        ),
        TopologyContextFrontierThreshold(
            "maximum-records", 16.0, "records", "fixture stays aggregate and bounded"
        ),
    )
    return TopologyContextFrontierThresholdReport(thresholds, True)


__all__ = [
    "TopologyContextFrontierThreshold",
    "TopologyContextFrontierThresholdReport",
    "build_topology_context_frontier_threshold_report",
]
