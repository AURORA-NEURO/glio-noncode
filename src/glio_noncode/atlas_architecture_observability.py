"""Operational observability receipts for the D05 atlas runtime."""

from __future__ import annotations

from dataclasses import dataclass

from .atlas_architecture_contracts import (
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    addressed,
)
from .atlas_architecture_metrics import AtlasArchitectureMetrics


@dataclass(frozen=True, slots=True)
class AtlasArchitectureObservation:
    run_id: str
    event_count: int
    addressed_count: int
    error_count: int
    counters: dict[str, int]
    checks: tuple[AtlasArchitectureCheck, ...]
    content_address: str

    def to_dict(self) -> dict[str, object]:
        from .serialization import jsonable

        return jsonable(self)


def observe_atlas_architecture_run(
    run_id: str,
    stage_count: int,
    metrics: AtlasArchitectureMetrics,
) -> AtlasArchitectureObservation:
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
            "control-issue-count",
            metrics.control_issue_count == 48,
            metrics.control_issue_count,
            48,
            "each control retains one boundary issue",
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
    return AtlasArchitectureObservation(
        run_id,
        stage_count,
        metrics.case_count,
        metrics.issue_count,
        counters,
        checks,
        addressed(body, "atlas-observation"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> AtlasArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": AtlasArchitectureCheckKind.INVARIANT,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return AtlasArchitectureCheck(
        check_id,
        AtlasArchitectureCheckKind.INVARIANT,
        passed,
        observed,
        required,
        detail,
        addressed(body, "atlas-observation-check"),
    )


__all__ = ["AtlasArchitectureObservation", "observe_atlas_architecture_run"]
