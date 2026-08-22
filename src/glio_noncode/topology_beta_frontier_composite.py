"""Composite evidence joins that keep operation outputs separate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierCompositeLink:
    link_id: str
    enhancer_id: str
    promoter_id: str
    context_key: str
    operation_ids: tuple[str, ...]
    operation_states: dict[str, str]
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    component_count: int
    completeness: float
    link_state: str
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierCompositeReport:
    links: tuple[TopologyBetaFrontierCompositeLink, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_state(self, state: str) -> tuple[TopologyBetaFrontierCompositeLink, ...]:
        return tuple(item for item in self.links if item.link_state == state)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"links": [item.to_dict() for item in self.links], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _measurements(row: Any) -> tuple[str, ...]:
    value = row.adapter.measurements
    identifiers = []
    for key in ("promoters", "targets", "source_ids", "model_id"):
        if key in value:
            identifiers.append(f"{key}:{value[key]}")
    return tuple(identifiers)


def build_topology_beta_frontier_composite(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierCompositeReport:
    links = []
    for index, group in enumerate((tuple(evaluation.by_operation(operation)) for operation in sorted({item.operation for item in evaluation.rows})), start=1):
        positive = next(item for item in group if item.role == "positive")
        operation_states = {item.operation: item.observed_state for item in group}
        source_ids = tuple(sorted({source for item in group for source in item.adapter.source_ids}))
        evidence_ids = tuple(sorted({evidence for item in group for evidence in item.adapter.evidence_ids}))
        completeness = sum(bool(item.adapter.measurements) for item in group) / len(group)
        link_state = "supported" if positive.observed_state == "supported" else positive.observed_state
        links.append(TopologyBetaFrontierCompositeLink(f"composite-{index:02d}", "enh-1", "GENE1", "GRCh38|glioma|adult|stem_like|core|unknown", tuple(item.record_id for item in group), operation_states, source_ids, evidence_ids, len(_measurements(positive)) + len(evidence_ids), completeness, link_state, "Operation outputs remain separate; this view is an aggregate review join, not a new scientific claim."))
    values = tuple(links)
    return TopologyBetaFrontierCompositeReport(values, len(values) == 4 and all(item.completeness == 1.0 for item in values))


def summarize_topology_beta_frontier_composite(report: TopologyBetaFrontierCompositeReport) -> dict[str, Any]:
    return {"link_count": len(report.links), "accepted": report.accepted, "states": {state: len(report.for_state(state)) for state in sorted({item.link_state for item in report.links})}, "component_counts": [item.component_count for item in report.links]}


__all__ = ["TopologyBetaFrontierCompositeLink", "TopologyBetaFrontierCompositeReport", "build_topology_beta_frontier_composite", "summarize_topology_beta_frontier_composite"]
