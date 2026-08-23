"""Release quality gate that reconciles all D02 architecture evidence."""

from __future__ import annotations

from .structural_architecture_contracts import (
    StructuralArchitectureCheck,
    StructuralArchitectureCheckKind,
    StructuralArchitectureQualityGate,
    StructuralArchitectureRuntime,
    StructuralArchitectureState,
    addressed,
)
from .structural_architecture_public_data import audit_structural_architecture_data


def evaluate_structural_architecture_quality(
    runtime: StructuralArchitectureRuntime,
) -> StructuralArchitectureQualityGate:
    """Apply fixture, runtime, release, depth, and privacy checks."""

    audit = audit_structural_architecture_data()
    checks = (
        _check(
            "runtime-state",
            runtime.state is StructuralArchitectureState.PUBLISHED,
            runtime.state.value,
            "published",
            "runtime finalized",
        ),
        _check(
            "stage-count",
            len(runtime.stages) == 20,
            len(runtime.stages),
            20,
            "twenty stages executed",
        ),
        _check(
            "case-count",
            len(runtime.evaluation.receipts) == 64,
            len(runtime.evaluation.receipts),
            64,
            "all cases accounted",
        ),
        _check(
            "positive-count",
            runtime.evaluation.positive_count == 16,
            runtime.evaluation.positive_count,
            16,
            "one positive per operation",
        ),
        _check(
            "control-count",
            runtime.evaluation.control_count == 48,
            runtime.evaluation.control_count,
            48,
            "three controls per operation",
        ),
        _check("fixture-audit", audit.accepted, audit.accepted, True, "source and payload scope"),
        _check(
            "evaluation",
            runtime.evaluation.accepted,
            runtime.evaluation.state.value,
            "accepted",
            "adapter assertions",
        ),
        _check("plan", runtime.plan.accepted, runtime.plan.accepted, True, "dependency plan"),
        _check(
            "review",
            runtime.review_queue.accepted,
            len(runtime.review_queue.items),
            48,
            "controls routed",
        ),
        _check("ledger", runtime.ledger.accepted, len(runtime.ledger.events), 64, "lineage chain"),
        _check(
            "artifacts",
            len(runtime.artifacts) == 6,
            len(runtime.artifacts),
            6,
            "offline artifact inventory",
        ),
        _check(
            "release",
            runtime.release.published,
            runtime.release.state.value,
            "published",
            "release state",
        ),
    )
    state = (
        StructuralArchitectureState.PUBLISHED
        if all(item.passed for item in checks)
        else StructuralArchitectureState.REVIEW
    )
    body = {"fixture_id": runtime.fixture_id, "state": state, "checks": checks}
    return StructuralArchitectureQualityGate(
        fixture_id=runtime.fixture_id,
        state=state,
        checks=checks,
        content_address=addressed(body, "structural-quality"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> StructuralArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": StructuralArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return StructuralArchitectureCheck(
        **body, content_address=addressed(body, "structural-quality-check")
    )


__all__ = ["evaluate_structural_architecture_quality"]
