"""Local regression benchmark for control frontier evaluation and replay."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from .control_frontier_contracts import ControlFrontierFixture
from .control_frontier_fixture_eval import evaluate_control_frontier_fixture
from .control_frontier_public_data import default_control_frontier_fixture
from .control_frontier_replay import replay_control_frontier_evaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierBenchmarkSample:
    sample_id: str
    repetitions: int
    rows_processed: int
    elapsed_ms: float
    rows_per_second: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierBenchmarkReport:
    fixture_id: str
    samples: tuple[ControlFrontierBenchmarkSample, ...]
    minimum_rows_per_second: float
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _measure(sample_id: str, repetitions: int, fn: Callable[[], int]) -> ControlFrontierBenchmarkSample:
    started = perf_counter()
    rows = sum(fn() for _ in range(repetitions))
    elapsed_ms = max(round((perf_counter() - started) * 1000, 3), 0.001)
    body = {"sample_id": sample_id, "repetitions": repetitions, "rows_processed": rows, "elapsed_ms": elapsed_ms, "rows_per_second": round(rows / (elapsed_ms / 1000), 3)}
    return ControlFrontierBenchmarkSample(**body, content_address=content_hash(body))


def run_control_frontier_benchmark(fixture: ControlFrontierFixture | None = None, *, repetitions: int = 2, minimum_rows_per_second: float = 1.0) -> ControlFrontierBenchmarkReport:
    fixture = fixture or default_control_frontier_fixture()
    evaluation_sample = _measure("evaluation", repetitions, lambda: len(evaluate_control_frontier_fixture(fixture).executions))
    replay_sample = _measure("replay", repetitions, lambda: len(replay_control_frontier_evaluation(fixture, evaluate_control_frontier_fixture(fixture)).checks))
    samples = (evaluation_sample, replay_sample)
    accepted = repetitions > 0 and all(item.rows_per_second >= minimum_rows_per_second for item in samples)
    body = {"fixture_id": fixture.fixture_id, "samples": samples, "minimum_rows_per_second": minimum_rows_per_second, "accepted": accepted}
    return ControlFrontierBenchmarkReport(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierBenchmarkReport", "ControlFrontierBenchmarkSample", "run_control_frontier_benchmark"]
