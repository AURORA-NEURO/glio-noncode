"""Repeatable workload measurements for the lifecycle beta frontier runtime."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_fixture_eval import evaluate_lifecycle_beta_frontier_fixture
from .lifecycle_beta_frontier_public_data import default_lifecycle_beta_frontier_fixture
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierBenchmarkSample:
    """One measured workload sample with its functional output count."""

    sample_id: str
    repetitions: int
    records_processed: int
    elapsed_ms: float
    records_per_second: float
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.sample_id, "sample_id")
        if self.repetitions < 1 or self.records_processed < 1:
            raise ValueError("benchmark sample dimensions must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierBenchmarkReport:
    """Benchmark report used for regression review, not scientific inference."""

    fixture_id: str
    samples: tuple[LifecycleBetaFrontierBenchmarkSample, ...]
    minimum_records_per_second: float
    accepted: bool
    content_address: str

    @property
    def slowest_records_per_second(self) -> float:
        return min(item.records_per_second for item in self.samples)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"slowest_records_per_second": self.slowest_records_per_second}


def _measure(sample_id: str, repetitions: int, fn: Callable[[], int]) -> LifecycleBetaFrontierBenchmarkSample:
    started = perf_counter()
    records = 0
    for _ in range(repetitions):
        records += fn()
    elapsed_ms = max(round((perf_counter() - started) * 1000, 3), 0.001)
    records_per_second = round(records / (elapsed_ms / 1000), 3)
    body = {
        "sample_id": sample_id,
        "repetitions": repetitions,
        "records_processed": records,
        "elapsed_ms": elapsed_ms,
        "records_per_second": records_per_second,
    }
    return LifecycleBetaFrontierBenchmarkSample(**body, content_address=content_hash(body))


def run_lifecycle_beta_frontier_benchmark(
    fixture: LifecycleBetaFrontierFixture | None = None,
    *,
    repetitions: int = 2,
    minimum_records_per_second: float = 1.0,
) -> LifecycleBetaFrontierBenchmarkReport:
    """Measure evaluation and projection workloads over aggregate rows."""

    if repetitions < 1:
        raise ValueError("benchmark repetitions must be positive")
    fixture = fixture or default_lifecycle_beta_frontier_fixture()
    evaluation_sample = _measure(
        "fixture-evaluation",
        repetitions,
        lambda: len(evaluate_lifecycle_beta_frontier_fixture(fixture).executions),
    )
    projection_sample = _measure(
        "record-address-scan",
        repetitions,
        lambda: sum(item.content_address.startswith("sha256:") for item in fixture.records),
    )
    samples = (evaluation_sample, projection_sample)
    accepted = all(item.records_per_second >= minimum_records_per_second for item in samples)
    body = {
        "fixture_id": fixture.fixture_id,
        "samples": samples,
        "minimum_records_per_second": minimum_records_per_second,
        "accepted": accepted,
    }
    return LifecycleBetaFrontierBenchmarkReport(**body, content_address=content_hash(body))


__all__ = [
    "LifecycleBetaFrontierBenchmarkReport",
    "LifecycleBetaFrontierBenchmarkSample",
    "run_lifecycle_beta_frontier_benchmark",
]
