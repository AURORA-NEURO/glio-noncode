"""Operational observability receipts for the D04 runtime."""

from __future__ import annotations

from dataclasses import dataclass

from .reference_architecture_contracts import (
    ReferenceArchitectureCheck,
    ReferenceArchitectureCheckKind,
    addressed,
)
from .reference_architecture_metrics import ReferenceArchitectureMetrics


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureObservation:
    run_id: str
    event_count: int
    addressed_count: int
    error_count: int
    counters: dict[str, int]
    checks: tuple[ReferenceArchitectureCheck, ...]
    content_address: str


def observe_reference_architecture_run(
    run_id: str, stage_count: int, metrics: ReferenceArchitectureMetrics
) -> ReferenceArchitectureObservation:
    counters = {
        "operations": metrics.operation_count,
        "cases": metrics.case_count,
        "positive_cases": metrics.positive_count,
        "control_cases": metrics.control_count,
        "validation_cells": metrics.validation_cell_count,
    }
    checks = (
        _check(
            "stage-count", stage_count >= 20, stage_count, 20, "runtime has complete stage depth"
        ),
        _check(
            "case-count", metrics.case_count == 64, metrics.case_count, 64, "case count is closed"
        ),
        _check(
            "control-error-count",
            metrics.control_issue_count == 48,
            metrics.control_issue_count,
            48,
            "every control retains one policy issue",
        ),
    )
    body = {
        "run_id": run_id,
        "event_count": stage_count,
        "addressed_count": metrics.case_count,
        "error_count": metrics.issue_count,
        "counters": counters,
        "checks": checks,
    }
    return ReferenceArchitectureObservation(
        run_id,
        stage_count,
        metrics.case_count,
        metrics.issue_count,
        counters,
        checks,
        addressed(body, "reference-observation"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> ReferenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": ReferenceArchitectureCheckKind.INVARIANT,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceArchitectureCheck(
        check_id,
        ReferenceArchitectureCheckKind.INVARIANT,
        passed,
        observed,
        required,
        detail,
        addressed(body, "reference-observation-check"),
    )


__all__ = ["ReferenceArchitectureObservation", "observe_reference_architecture_run"]
