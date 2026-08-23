"""Human-readable and structured release summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture
from .planning_frontier_metrics import PlanningMetrics, measure_planning
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningReport:
    report_id: str
    fixture_id: str
    title: str
    boundary: str
    metrics: PlanningMetrics
    sections: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def markdown(self) -> str:
        lines = [f"# {self.title}", "", f"Fixture: `{self.fixture_id}`", f"Boundary: `{self.boundary}`", "", "This report is a bounded public aggregate planning artifact.", "", "## Operation coverage", ""]
        for key, value in sorted(self.metrics.operation_counts.items()):
            lines.append(f"- `{key}`: {value} scenarios")
        lines.extend(("", "## Disposition", "", f"Accepted: `{self.accepted}`", f"Content address: `{self.content_address}`", ""))
        return "\n".join(lines)


def build_planning_report(*, fixture: PlanningFixture, evaluation: PlanningEvaluation, report_id: str = "planning-release-report") -> PlanningReport:
    metrics = measure_planning(evaluation)
    sections = (
        {"section_id": "scope", "detail": "four D13 planning capabilities under public aggregate evidence"},
        {"section_id": "review", "detail": "blocked, review, rejected, and abstained outcomes remain visible"},
        {"section_id": "boundary", "detail": "no efficacy, safety, clinical, or institutional conclusion is emitted"},
    )
    body = {"report_id": report_id, "fixture_id": fixture.fixture_id, "title": "D13 C09-C12 Planning Frontier", "boundary": fixture.evidence_boundary, "metrics": metrics, "sections": sections, "accepted": evaluation.accepted}
    return PlanningReport(**body, content_address=content_hash(body, prefix="planning-report"))


__all__ = ["PlanningReport", "build_planning_report"]
