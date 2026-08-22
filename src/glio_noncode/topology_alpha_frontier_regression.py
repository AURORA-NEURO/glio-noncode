"""Baseline comparison for alpha fixture and release invariants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation, evaluate_topology_alpha_frontier_fixture
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture, default_topology_alpha_frontier_fixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierRegressionCheck:
    check_id: str
    expected: Any
    observed: Any
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierRegressionReport:
    baseline_address: str
    candidate_address: str
    checks: tuple[TopologyAlphaFrontierRegressionCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def failed(self) -> tuple[TopologyAlphaFrontierRegressionCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def compare_topology_alpha_frontier_regression(baseline: TopologyAlphaFrontierEvaluation, candidate: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierRegressionReport:
    checks = (
        TopologyAlphaFrontierRegressionCheck("row-count", len(baseline.rows), len(candidate.rows), len(baseline.rows) == len(candidate.rows), "record cardinality remains stable"),
        TopologyAlphaFrontierRegressionCheck("state-map", tuple((row.record_id, row.observed_state) for row in baseline.rows), tuple((row.record_id, row.observed_state) for row in candidate.rows), tuple((row.record_id, row.observed_state) for row in baseline.rows) == tuple((row.record_id, row.observed_state) for row in candidate.rows), "state transitions remain stable"),
        TopologyAlphaFrontierRegressionCheck("issue-map", tuple((row.record_id, row.observed_issue_codes) for row in baseline.rows), tuple((row.record_id, row.observed_issue_codes) for row in candidate.rows), tuple((row.record_id, row.observed_issue_codes) for row in baseline.rows) == tuple((row.record_id, row.observed_issue_codes) for row in candidate.rows), "issue visibility remains stable"),
        TopologyAlphaFrontierRegressionCheck("acceptance", True, candidate.accepted, candidate.accepted, "candidate remains accepted"),
    )
    return TopologyAlphaFrontierRegressionReport(baseline.content_address, candidate.content_address, checks, all(item.passed for item in checks))


def run_topology_alpha_frontier_regression(fixture: TopologyAlphaFrontierFixture | None = None) -> TopologyAlphaFrontierRegressionReport:
    value = fixture or default_topology_alpha_frontier_fixture()
    return compare_topology_alpha_frontier_regression(evaluate_topology_alpha_frontier_fixture(value), evaluate_topology_alpha_frontier_fixture(value))


__all__ = ["TopologyAlphaFrontierRegressionCheck", "TopologyAlphaFrontierRegressionReport", "compare_topology_alpha_frontier_regression", "run_topology_alpha_frontier_regression"]
