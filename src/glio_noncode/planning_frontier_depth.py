"""Depth thresholds for the four operation planning surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture
from .planning_frontier_metrics import PlanningMetrics
from .planning_frontier_quality_gate import PlanningQualityGate
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningDepthReport:
    plane_ids: tuple[str, ...]
    values: dict[str, Any]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_depth_report(fixture: PlanningFixture, evaluation: PlanningEvaluation, metrics: PlanningMetrics, quality: PlanningQualityGate) -> PlanningDepthReport:
    operation_counts = metrics.operation_counts
    values = {
        "source_count": len(fixture.sources),
        "record_count": len(fixture.records),
        "operation_count": len(operation_counts),
        "checks": len(evaluation.checks),
        "positive_records": len(fixture.positive_records),
        "control_records": len(fixture.control_records),
        "quality_checks": len(quality.checks),
        "operation_closure": sorted(operation_counts.values()) == [4, 4, 4, 4],
        "five_checks_per_record": len(evaluation.checks) == len(fixture.records) * 5,
    }
    planes = ("source", "record", "operation", "scenario", "check", "role", "quality", "closure", "boundary", "replay", "review", "release")
    accepted = bool(values["source_count"] == 5 and values["record_count"] == 16 and values["operation_count"] == 4 and values["checks"] == 80 and values["positive_records"] == 4 and values["control_records"] == 12 and values["quality_checks"] >= 7 and values["operation_closure"] and values["five_checks_per_record"] and quality.accepted)
    body = {"plane_ids": planes, "values": values, "accepted": accepted}
    return PlanningDepthReport(planes, values, accepted, content_hash(body, prefix="planning-depth"))


__all__ = ["PlanningDepthReport", "build_planning_depth_report"]
