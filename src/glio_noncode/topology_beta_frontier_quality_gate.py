"""Quality floor combining fixture, schema, replay, and reconciliation checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation
from .topology_beta_frontier_public_data import TopologyBetaFrontierDataAudit, TopologyBetaFrontierFixture
from .topology_beta_frontier_reconciliation import TopologyBetaFrontierReconciliation
from .topology_beta_frontier_schema import TopologyBetaFrontierSchemaReport


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierQualityCheck:
    check_id: str
    passed: bool
    threshold: str
    observed: Any
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierQualityReport:
    checks: tuple[TopologyBetaFrontierQualityCheck, ...]
    accepted: bool
    quality_score: float
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "accepted": self.accepted, "quality_score": self.quality_score}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_quality(fixture: TopologyBetaFrontierFixture, data: TopologyBetaFrontierDataAudit, schema: TopologyBetaFrontierSchemaReport, evaluation: TopologyBetaFrontierEvaluation, reconciliation: TopologyBetaFrontierReconciliation) -> TopologyBetaFrontierQualityReport:
    checks = (
        TopologyBetaFrontierQualityCheck("data-audit", data.accepted, "accepted", data.accepted, "public fixture boundary and counts"),
        TopologyBetaFrontierQualityCheck("schema", schema.accepted, "all checks pass", len(schema.failed()) == 0, "schema and envelope checks"),
        TopologyBetaFrontierQualityCheck("state-replay", evaluation.accepted, "16 of 16", evaluation.state_match_count, "state expectations"),
        TopologyBetaFrontierQualityCheck("issue-replay", evaluation.accepted, "16 of 16", evaluation.issue_match_count, "issue floors"),
        TopologyBetaFrontierQualityCheck("reconciliation", reconciliation.accepted, "closed", reconciliation.accepted, "measurement and state closure"),
        TopologyBetaFrontierQualityCheck("positive-count", len(fixture.positive_records) == 4, "4", len(fixture.positive_records), "one positive per operation"),
        TopologyBetaFrontierQualityCheck("control-count", len(fixture.control_records) == 12, "12", len(fixture.control_records), "three controls per operation"),
    )
    score = sum(item.passed for item in checks) / len(checks)
    return TopologyBetaFrontierQualityReport(checks, all(item.passed for item in checks), score)


__all__ = ["TopologyBetaFrontierQualityCheck", "TopologyBetaFrontierQualityReport", "build_topology_beta_frontier_quality"]
