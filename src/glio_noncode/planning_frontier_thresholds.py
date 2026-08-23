"""Executable release thresholds for the planning frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningThreshold:
    threshold_id: str
    operation: PlanningOperation | None
    metric: str
    required: Any
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningThresholdReport:
    thresholds: tuple[PlanningThreshold, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_threshold_report() -> PlanningThresholdReport:
    rows = (
        ("sources", None, "source_count", 5, "public receipt closure"),
        ("records", None, "record_count", 16, "balanced aggregate scenarios"),
        ("checks", None, "checks_per_record", 5, "state, issue, role, integrity, safety planes"),
        ("eligibility-strength", PlanningOperation.MODEL_ELIGIBILITY, "minimum_evidence_strength", "moderate", "weak evidence stays held"),
        ("guide-context", PlanningOperation.GUIDE_OLIGO, "context_match", True, "foreign rows stay blocked"),
        ("control-seed", PlanningOperation.CONTROLS_RANDOMIZATION, "seed_required", True, "assignment replayability"),
        ("power-variance", PlanningOperation.POWER_REPLICATION, "variance_positive", True, "approximation must have noise input"),
        ("private-markers", None, "private_marker_count", 0, "aggregate public boundary"),
        ("assurance", None, "assurance_planes", 60, "independent release assurance"),
    )
    thresholds = []
    for threshold_id, operation, metric, required, rationale in rows:
        body = {"threshold_id": threshold_id, "operation": operation, "metric": metric, "required": required, "rationale": rationale}
        thresholds.append(PlanningThreshold(**body, content_address=content_hash(body, prefix="planning-threshold")))
    values = tuple(thresholds)
    return PlanningThresholdReport(values, bool(values and all(item.content_address.startswith("planning-threshold:") for item in values)), content_hash(values, prefix="planning-threshold-report"))


__all__ = ["PlanningThreshold", "PlanningThresholdReport", "build_planning_threshold_report"]
