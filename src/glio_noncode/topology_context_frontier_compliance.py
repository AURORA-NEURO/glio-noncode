"""Boundary checks for aggregate topology evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation
from .topology_context_frontier_public_data import (
    TOPOLOGY_CONTEXT_FRONTIER_BOUNDARY,
    TopologyContextFrontierFixture,
)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierBoundaryCheck:
    check_id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierBoundaryReport:
    checks: tuple[TopologyContextFrontierBoundaryCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_topology_context_frontier_boundary(
    fixture: TopologyContextFrontierFixture,
    evaluation: TopologyContextFrontierEvaluation | None = None,
) -> TopologyContextFrontierBoundaryReport:
    checks = (
        TopologyContextFrontierBoundaryCheck(
            "aggregate-boundary",
            fixture.boundary == TOPOLOGY_CONTEXT_FRONTIER_BOUNDARY,
            "aggregate boundary is declared",
        ),
        TopologyContextFrontierBoundaryCheck(
            "no-subject-keys",
            all("subject_id" not in str(item.payload) for item in fixture.records),
            "subject keys are absent",
        ),
        TopologyContextFrontierBoundaryCheck(
            "no-clinical-labels",
            all(
                not any(
                    term in str(item.payload).lower()
                    for term in ("diagnosis", "prognosis", "treatment selection")
                )
                for item in fixture.records
            ),
            "clinical conclusions are absent",
        ),
        TopologyContextFrontierBoundaryCheck(
            "negative-control-closure", len(fixture.control_records) == 12, "controls are present"
        ),
        TopologyContextFrontierBoundaryCheck(
            "evaluation-closure",
            evaluation is None or evaluation.accepted,
            "evaluation is accepted when supplied",
        ),
    )
    return TopologyContextFrontierBoundaryReport(checks, all(item.passed for item in checks))


__all__ = [
    "TopologyContextFrontierBoundaryCheck",
    "TopologyContextFrontierBoundaryReport",
    "evaluate_topology_context_frontier_boundary",
]
