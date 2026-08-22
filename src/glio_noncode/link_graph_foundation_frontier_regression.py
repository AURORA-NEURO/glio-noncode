"""Regression sentinels for public aggregate link behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierOperation, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierRegressionSentinel:
    sentinel_id: str
    operation: str
    record_id: str
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierRegressionResult:
    sentinel_id: str
    record_id: str
    state_match: bool
    issue_match: bool
    observed_state: str
    observed_issue_codes: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return self.state_match and self.issue_match

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierRegressionReport:
    fixture_id: str
    sentinels: tuple[LinkGraphFoundationFrontierRegressionSentinel, ...]
    results: tuple[LinkGraphFoundationFrontierRegressionResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(item.sentinel_id for item in self.results if not item.accepted)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "sentinels": [item.to_dict() for item in self.sentinels], "results": [item.to_dict() for item in self.results], "failures": self.failures, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_foundation_frontier_sentinels(fixture: LinkGraphFoundationFrontierFixture | None = None) -> tuple[LinkGraphFoundationFrontierRegressionSentinel, ...]:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    selected = ("D10-C01-P", "D10-C01-C1", "D10-C02-C2", "D10-C03-C3", "D10-C04-C2")
    return tuple(LinkGraphFoundationFrontierRegressionSentinel(f"sentinel-{record_id.lower()}", next(record.operation.value for record in value.records if record.record_id == record_id), record_id, record.expected_state, record.expected_issue_codes, "locks a public boundary behavior") for record_id in selected for record in value.records if record.record_id == record_id)


def evaluate_link_graph_foundation_frontier_regressions(evaluation: LinkGraphFoundationFrontierEvaluation, fixture: LinkGraphFoundationFrontierFixture | None = None) -> LinkGraphFoundationFrontierRegressionReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    sentinels = default_link_graph_foundation_frontier_sentinels(value)
    results = []
    for sentinel in sentinels:
        row = next((item for item in evaluation.rows if item.record_id == sentinel.record_id), None)
        results.append(LinkGraphFoundationFrontierRegressionResult(sentinel.sentinel_id, sentinel.record_id, bool(row and row.observed_state == sentinel.expected_state), bool(row and set(sentinel.expected_issue_codes) <= set(row.observed_issue_codes)), row.observed_state if row else "missing", row.observed_issue_codes if row else ()))
    values = tuple(results)
    return LinkGraphFoundationFrontierRegressionReport(value.fixture_id, sentinels, values, bool(values) and all(item.accepted for item in values))


def operation_regression_counts(report: LinkGraphFoundationFrontierRegressionReport) -> dict[str, int]:
    return {operation.value: sum(item.operation == operation.value for item in report.sentinels) for operation in LinkGraphFoundationFrontierOperation}


__all__ = ["LinkGraphFoundationFrontierRegressionReport", "LinkGraphFoundationFrontierRegressionResult", "LinkGraphFoundationFrontierRegressionSentinel", "default_link_graph_foundation_frontier_sentinels", "evaluate_link_graph_foundation_frontier_regressions", "operation_regression_counts"]
