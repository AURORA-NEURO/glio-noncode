"""Quality gate combining data, schema, replay, and reconciliation checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierDataAudit, LinkGraphBetaFrontierFixture
from .link_graph_beta_frontier_reconciliation import LinkGraphBetaFrontierReconciliation
from .link_graph_beta_frontier_schema import LinkGraphBetaFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierQualityCheck:
    check_id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierQualityReport:
    fixture_id: str
    checks: tuple[LinkGraphBetaFrontierQualityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "checks": [item.to_dict() for item in self.checks], "failed_checks": self.failed_checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_quality(fixture: LinkGraphBetaFrontierFixture, data: LinkGraphBetaFrontierDataAudit, schema: LinkGraphBetaFrontierSchemaReport, evaluation: LinkGraphBetaFrontierEvaluation, reconciliation: LinkGraphBetaFrontierReconciliation) -> LinkGraphBetaFrontierQualityReport:
    checks = (LinkGraphBetaFrontierQualityCheck("data", data.accepted, "fixture audit"), LinkGraphBetaFrontierQualityCheck("schema", schema.accepted, "schema validation"), LinkGraphBetaFrontierQualityCheck("evaluation", evaluation.accepted, "deterministic replay"), LinkGraphBetaFrontierQualityCheck("reconciliation", reconciliation.accepted, "expected versus observed"), LinkGraphBetaFrontierQualityCheck("source_count", len(fixture.sources) == 4, "four public aggregate receipts"), LinkGraphBetaFrontierQualityCheck("operation_count", len(fixture.records) == 16, "four records per operation"))
    return LinkGraphBetaFrontierQualityReport(fixture.fixture_id, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphBetaFrontierQualityCheck", "LinkGraphBetaFrontierQualityReport", "build_link_graph_beta_frontier_quality"]
