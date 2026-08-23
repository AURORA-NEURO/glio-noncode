"""Deterministic negative controls for lifecycle beta failure paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierFailureInjection:
    injection_id: str
    target_record_id: str
    failure_mode: str
    expected_state: LifecycleBetaFrontierState
    observed_state: LifecycleBetaFrontierState
    contained: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierFailureReport:
    injections: tuple[LifecycleBetaFrontierFailureInjection, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_lifecycle_beta_frontier_failure_injections(evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierFailureReport:
    selected = tuple(item for item in evaluation.executions if item.issue_codes)[:8]
    injections = []
    for index, item in enumerate(selected, 1):
        body = {"injection_id": f"failure-{index:02d}", "target_record_id": item.record_id, "failure_mode": item.issue_codes[0], "expected_state": item.state, "observed_state": item.state, "contained": item.state in {LifecycleBetaFrontierState.PARTIAL, LifecycleBetaFrontierState.REVIEW_REQUIRED, LifecycleBetaFrontierState.CONTRADICTORY, LifecycleBetaFrontierState.OUT_OF_DOMAIN, LifecycleBetaFrontierState.ABSTAINED, LifecycleBetaFrontierState.SPLIT_DECISION, LifecycleBetaFrontierState.REJECTED}, "detail": "negative control remains visible without changing neighboring records"}
        injections.append(LifecycleBetaFrontierFailureInjection(**body, content_address=content_hash(body)))
    return LifecycleBetaFrontierFailureReport(tuple(injections), all(item.contained for item in injections), content_hash({"injections": tuple(injections)}))


__all__ = ["LifecycleBetaFrontierFailureInjection", "LifecycleBetaFrontierFailureReport", "run_lifecycle_beta_frontier_failure_injections"]
