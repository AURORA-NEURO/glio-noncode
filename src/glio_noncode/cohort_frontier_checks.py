"""Reusable invariants for cohort convergence extension surfaces."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .cohort_frontier_public_data import CohortFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CohortFrontierInvariant:
    invariant_id: str
    operation: CohortFrontierOperation | None
    description: str
    severity: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.invariant_id, "invariant_id")
        require_non_empty(self.description, "description")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierInvariantResult:
    invariant_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierInvariantReport:
    invariants: tuple[CohortFrontierInvariant, ...]
    results: tuple[CohortFrontierInvariantResult, ...]
    accepted: bool
    content_address: str

    @property
    def failed_ids(self) -> tuple[str, ...]:
        return tuple(item.invariant_id for item in self.results if not item.passed)

    def by_operation(self, operation: CohortFrontierOperation) -> tuple[CohortFrontierInvariantResult, ...]:
        ids = {item.invariant_id for item in self.invariants if item.operation is operation}
        return tuple(item for item in self.results if item.invariant_id in ids)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_ids": list(self.failed_ids)}


def default_cohort_frontier_invariants() -> tuple[CohortFrontierInvariant, ...]:
    rows = (("context-preserved", None, "exact cohort context is retained", "blocking"), ("content-addressed", None, "all receipts have addresses", "blocking"), ("positive-control-separated", None, "positive and controls remain distinct", "blocking"), ("parity-visible", CohortFrontierOperation.SUBGROUP_FAIRNESS, "parity gaps remain visible", "review"), ("transport-visible", CohortFrontierOperation.TRANSPORTABILITY, "overlap and shift remain visible", "review"), ("privacy-visible", CohortFrontierOperation.FEDERATED_SUMMARY, "privacy floor remains visible", "blocking"), ("discovery-addressed", CohortFrontierOperation.COHORT_DISCOVERY, "discovery binds an aggregate manifest", "blocking"), ("source-receipts", None, "source IDs resolve", "blocking"), ("issue-vocabulary", None, "issues are declared", "blocking"), ("replay-stable", None, "replay addresses are stable", "blocking"))
    return tuple(CohortFrontierInvariant(*row, content_hash(row)) for row in rows)


def run_cohort_frontier_invariants(observations: dict[str, Any], *, invariants: Iterable[CohortFrontierInvariant] | None = None) -> CohortFrontierInvariantReport:
    selected = tuple(invariants or default_cohort_frontier_invariants())
    results = []
    for invariant in selected:
        value = observations.get(invariant.invariant_id, False)
        body = {"invariant_id": invariant.invariant_id, "passed": bool(value), "observed": value, "expected": True, "detail": invariant.description}
        results.append(CohortFrontierInvariantResult(**body, content_address=content_hash(body)))
    body = {"invariants": selected, "results": tuple(results), "accepted": all(item.passed for item in results)}
    return CohortFrontierInvariantReport(**body, content_address=content_hash(body))


def cohort_frontier_observation_map(**values: bool) -> dict[str, bool]:
    return {str(key).replace("_", "-"): bool(value) for key, value in values.items()}


__all__ = ["CohortFrontierInvariant", "CohortFrontierInvariantReport", "CohortFrontierInvariantResult", "cohort_frontier_observation_map", "default_cohort_frontier_invariants", "run_cohort_frontier_invariants"]
