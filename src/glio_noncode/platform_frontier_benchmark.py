"""Small deterministic benchmark receipt for platform operation latency."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierFixture
from .platform_frontier_fixture_eval import evaluate_platform_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierBenchmarkSample:
    repetition: int
    duration_ms: float
    evaluation_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierBenchmarkReport:
    fixture_id: str
    repetitions: int
    samples: tuple[PlatformFrontierBenchmarkSample, ...]
    median_ms: float
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_platform_frontier_benchmark(fixture: PlatformFrontierFixture, *, repetitions: int = 2) -> PlatformFrontierBenchmarkReport:
    samples = []
    for repetition in range(1, repetitions + 1):
        started = perf_counter()
        evaluation = evaluate_platform_frontier_fixture(fixture)
        duration = round((perf_counter() - started) * 1000, 3)
        body = {"repetition": repetition, "duration_ms": duration, "evaluation_address": evaluation.content_address, "accepted": evaluation.accepted}
        samples.append(PlatformFrontierBenchmarkSample(**body, content_address=content_hash(body)))
    durations = sorted(item.duration_ms for item in samples)
    median = durations[len(durations) // 2] if durations else 0.0
    deterministic = len({item.evaluation_address for item in samples}) <= 1
    return PlatformFrontierBenchmarkReport(fixture.fixture_id, repetitions, tuple(samples), median, deterministic, bool(samples) and all(item.accepted for item in samples), content_hash(tuple(samples)))


__all__ = ["PlatformFrontierBenchmarkReport", "PlatformFrontierBenchmarkSample", "run_platform_frontier_benchmark"]
