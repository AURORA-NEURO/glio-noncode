"""Deterministic benchmark ledger for Domain 10 C01-C04 operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierOperation, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierBenchmarkCase:
    case_id: str
    operation: str
    record_ids: tuple[str, ...]
    expected_states: tuple[str, ...]
    expected_issue_codes: tuple[str, ...]
    work_units: int
    work_limit: int

    @property
    def within_budget(self) -> bool:
        return 0 < self.work_units <= self.work_limit

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierBenchmarkResult:
    case_id: str
    operation: str
    observed_states: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool
    within_budget: bool
    work_units: int

    @property
    def accepted(self) -> bool:
        return self.state_match and self.issue_match and self.within_budget

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierBenchmarkReport:
    fixture_id: str
    cases: tuple[LinkGraphFoundationFrontierBenchmarkCase, ...]
    results: tuple[LinkGraphFoundationFrontierBenchmarkResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_case_ids(self) -> tuple[str, ...]:
        return tuple(item.case_id for item in self.results if not item.accepted)

    @property
    def operation_count(self) -> int:
        return len({item.operation for item in self.results})

    def result(self, case_id: str) -> LinkGraphFoundationFrontierBenchmarkResult:
        for item in self.results:
            if item.case_id == case_id:
                return item
        raise KeyError(case_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cases": [item.to_dict() for item in self.cases], "results": [item.to_dict() for item in self.results], "failed_case_ids": self.failed_case_ids, "operation_count": self.operation_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _cases(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation) -> tuple[LinkGraphFoundationFrontierBenchmarkCase, ...]:
    values = []
    for operation in LinkGraphFoundationFrontierOperation:
        rows = evaluation.by_operation(operation.value)
        values.append(LinkGraphFoundationFrontierBenchmarkCase(f"benchmark-{operation.value}", operation.value, tuple(row.record_id for row in rows), tuple(row.expected_state for row in rows), tuple(sorted({code for row in rows for code in row.expected_issue_codes})), sum(len(row.adapter.evidence_ids) + len(row.adapter.issue_codes) + int(row.adapter.measurements.get("link_count", row.adapter.measurements.get("element_count", 0))) + 3 for row in rows), 64))
    return tuple(values)


def build_link_graph_foundation_frontier_benchmark(evaluation: LinkGraphFoundationFrontierEvaluation, fixture: LinkGraphFoundationFrontierFixture | None = None) -> LinkGraphFoundationFrontierBenchmarkReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    cases = _cases(value, evaluation)
    results = []
    for case in cases:
        rows = tuple(row for row in evaluation.rows if row.record_id in case.record_ids)
        observed_states = tuple(row.observed_state for row in rows)
        observed_issue_codes = tuple(sorted({code for row in rows for code in row.observed_issue_codes}))
        results.append(LinkGraphFoundationFrontierBenchmarkResult(case.case_id, case.operation, observed_states, observed_issue_codes, observed_states == case.expected_states, observed_issue_codes == case.expected_issue_codes, case.within_budget, case.work_units))
    observed = tuple(results)
    return LinkGraphFoundationFrontierBenchmarkReport(value.fixture_id, cases, observed, bool(observed) and all(item.accepted for item in observed))


def benchmark_link_graph_foundation_frontier_operation(operation: str, evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierBenchmarkResult:
    value = evaluation or __import__("glio_noncode.link_graph_foundation_frontier_fixture_eval", fromlist=["evaluate_link_graph_foundation_frontier_fixture"]).evaluate_link_graph_foundation_frontier_fixture()
    report = build_link_graph_foundation_frontier_benchmark(value)
    return next(item for item in report.results if item.operation == operation)


__all__ = ["LinkGraphFoundationFrontierBenchmarkCase", "LinkGraphFoundationFrontierBenchmarkReport", "LinkGraphFoundationFrontierBenchmarkResult", "benchmark_link_graph_foundation_frontier_operation", "build_link_graph_foundation_frontier_benchmark"]
