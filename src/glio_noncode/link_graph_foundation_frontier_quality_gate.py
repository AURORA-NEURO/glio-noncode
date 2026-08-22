"""Quality floor for the C01-C04 baseline fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierDataAudit, LinkGraphFoundationFrontierFixture
from .link_graph_foundation_frontier_reconciliation import LinkGraphFoundationFrontierReconciliation
from .link_graph_foundation_frontier_schema import LinkGraphFoundationFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierQualityCheck:
    check_id: str
    passed: bool
    observed: float
    minimum: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierQualityReport:
    checks: tuple[LinkGraphFoundationFrontierQualityCheck, ...]
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


def build_link_graph_foundation_frontier_quality(fixture: LinkGraphFoundationFrontierFixture, data: LinkGraphFoundationFrontierDataAudit, schema: LinkGraphFoundationFrontierSchemaReport, evaluation: LinkGraphFoundationFrontierEvaluation, reconciliation: LinkGraphFoundationFrontierReconciliation) -> LinkGraphFoundationFrontierQualityReport:
    total = len(fixture.records)
    checks = (LinkGraphFoundationFrontierQualityCheck("data", data.accepted, data.record_count, 16, "balanced fixture"), LinkGraphFoundationFrontierQualityCheck("schema", schema.accepted, sum(item.passed for item in schema.checks), len(schema.checks), "schema checks"), LinkGraphFoundationFrontierQualityCheck("state_replay", evaluation.state_match_count == total, evaluation.state_match_count, total, "state replay"), LinkGraphFoundationFrontierQualityCheck("issue_replay", evaluation.issue_match_count == total, evaluation.issue_match_count, total, "control replay"), LinkGraphFoundationFrontierQualityCheck("reconciliation", reconciliation.accepted, total - len(reconciliation.mismatches), total, "expected and observed reconciliation"), LinkGraphFoundationFrontierQualityCheck("aggregate", fixture.boundary == "public_aggregate_non_patient", 1 if fixture.boundary == "public_aggregate_non_patient" else 0, 1, "aggregate boundary"))
    return LinkGraphFoundationFrontierQualityReport(checks, all(item.passed for item in checks))


__all__ = ["LinkGraphFoundationFrontierQualityCheck", "LinkGraphFoundationFrontierQualityReport", "build_link_graph_foundation_frontier_quality"]
