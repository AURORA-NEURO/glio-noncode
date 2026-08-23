"""Repeatable operation workload benchmark without nondeterministic release input."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseFixture
from .validation_release_frontier_fixture_eval import evaluate_validation_release_fixture


@dataclass(frozen=True, slots=True)
class ValidationReleaseBenchmarkResult:
    iterations: int
    record_count: int
    check_count: int
    deterministic_address: str
    elapsed_ms: float
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def benchmark_validation_release(fixture: ValidationReleaseFixture, iterations: int = 3) -> ValidationReleaseBenchmarkResult:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    started = perf_counter()
    reports = tuple(evaluate_validation_release_fixture(fixture) for _ in range(iterations))
    elapsed = round((perf_counter() - started) * 1000, 3)
    addresses = tuple(item.content_address for item in reports)
    body = {"iterations": iterations, "record_count": len(reports[0].executions), "check_count": len(reports[0].checks), "deterministic_address": addresses[0], "elapsed_ms": elapsed, "accepted": len(set(addresses)) == 1 and reports[0].accepted}
    return ValidationReleaseBenchmarkResult(**body, content_address=content_hash({key: value for key, value in body.items() if key != "elapsed_ms"}))


__all__ = ["ValidationReleaseBenchmarkResult", "benchmark_validation_release"]
