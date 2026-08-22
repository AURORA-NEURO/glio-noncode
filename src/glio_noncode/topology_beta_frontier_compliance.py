"""Boundary checks for public aggregate scope and safe result language."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierComplianceCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierBoundaryReport:
    checks: tuple[TopologyBetaFrontierComplianceCheck, ...]
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


def evaluate_topology_beta_frontier_boundary(fixture: TopologyBetaFrontierFixture, evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierBoundaryReport:
    serialized = str(evaluation.to_dict()).lower()
    checks = (
        TopologyBetaFrontierComplianceCheck("scope-label", fixture.boundary == "public_aggregate_non_patient", "fixture boundary is aggregate and public", fixture.boundary),
        TopologyBetaFrontierComplianceCheck("source-scope", all(item.public_aggregate for item in fixture.sources), "all source receipts are aggregate", len(fixture.sources)),
        TopologyBetaFrontierComplianceCheck("payload-scope", all(row.payload.get("public_aggregate") is True for row in fixture.records), "all payloads declare aggregate scope", len(fixture.records)),
        TopologyBetaFrontierComplianceCheck("no-subject-fields", "subject_id" not in serialized and "patient_id" not in serialized, "subject-level identifiers are absent", True),
        TopologyBetaFrontierComplianceCheck("context-gate", all(row.adapter.state != "supported" or row.observed_state == "supported" for row in evaluation.rows), "supported states remain replay matched", len(evaluation.rows)),
        TopologyBetaFrontierComplianceCheck("limitation-receipts", all(len(row.adapter.content_address) > 0 for row in evaluation.rows), "every result is addressable for review", len(evaluation.rows)),
    )
    return TopologyBetaFrontierBoundaryReport(checks, all(item.passed for item in checks))


__all__ = ["TopologyBetaFrontierBoundaryReport", "TopologyBetaFrontierComplianceCheck", "evaluate_topology_beta_frontier_boundary"]
