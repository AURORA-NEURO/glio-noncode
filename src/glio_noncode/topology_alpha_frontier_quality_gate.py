"""Quality floor for alpha fixture, schema, replay, and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierDataAudit, TopologyAlphaFrontierFixture
from .topology_alpha_frontier_reconciliation import TopologyAlphaFrontierReconciliation
from .topology_alpha_frontier_schema import TopologyAlphaFrontierSchemaReport


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierQualityCheck:
    check_id: str
    passed: bool
    threshold: str
    observed: Any
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierQualityReport:
    checks: tuple[TopologyAlphaFrontierQualityCheck, ...]
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


def build_topology_alpha_frontier_quality(fixture: TopologyAlphaFrontierFixture, data: TopologyAlphaFrontierDataAudit, schema: TopologyAlphaFrontierSchemaReport, evaluation: TopologyAlphaFrontierEvaluation, reconciliation: TopologyAlphaFrontierReconciliation) -> TopologyAlphaFrontierQualityReport:
    checks = (TopologyAlphaFrontierQualityCheck("data-audit", data.accepted, "accepted", data.accepted, "public fixture boundary and counts"), TopologyAlphaFrontierQualityCheck("schema", schema.accepted, "all checks pass", len(schema.failed()) == 0, "schema envelope checks"), TopologyAlphaFrontierQualityCheck("state-replay", evaluation.accepted, "16 of 16", evaluation.state_match_count, "state expectations"), TopologyAlphaFrontierQualityCheck("issue-replay", evaluation.accepted, "16 of 16", evaluation.issue_match_count, "issue floors"), TopologyAlphaFrontierQualityCheck("reconciliation", reconciliation.accepted, "closed", reconciliation.accepted, "state and measurement closure"), TopologyAlphaFrontierQualityCheck("positive-count", len(fixture.positive_records) == 4, "4", len(fixture.positive_records), "one positive per operation"), TopologyAlphaFrontierQualityCheck("control-count", len(fixture.control_records) == 12, "12", len(fixture.control_records), "three controls per operation"))
    score = sum(item.passed for item in checks) / len(checks)
    return TopologyAlphaFrontierQualityReport(checks, all(item.passed for item in checks), score)


__all__ = ["TopologyAlphaFrontierQualityCheck", "TopologyAlphaFrontierQualityReport", "build_topology_alpha_frontier_quality"]
