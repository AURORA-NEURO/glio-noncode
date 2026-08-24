"""D13 release quality gate."""

from __future__ import annotations

from .planning_architecture_artifacts import planning_architecture_artifacts_are_safe
from .planning_architecture_contracts import (
    PlanningArchitectureCheck,
    PlanningArchitectureCheckKind,
    PlanningArchitectureDataAudit,
    PlanningArchitectureEvaluation,
    PlanningArchitectureFixture,
    PlanningArchitecturePlan,
    PlanningArchitectureQualityGate,
    PlanningArchitectureRelease,
    PlanningArchitectureState,
    addressed,
)
from .planning_architecture_ledger import planning_architecture_ledger_is_closed
from .planning_architecture_lineage import planning_architecture_lineage_gaps
from .planning_architecture_metrics import (
    planning_architecture_metric_invariants,
    planning_architecture_metrics,
)
from .planning_architecture_replay import PlanningArchitectureReplay


def _check(check_id: str, passed: bool, observed: object, detail: str) -> PlanningArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": PlanningArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": True,
        "detail": detail,
    }
    return PlanningArchitectureCheck(
        **body,
        content_address=addressed(body, "planning-quality-check"),
    )


def assess_planning_architecture_quality(
    fixture: PlanningArchitectureFixture,
    audit: PlanningArchitectureDataAudit,
    plan: PlanningArchitecturePlan,
    evaluation: PlanningArchitectureEvaluation,
    replay: PlanningArchitectureReplay,
    release: PlanningArchitectureRelease,
    artifacts,
    ledger=None,
) -> PlanningArchitectureQualityGate:
    metrics = planning_architecture_metrics(fixture, evaluation)
    invariants = planning_architecture_metric_invariants(metrics)
    lineage_gaps = planning_architecture_lineage_gaps(fixture)
    checks = (
        _check("quality:data-audit", audit.accepted, audit.accepted, "public data audit closes"),
        _check("quality:plan", plan.accepted, plan.accepted, "dependency plan closes"),
        _check(
            "quality:evaluation", evaluation.accepted, evaluation.accepted, "all D13 receipts close"
        ),
        _check("quality:replay", replay.accepted, replay.accepted, "deterministic replay closes"),
        _check(
            "quality:artifacts",
            planning_architecture_artifacts_are_safe(artifacts),
            len(artifacts),
            "six review-safe artifacts are present",
        ),
        _check("quality:metrics", not invariants, invariants, "metric invariants close"),
        _check("quality:lineage", not lineage_gaps, lineage_gaps, "lineage has no gaps"),
        _check(
            "quality:release",
            release.state is PlanningArchitectureState.PUBLISHED,
            release.state.value,
            "release is published only after evaluation and artifacts close",
        ),
        _check(
            "quality:ledger",
            ledger is None or planning_architecture_ledger_is_closed(ledger),
            ledger is None or planning_architecture_ledger_is_closed(ledger),
            "append-only ledger closure is retained when supplied",
        ),
        _check(
            "quality:state-coverage",
            len(metrics["state_counts"]) >= 6,
            metrics["state_counts"],
            "positive and held planning states remain visible",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return PlanningArchitectureQualityGate(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "planning-quality"),
    )


def planning_architecture_quality_summary(
    gate: PlanningArchitectureQualityGate,
) -> dict[str, object]:
    return {
        "fixture_id": gate.fixture_id,
        "accepted": gate.accepted,
        "check_count": len(gate.checks),
        "passed_count": sum(item.passed for item in gate.checks),
        "failed_check_ids": [item.check_id for item in gate.checks if not item.passed],
    }


__all__ = ["assess_planning_architecture_quality", "planning_architecture_quality_summary"]
