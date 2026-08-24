"""Ten-check release quality gate for D15."""

from __future__ import annotations

from .workbench_architecture_artifacts import workbench_architecture_artifacts_are_safe
from .workbench_architecture_contracts import (
    WorkbenchArchitectureCheck,
    WorkbenchArchitectureCheckKind,
    WorkbenchArchitectureDataAudit,
    WorkbenchArchitectureEvaluation,
    WorkbenchArchitectureFixture,
    WorkbenchArchitecturePlan,
    WorkbenchArchitectureQualityGate,
    WorkbenchArchitectureRelease,
    addressed,
)
from .workbench_architecture_ledger import workbench_architecture_ledger_is_closed
from .workbench_architecture_lineage import workbench_architecture_lineage_gaps
from .workbench_architecture_metrics import (
    workbench_architecture_metric_invariants,
    workbench_architecture_metrics,
)
from .workbench_architecture_release import workbench_architecture_release_is_publishable
from .workbench_architecture_replay import WorkbenchArchitectureReplay


def _check(
    check_id: str, passed: bool, observed: object, detail: str
) -> WorkbenchArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": WorkbenchArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": True,
        "detail": detail,
    }
    return WorkbenchArchitectureCheck(
        **body, content_address=addressed(body, "workbench-architecture-quality-check")
    )


def assess_workbench_architecture_quality(
    fixture: WorkbenchArchitectureFixture,
    audit: WorkbenchArchitectureDataAudit,
    plan: WorkbenchArchitecturePlan,
    evaluation: WorkbenchArchitectureEvaluation,
    replay: WorkbenchArchitectureReplay,
    release: WorkbenchArchitectureRelease,
    artifacts,
    ledger=None,
) -> WorkbenchArchitectureQualityGate:
    metrics = workbench_architecture_metrics(fixture, evaluation)
    invariants = workbench_architecture_metric_invariants(metrics)
    gaps = workbench_architecture_lineage_gaps(fixture)
    checks = (
        _check(
            "quality:data-audit", audit.accepted, audit.accepted, "public aggregate audit closes"
        ),
        _check("quality:plan", plan.accepted, plan.accepted, "dependency plan closes"),
        _check(
            "quality:evaluation", evaluation.accepted, evaluation.accepted, "all D15 receipts close"
        ),
        _check("quality:replay", replay.accepted, replay.accepted, "deterministic replay closes"),
        _check(
            "quality:artifacts",
            workbench_architecture_artifacts_are_safe(artifacts),
            len(artifacts),
            "six review-safe artifacts are present",
        ),
        _check("quality:metrics", not invariants, invariants, "metric invariants close"),
        _check("quality:lineage", not gaps, gaps, "lineage has no gaps"),
        _check(
            "quality:release",
            workbench_architecture_release_is_publishable(release),
            release.state.value,
            "release follows evaluation and artifact closure",
        ),
        _check(
            "quality:ledger",
            ledger is None or workbench_architecture_ledger_is_closed(ledger),
            bool(ledger is None or workbench_architecture_ledger_is_closed(ledger)),
            "append-only ledger closure is retained",
        ),
        _check(
            "quality:state-coverage",
            len(metrics["state_counts"]) >= 12,
            metrics["state_counts"],
            "positive and held workbench states remain visible",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return WorkbenchArchitectureQualityGate(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "workbench-architecture-quality"),
    )


def workbench_architecture_quality_summary(
    gate: WorkbenchArchitectureQualityGate,
) -> dict[str, object]:
    return {
        "fixture_id": gate.fixture_id,
        "accepted": gate.accepted,
        "check_count": len(gate.checks),
        "passed_count": sum(item.passed for item in gate.checks),
        "failed_check_ids": [item.check_id for item in gate.checks if not item.passed],
    }


__all__ = ["assess_workbench_architecture_quality", "workbench_architecture_quality_summary"]
