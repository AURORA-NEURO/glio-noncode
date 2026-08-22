"""Invariant checks for the Domain 13 planning frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ValidationFrontierInvariant:
    invariant_id: str
    description: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierInvariantResult:
    invariant_id: str
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierInvariantReport:
    results: tuple[ValidationFrontierInvariantResult, ...]
    accepted: bool
    failed_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_ids": list(self.failed_ids)}


def default_validation_frontier_invariants() -> tuple[ValidationFrontierInvariant, ...]:
    rows = (("context-preserved", "exact planning context is retained"), ("positive-control-separated", "positive and control roles remain separate"), ("source-receipts", "public source receipts are present"), ("gap-visible", "evidence gaps remain visible"), ("route-blockers", "assay route blockers remain visible"), ("construct-pairs", "reference and alternate constructs remain paired"), ("limitations-retained", "planning limitations remain visible"), ("content-addressed", "stable artifacts have addresses"), ("replay-stable", "replay has no drift"), ("use-boundary", "allowed and excluded uses remain explicit"))
    return tuple(ValidationFrontierInvariant(invariant_id, description, content_hash({"invariant_id": invariant_id, "description": description})) for invariant_id, description in rows)


def validation_frontier_observation_map(**values: bool) -> dict[str, bool]:
    return {str(key): bool(value) for key, value in values.items()}


def run_validation_frontier_invariants(observations: dict[str, bool]) -> ValidationFrontierInvariantReport:
    results = []
    for invariant in default_validation_frontier_invariants():
        key = invariant.invariant_id.replace("-", "_")
        observed = observations.get(key, False)
        body = {"invariant_id": invariant.invariant_id, "passed": observed, "observed": observed, "required": True}
        results.append(ValidationFrontierInvariantResult(**body, content_address=content_hash(body)))
    failed = tuple(item.invariant_id for item in results if not item.passed)
    body = {"results": tuple(results), "accepted": not failed, "failed_ids": failed}
    return ValidationFrontierInvariantReport(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierInvariant", "ValidationFrontierInvariantReport", "ValidationFrontierInvariantResult", "default_validation_frontier_invariants", "run_validation_frontier_invariants", "validation_frontier_observation_map"]
