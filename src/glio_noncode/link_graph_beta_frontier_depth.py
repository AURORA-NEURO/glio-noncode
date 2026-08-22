"""Depth audit for the four beta evidence operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierDepthCheck:
    check_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierDepthReport:
    fixture_id: str
    checks: tuple[LinkGraphBetaFrontierDepthCheck, ...]
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


def audit_link_graph_beta_frontier_depth(fixture: LinkGraphBetaFrontierFixture, evaluation: LinkGraphBetaFrontierEvaluation) -> LinkGraphBetaFrontierDepthReport:
    checks = (LinkGraphBetaFrontierDepthCheck("operation_balance", all(len(fixture.operation_records(operation)) == 4 for operation in LinkGraphBetaFrontierOperation), {operation.value: len(fixture.operation_records(operation)) for operation in LinkGraphBetaFrontierOperation}, {operation.value: 4 for operation in LinkGraphBetaFrontierOperation}, "four records per operation"), LinkGraphBetaFrontierDepthCheck("state_controls", {row.observed_state for row in evaluation.rows} >= {"partial", "abstained", "out_of_domain", "contradictory"}, sorted({row.observed_state for row in evaluation.rows}), ["partial", "abstained", "out_of_domain", "contradictory"], "positive and control states remain visible"), LinkGraphBetaFrontierDepthCheck("measurement_coverage", all(record.expected_measurements for record in fixture.records), sum(bool(record.expected_measurements) for record in fixture.records), len(fixture.records), "measurement expectations are present"), LinkGraphBetaFrontierDepthCheck("receipt_coverage", all(record.source_ids for record in fixture.records), sum(bool(record.source_ids) for record in fixture.records), len(fixture.records), "every record has a receipt"), LinkGraphBetaFrontierDepthCheck("replay_alignment", len(evaluation.rows) == len(fixture.records), len(evaluation.rows), len(fixture.records), "replay rows align"))
    return LinkGraphBetaFrontierDepthReport(fixture.fixture_id, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphBetaFrontierDepthCheck", "LinkGraphBetaFrontierDepthReport", "audit_link_graph_beta_frontier_depth"]
