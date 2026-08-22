"""Deterministic benchmark ledger for C05-C08 beta evidence paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierOperation, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierBenchmarkCase:
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
class LinkGraphBetaFrontierBenchmarkResult:
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
class LinkGraphBetaFrontierBenchmarkReport:
    fixture_id: str
    cases: tuple[LinkGraphBetaFrontierBenchmarkCase, ...]
    results: tuple[LinkGraphBetaFrontierBenchmarkResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_case_ids(self) -> tuple[str, ...]:
        return tuple(item.case_id for item in self.results if not item.accepted)

    def result(self, case_id: str) -> LinkGraphBetaFrontierBenchmarkResult:
        return next(item for item in self.results if item.case_id == case_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cases": [item.to_dict() for item in self.cases], "results": [item.to_dict() for item in self.results], "failed_case_ids": self.failed_case_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_benchmark(evaluation: LinkGraphBetaFrontierEvaluation, fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierBenchmarkReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    cases = []
    results = []
    for operation in LinkGraphBetaFrontierOperation:
        rows = evaluation.by_operation(operation.value)
        case = LinkGraphBetaFrontierBenchmarkCase(f"benchmark-{operation.value}", operation.value, tuple(row.record_id for row in rows), tuple(row.expected_state for row in rows), tuple(sorted({issue for row in rows for issue in row.expected_issue_codes})), sum(3 + len(row.adapter.evidence_ids) + len(row.adapter.issue_codes) + int(row.adapter.measurements.get("observation_count", 0)) for row in rows), 64)
        cases.append(case)
        results.append(LinkGraphBetaFrontierBenchmarkResult(case.case_id, case.operation, tuple(row.observed_state for row in rows), tuple(sorted({issue for row in rows for issue in row.observed_issue_codes})), all(row.state_match for row in rows), tuple(sorted({issue for row in rows for issue in row.observed_issue_codes})) == case.expected_issue_codes, case.within_budget, case.work_units))
    values = tuple(results)
    return LinkGraphBetaFrontierBenchmarkReport(value.fixture_id, tuple(cases), values, bool(values) and all(item.accepted for item in values))


__all__ = ["LinkGraphBetaFrontierBenchmarkCase", "LinkGraphBetaFrontierBenchmarkReport", "LinkGraphBetaFrontierBenchmarkResult", "build_link_graph_beta_frontier_benchmark"]
