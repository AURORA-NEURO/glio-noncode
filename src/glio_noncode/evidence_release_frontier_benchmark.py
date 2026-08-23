"""Small deterministic benchmark model for the release surface.

The benchmark is intentionally local and synthetic. It measures the amount of
work represented by a fixture run, not scientific quality, throughput claims, or
production infrastructure capacity. Its purpose is to keep accidental quadratic
operations visible during refactors.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseBenchmarkResult:
    row_count: int
    check_count: int
    source_join_count: int
    expected_comparisons: int
    bounded: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def benchmark_evidence_release(evaluation: Any, fixture: Any) -> EvidenceReleaseBenchmarkResult:
    row_count = len(evaluation.executions)
    check_count = len(evaluation.checks)
    source_join_count = sum(len(record.source_ids) for record in fixture.records)
    expected_comparisons = row_count * 5 + source_join_count
    body = {"row_count": row_count, "check_count": check_count, "source_join_count": source_join_count, "expected_comparisons": expected_comparisons, "bounded": expected_comparisons <= 10000}
    return EvidenceReleaseBenchmarkResult(**body, content_address=content_hash(body))


def benchmark_is_closed(result: EvidenceReleaseBenchmarkResult) -> bool:
    return result.bounded and result.row_count > 0 and result.check_count >= result.row_count * 5


__all__ = ["EvidenceReleaseBenchmarkResult", "benchmark_evidence_release", "benchmark_is_closed"]
