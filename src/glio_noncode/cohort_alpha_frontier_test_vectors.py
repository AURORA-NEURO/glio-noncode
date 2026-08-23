"""Test-vector catalog for state boundary and control behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierTestVector:
    vector_id: str
    operation: str
    expected_state: str
    accepted: bool
    assertion: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierTestVectorSet:
    vectors: tuple[CohortAlphaFrontierTestVector, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_test_vectors(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierTestVectorSet:
    vectors = tuple(CohortAlphaFrontierTestVector(f"vector-{row.record_id}", row.operation, row.observed_state.value, row.accepted, f"{row.operation} emits {row.observed_state.value} for {row.record_id}", content_hash({"id": row.record_id, "operation": row.operation, "state": row.observed_state.value, "accepted": row.accepted}, prefix="alpha-test-vector")) for row in evaluation.rows)
    return CohortAlphaFrontierTestVectorSet(vectors, len(vectors) == 16 and all(item.accepted for item in vectors), content_hash(vectors, prefix="alpha-test-vectors"))


__all__ = ["CohortAlphaFrontierTestVector", "CohortAlphaFrontierTestVectorSet", "build_cohort_alpha_frontier_test_vectors"]
