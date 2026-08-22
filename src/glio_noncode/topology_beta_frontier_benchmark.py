"""Deterministic capacity receipts for the aggregate beta pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierBenchmarkCase:
    case_id: str
    operation: str
    record_count: int
    evidence_count: int
    issue_count: int
    expected_address_count: int
    bounded: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierBenchmarkReport:
    cases: tuple[TopologyBetaFrontierBenchmarkCase, ...]
    total_records: int
    total_evidence: int
    total_issues: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> TopologyBetaFrontierBenchmarkCase:
        for item in self.cases:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cases": [item.to_dict() for item in self.cases], "total_records": self.total_records, "total_evidence": self.total_evidence, "total_issues": self.total_issues, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_benchmark(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierBenchmarkReport:
    cases = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        rows = evaluation.by_operation(operation)
        cases.append(TopologyBetaFrontierBenchmarkCase(f"benchmark-{operation}", operation, len(rows), sum(len(item.adapter.evidence_ids) for item in rows), sum(len(item.observed_issue_codes) for item in rows), sum(bool(item.adapter.content_address) for item in rows), len(rows) <= 4 and all(item.adapter.measurements is not None for item in rows), "closed fixture capacity receipt"))
    values = tuple(cases)
    return TopologyBetaFrontierBenchmarkReport(values, sum(item.record_count for item in values), sum(item.evidence_count for item in values), sum(item.issue_count for item in values), len(values) == 4 and all(item.bounded for item in values))


__all__ = ["TopologyBetaFrontierBenchmarkCase", "TopologyBetaFrontierBenchmarkReport", "build_topology_beta_frontier_benchmark"]
