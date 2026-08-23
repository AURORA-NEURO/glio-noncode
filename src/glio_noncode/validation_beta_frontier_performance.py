"""Bounded performance receipt without claiming production capacity."""

from time import perf_counter
from typing import Any, Callable


def measure_validation_beta_frontier_operation(fn: Callable[[], Any]) -> dict[str, Any]:
    start = perf_counter()
    output = fn()
    duration_ms = round((perf_counter() - start) * 1000, 3)
    address = str(getattr(output, "content_address", "unaddressed"))
    return {"duration_ms": duration_ms, "output_address": address, "bounded": duration_ms >= 0, "result_type": type(output).__name__}


__all__ = ["measure_validation_beta_frontier_operation"]
