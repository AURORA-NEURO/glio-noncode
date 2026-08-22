"""Named thresholds and their intended link-path semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierThreshold:
    threshold_id: str
    value: float
    unit: str
    applies_to: str
    action_below: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierThresholdSet:
    thresholds: tuple[LinkGraphAlphaFrontierThreshold, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_id(self, threshold_id: str) -> LinkGraphAlphaFrontierThreshold:
        for item in self.thresholds:
            if item.threshold_id == threshold_id:
                return item
        raise KeyError(threshold_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"thresholds": [item.to_dict() for item in self.thresholds], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_alpha_frontier_thresholds() -> LinkGraphAlphaFrontierThresholdSet:
    thresholds = (
        LinkGraphAlphaFrontierThreshold("crispr-low-support", 0.2, "normalized support", "crispr_perturbation", "review", "weak perturbation paths remain visible"),
        LinkGraphAlphaFrontierThreshold("contact-weak-signal", 0.3, "normalized contact", "contact_3d", "review", "weak contact does not become a strong edge"),
        LinkGraphAlphaFrontierThreshold("tethering-minimum-score", 0.35, "tethering score", "promoter_tethering", "abstain", "minimum score follows the bounded baseline"),
        LinkGraphAlphaFrontierThreshold("graph-minimum-support", 0.0, "edge support", "multi_gene_graph", "retain", "graph bookkeeping preserves low support for review"),
    )
    return LinkGraphAlphaFrontierThresholdSet(thresholds, len(thresholds) == 4 and all(0 <= item.value <= 1 for item in thresholds))


__all__ = ["LinkGraphAlphaFrontierThreshold", "LinkGraphAlphaFrontierThresholdSet", "default_link_graph_alpha_frontier_thresholds"]
