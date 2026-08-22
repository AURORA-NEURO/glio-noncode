"""Small deterministic execution benchmark for the fixture pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .link_graph_alpha_frontier_pipeline import run_link_graph_alpha_frontier_pipeline
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierBenchmarkReport:
    iterations: int
    accepted_iterations: int
    elapsed_seconds: float
    records_processed: int
    records_per_second: float
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"iterations": self.iterations, "accepted_iterations": self.accepted_iterations, "elapsed_seconds": self.elapsed_seconds, "records_processed": self.records_processed, "records_per_second": self.records_per_second}
        if include_address:
            value["content_address"] = self.content_address
        return value


def benchmark_link_graph_alpha_frontier(iterations: int = 1) -> LinkGraphAlphaFrontierBenchmarkReport:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    started = perf_counter()
    accepted = 0
    records = 0
    for _ in range(iterations):
        pipeline = run_link_graph_alpha_frontier_pipeline()
        accepted += pipeline.accepted
        records += len(pipeline.evaluation.rows)
    elapsed = max(perf_counter() - started, 1e-9)
    return LinkGraphAlphaFrontierBenchmarkReport(iterations, accepted, elapsed, records, records / elapsed)


__all__ = ["LinkGraphAlphaFrontierBenchmarkReport", "benchmark_link_graph_alpha_frontier"]
