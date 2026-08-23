"""Run observability receipts with no raw specimen payload exposure."""

from __future__ import annotations

from dataclasses import dataclass

from .specimen_architecture_contracts import (
    SpecimenArchitectureCheck,
    SpecimenArchitectureCheckKind,
    addressed,
)
from .specimen_architecture_metrics import SpecimenArchitectureMetrics


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureObservation:
    run_id: str
    event_count: int
    addressed_count: int
    error_count: int
    counters: dict[str, int]
    checks: tuple[SpecimenArchitectureCheck, ...]
    content_address: str


def observe_specimen_architecture_run(
    run_id: str,
    stage_count: int,
    metrics: SpecimenArchitectureMetrics,
) -> SpecimenArchitectureObservation:
    """Record stage and metric cardinalities for operations monitoring."""

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
            "address-count",
            metrics.case_count == 64,
            metrics.case_count,
            64,
            "case metrics are bounded",
        ),
        _check(
            "error-count",
            metrics.issue_count == 48,
            metrics.issue_count,
            48,
            "only policy controls carry issues",
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
    return SpecimenArchitectureObservation(
        run_id,
        stage_count,
        metrics.case_count,
        metrics.issue_count,
        counters,
        checks,
        addressed(body, "specimen-observation"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SpecimenArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SpecimenArchitectureCheckKind.INVARIANT,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SpecimenArchitectureCheck(
        check_id,
        SpecimenArchitectureCheckKind.INVARIANT,
        passed,
        observed,
        required,
        detail,
        addressed(body, "specimen-observation-check"),
    )


__all__ = ["SpecimenArchitectureObservation", "observe_specimen_architecture_run"]
