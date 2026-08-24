"""D12 release quality gate."""

from __future__ import annotations

from .cohort_architecture_artifacts import cohort_architecture_artifacts_are_safe
from .cohort_architecture_contracts import (
    CohortArchitectureCheck,
    CohortArchitectureCheckKind,
    CohortArchitectureDataAudit,
    CohortArchitectureEvaluation,
    CohortArchitectureFixture,
    CohortArchitecturePlan,
    CohortArchitectureQualityGate,
    CohortArchitectureRelease,
    addressed,
)
from .cohort_architecture_ledger import cohort_architecture_ledger_is_closed
from .cohort_architecture_lineage import cohort_architecture_lineage_gaps
from .cohort_architecture_metrics import (
    cohort_architecture_metric_invariants,
    cohort_architecture_metrics,
)
from .cohort_architecture_replay import CohortArchitectureReplay


def _check(check_id: str, passed: bool, observed: object, detail: str) -> CohortArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": CohortArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": True,
        "detail": detail,
    }
    return CohortArchitectureCheck(**body, content_address=addressed(body, "cohort-quality-check"))


def assess_cohort_architecture_quality(
    fixture: CohortArchitectureFixture,
    audit: CohortArchitectureDataAudit,
    plan: CohortArchitecturePlan,
    evaluation: CohortArchitectureEvaluation,
    replay: CohortArchitectureReplay,
    release: CohortArchitectureRelease,
    artifacts,
    ledger=None,
) -> CohortArchitectureQualityGate:
    metrics = cohort_architecture_metrics(fixture, evaluation)
    checks = (
        _check("quality:data-audit", audit.accepted, audit.accepted, "data audit closes"),
        _check("quality:plan", plan.accepted, plan.accepted, "dependency plan closes"),
        _check(
            "quality:evaluation",
            evaluation.accepted,
            evaluation.accepted,
            "all receipts and checks close",
        ),
        _check("quality:replay", replay.accepted, replay.accepted, "deterministic replay closes"),
        _check(
            "quality:artifacts",
            cohort_architecture_artifacts_are_safe(artifacts),
            len(artifacts),
            "six artifacts are review safe",
        ),
        _check(
            "quality:metrics",
            not cohort_architecture_metric_invariants(metrics),
            cohort_architecture_metric_invariants(metrics),
            "metric invariants close",
        ),
        _check(
            "quality:lineage",
            not cohort_architecture_lineage_gaps(fixture),
            cohort_architecture_lineage_gaps(fixture),
            "lineage has no gaps",
        ),
        _check(
            "quality:release",
            release.state.value == "published",
            release.state.value,
            "release is published",
        ),
        _check(
            "quality:ledger",
            ledger is None or cohort_architecture_ledger_is_closed(ledger),
            True,
            "ledger closure is retained when supplied",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return CohortArchitectureQualityGate(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "cohort-quality"),
    )


def cohort_architecture_quality_summary(
    gate: CohortArchitectureQualityGate,
) -> dict[str, object]:
    return {
        "fixture_id": gate.fixture_id,
        "accepted": gate.accepted,
        "check_count": len(gate.checks),
        "passed_count": sum(item.passed for item in gate.checks),
        "failed_check_ids": [item.check_id for item in gate.checks if not item.passed],
    }


__all__ = ["assess_cohort_architecture_quality", "cohort_architecture_quality_summary"]
