"""Scope and language boundary checks for alpha release outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierComplianceCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierBoundaryReport:
    checks: tuple[TopologyAlphaFrontierComplianceCheck, ...]
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


def evaluate_topology_alpha_frontier_boundary(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierBoundaryReport:
    serialized = str(evaluation.to_dict()).lower()
    checks = (TopologyAlphaFrontierComplianceCheck("scope-label", fixture.boundary == "public_aggregate_non_patient", "fixture boundary is aggregate and public", fixture.boundary), TopologyAlphaFrontierComplianceCheck("source-scope", all(item.public_aggregate for item in fixture.sources), "all source receipts are aggregate", len(fixture.sources)), TopologyAlphaFrontierComplianceCheck("payload-scope", all(row.payload.get("public_aggregate") is True for row in fixture.records), "all payloads declare aggregate scope", len(fixture.records)), TopologyAlphaFrontierComplianceCheck("no-subject-fields", "subject_id" not in serialized and "patient_id" not in serialized, "subject-level identifiers are absent", True), TopologyAlphaFrontierComplianceCheck("result-addresses", all(row.adapter.content_address.startswith("sha256:") for row in evaluation.rows), "result addresses are present", len(evaluation.rows)))
    return TopologyAlphaFrontierBoundaryReport(checks, all(item.passed for item in checks))


__all__ = ["TopologyAlphaFrontierBoundaryReport", "TopologyAlphaFrontierComplianceCheck", "evaluate_topology_alpha_frontier_boundary"]
