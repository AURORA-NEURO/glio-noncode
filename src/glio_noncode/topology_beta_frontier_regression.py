"""Regression expectations for the closed Domain 09 beta surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture, TopologyBetaFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierRegressionAssertion:
    assertion_id: str
    category: str
    observed: Any
    expected: Any
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierRegressionCase:
    case_id: str
    operation: str
    assertions: tuple[TopologyBetaFrontierRegressionAssertion, ...]
    passed: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def failed(self) -> tuple[TopologyBetaFrontierRegressionAssertion, ...]:
        return tuple(item for item in self.assertions if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"case_id": self.case_id, "operation": self.operation, "assertions": [item.to_dict() for item in self.assertions], "passed": self.passed}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierRegressionReport:
    cases: tuple[TopologyBetaFrontierRegressionCase, ...]
    assertion_count: int
    passed_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def case(self, operation: str) -> TopologyBetaFrontierRegressionCase:
        for item in self.cases:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def failed(self) -> tuple[TopologyBetaFrontierRegressionAssertion, ...]:
        return tuple(item for case in self.cases for item in case.failed())

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cases": [item.to_dict() for item in self.cases], "assertion_count": self.assertion_count, "passed_count": self.passed_count, "accepted": self.accepted, "failed_count": len(self.failed())}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _assert(assertion_id: str, category: str, observed: Any, expected: Any, detail: str) -> TopologyBetaFrontierRegressionAssertion:
    return TopologyBetaFrontierRegressionAssertion(assertion_id, category, observed, expected, observed == expected, detail)


def build_topology_beta_frontier_regression(fixture: TopologyBetaFrontierFixture, evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierRegressionReport:
    cases = []
    expected_states = {
        "loop_stripe": ("supported", "partial", "ambiguous", "out_of_domain"),
        "promoter_capture": ("supported", "partial", "ambiguous", "out_of_domain"),
        "enhancer_promoter_contact": ("supported", "ambiguous", "out_of_domain", "absent"),
        "activity_by_contact": ("supported", "abstained", "ambiguous", "out_of_domain"),
    }
    for operation in TopologyBetaFrontierOperation:
        rows = evaluation.by_operation(operation.value)
        assertions = (
            _assert(f"{operation.value}-count", "cardinality", len(rows), 4, "four records are retained per operation"),
            _assert(f"{operation.value}-positive", "role", sum(item.role == "positive" for item in rows), 1, "one positive path is retained"),
            _assert(f"{operation.value}-controls", "role", sum(item.role == "control" for item in rows), 3, "three controls are retained"),
            _assert(f"{operation.value}-states", "states", tuple(item.observed_state for item in rows), expected_states[operation.value], "state order is deterministic"),
            _assert(f"{operation.value}-addresses", "integrity", all(item.adapter.content_address.startswith("sha256:") for item in rows), True, "every result has an address"),
            _assert(f"{operation.value}-sources", "lineage", all(item.adapter.source_ids for item in rows), True, "every result retains source IDs"),
            _assert(f"{operation.value}-issues", "issues", all(item.issue_match for item in rows), True, "issue floors are retained"),
            _assert(f"{operation.value}-measurements", "measurements", all(item.adapter.measurements is not None for item in rows), True, "measurement maps are present"),
        )
        cases.append(TopologyBetaFrontierRegressionCase(f"regression-{operation.value}", operation.value, assertions, all(item.passed for item in assertions)))
    values = tuple(cases)
    all_assertions = tuple(item for case in values for item in case.assertions)
    return TopologyBetaFrontierRegressionReport(values, len(all_assertions), sum(item.passed for item in all_assertions), bool(values) and all(item.passed for item in all_assertions),)


def summarize_topology_beta_frontier_regression(report: TopologyBetaFrontierRegressionReport) -> dict[str, Any]:
    return {"case_count": len(report.cases), "assertion_count": report.assertion_count, "passed_count": report.passed_count, "failed_count": len(report.failed()), "accepted": report.accepted, "operations": {item.operation: item.passed for item in report.cases}}


__all__ = ["TopologyBetaFrontierRegressionAssertion", "TopologyBetaFrontierRegressionCase", "TopologyBetaFrontierRegressionReport", "build_topology_beta_frontier_regression", "summarize_topology_beta_frontier_regression"]
