"""Quality gate with coordination cross-plane closure for D16."""

from __future__ import annotations

from .platform_execution_architecture_artifacts import platform_execution_artifacts_are_safe
from .platform_execution_architecture_contracts import (
    PlatformExecutionCheck,
    PlatformExecutionCheckKind,
    PlatformExecutionDataAudit,
    PlatformExecutionEvaluation,
    PlatformExecutionFixture,
    PlatformExecutionPlan,
    PlatformExecutionQualityGate,
    PlatformExecutionRelease,
    addressed,
)
from .platform_execution_architecture_ledger import platform_execution_ledger_is_closed
from .platform_execution_architecture_metrics import (
    platform_execution_metric_invariants,
    platform_execution_metrics,
)
from .platform_execution_architecture_release import platform_execution_release_is_publishable
from .platform_execution_architecture_replay import PlatformExecutionReplay


def _check(check_id: str, passed: bool, observed: object, detail: str) -> PlatformExecutionCheck:
    body = {
        "check_id": check_id,
        "kind": PlatformExecutionCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": True,
        "detail": detail,
    }
    return PlatformExecutionCheck(
        **body, content_address=addressed(body, "platform-execution-quality-check")
    )


def _coordination_closure() -> tuple[bool, dict[str, object]]:
    from .coordination_architecture_operations import evaluate_coordination_fixture
    from .coordination_architecture_public_data import default_coordination_fixture

    fixture = default_coordination_fixture()
    evaluation = evaluate_coordination_fixture(fixture)
    detail = {
        "fixture_id": fixture.fixture_id,
        "case_count": len(fixture.cases),
        "accepted": evaluation.accepted,
        "content_address": fixture.content_address,
    }
    return evaluation.accepted and len(fixture.cases) == 64, detail


def assess_platform_execution_quality(
    fixture: PlatformExecutionFixture,
    audit: PlatformExecutionDataAudit,
    plan: PlatformExecutionPlan,
    evaluation: PlatformExecutionEvaluation,
    replay: PlatformExecutionReplay,
    release: PlatformExecutionRelease,
    artifacts,
    ledger=None,
) -> PlatformExecutionQualityGate:
    metrics = platform_execution_metrics(fixture, evaluation)
    invariants = platform_execution_metric_invariants(metrics)
    coordination_ok, coordination_detail = _coordination_closure()
    checks = (
        _check(
            "quality:data-audit", audit.accepted, audit.accepted, "public aggregate audit closes"
        ),
        _check("quality:plan", plan.accepted, plan.accepted, "dependency plan closes"),
        _check(
            "quality:evaluation", evaluation.accepted, evaluation.accepted, "all D16 receipts close"
        ),
        _check("quality:replay", replay.accepted, replay.accepted, "deterministic replay closes"),
        _check(
            "quality:artifacts",
            platform_execution_artifacts_are_safe(artifacts),
            len(artifacts),
            "six artifacts are safe",
        ),
        _check("quality:metrics", not invariants, invariants, "metric invariants close"),
        _check(
            "quality:release",
            platform_execution_release_is_publishable(release),
            release.state.value,
            "release follows evaluation and artifacts",
        ),
        _check(
            "quality:ledger",
            ledger is None or platform_execution_ledger_is_closed(ledger),
            bool(ledger is None or platform_execution_ledger_is_closed(ledger)),
            "ledger closure is retained",
        ),
        _check(
            "quality:state-coverage",
            len(metrics["state_counts"]) >= 12,
            metrics["state_counts"],
            "execution states remain visible",
        ),
        _check(
            "quality:coordination-closure",
            coordination_ok,
            coordination_detail,
            "coordination fixture closes the cross-plane contract",
        ),
        _check(
            "quality:control-surface",
            len(metrics["issue_counts"]) >= 20,
            len(metrics["issue_counts"]),
            "control issue vocabulary remains broad",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return PlatformExecutionQualityGate(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "platform-execution-quality"),
    )


__all__ = ["assess_platform_execution_quality"]
