"""Deterministic workload descriptors for alpha replay performance checks."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation, evaluate_topology_alpha_frontier_fixture
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture, default_topology_alpha_frontier_fixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierBenchmarkCase:
    case_id: str
    operation: str
    record_count: int
    repetitions: int
    elapsed_seconds: float
    rows_per_second: float
    deterministic: bool
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierBenchmarkReport:
    cases: tuple[TopologyAlphaFrontierBenchmarkCase, ...]
    total_rows: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> TopologyAlphaFrontierBenchmarkCase:
        for item in self.cases:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cases": [item.to_dict() for item in self.cases], "total_rows": self.total_rows, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _run_case(operation: str, fixture: TopologyAlphaFrontierFixture, repetitions: int, runner: Callable[[], TopologyAlphaFrontierEvaluation]) -> TopologyAlphaFrontierBenchmarkCase:
    first = runner()
    start = perf_counter()
    second = first
    for _ in range(repetitions):
        second = runner()
    elapsed = max(perf_counter() - start, 1e-9)
    rows = len(second.rows)
    return TopologyAlphaFrontierBenchmarkCase(f"benchmark-{operation}", operation, rows, repetitions, elapsed, rows * repetitions / elapsed, first.content_address == second.content_address, first.accepted and second.accepted)


def benchmark_topology_alpha_frontier(fixture: TopologyAlphaFrontierFixture | None = None, *, repetitions: int = 2) -> TopologyAlphaFrontierBenchmarkReport:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    value = fixture or default_topology_alpha_frontier_fixture()
    operations = tuple(sorted({item.operation.value for item in value.records}))
    cases = tuple(_run_case(operation, value, repetitions, lambda: evaluate_topology_alpha_frontier_fixture(value)) for operation in operations)
    return TopologyAlphaFrontierBenchmarkReport(cases, sum(item.record_count for item in cases), all(item.accepted and item.deterministic and item.rows_per_second > 0 for item in cases))


__all__ = ["TopologyAlphaFrontierBenchmarkCase", "TopologyAlphaFrontierBenchmarkReport", "benchmark_topology_alpha_frontier"]
