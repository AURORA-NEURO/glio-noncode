"""Quality floors for fixture integrity, replay, and evidence accounting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierDataAudit, LinkGraphAlphaFrontierFixture
from .link_graph_alpha_frontier_reconciliation import LinkGraphAlphaFrontierReconciliation
from .link_graph_alpha_frontier_schema import LinkGraphAlphaFrontierSchemaReport
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierQualityCheck:
    check_id: str
    passed: bool
    observed: float
    minimum: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierQualityReport:
    checks: tuple[LinkGraphAlphaFrontierQualityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "failed_checks": self.failed_checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_quality(fixture: LinkGraphAlphaFrontierFixture, data: LinkGraphAlphaFrontierDataAudit, schema: LinkGraphAlphaFrontierSchemaReport, evaluation: LinkGraphAlphaFrontierEvaluation, reconciliation: LinkGraphAlphaFrontierReconciliation) -> LinkGraphAlphaFrontierQualityReport:
    total = len(fixture.records)
    checks = (
        LinkGraphAlphaFrontierQualityCheck("data_audit", data.accepted, float(data.record_count), 16.0, "closed fixture balance"),
        LinkGraphAlphaFrontierQualityCheck("schema_gate", schema.accepted, float(sum(item.passed for item in schema.checks)), float(len(schema.checks)), "schema checks pass"),
        LinkGraphAlphaFrontierQualityCheck("state_replay", evaluation.state_match_count == total, float(evaluation.state_match_count), float(total), "all records match state expectations"),
        LinkGraphAlphaFrontierQualityCheck("issue_replay", evaluation.issue_match_count == total, float(evaluation.issue_match_count), float(total), "all controls expose declared issues"),
        LinkGraphAlphaFrontierQualityCheck("reconciliation", reconciliation.accepted, float(len(reconciliation.items) - len(reconciliation.mismatches)), float(total), "expected and observed records reconcile"),
        LinkGraphAlphaFrontierQualityCheck("public_boundary", fixture.boundary == "public_aggregate_non_patient", 1.0 if fixture.boundary == "public_aggregate_non_patient" else 0.0, 1.0, "fixture remains aggregate"),
    )
    return LinkGraphAlphaFrontierQualityReport(checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierQualityCheck", "LinkGraphAlphaFrontierQualityReport", "build_link_graph_alpha_frontier_quality"]
