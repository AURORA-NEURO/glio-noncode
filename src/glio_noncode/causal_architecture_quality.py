"""D11 release quality gate."""

from __future__ import annotations

from .causal_architecture_artifacts import causal_architecture_artifacts_are_safe
from .causal_architecture_compliance import assess_causal_architecture_compliance
from .causal_architecture_contracts import (
    CausalArchitectureCheck,
    CausalArchitectureCheckKind,
    CausalArchitectureDataAudit,
    CausalArchitectureEvaluation,
    CausalArchitectureFixture,
    CausalArchitecturePlan,
    CausalArchitectureQualityGate,
    CausalArchitectureRelease,
    addressed,
)
from .causal_architecture_metrics import causal_architecture_metrics
from .causal_architecture_replay import CausalArchitectureReplay


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> CausalArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": CausalArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CausalArchitectureCheck(**body, content_address=addressed(body, "causal-quality-check"))


def assess_causal_architecture_quality(
    fixture: CausalArchitectureFixture,
    audit: CausalArchitectureDataAudit,
    plan: CausalArchitecturePlan,
    evaluation: CausalArchitectureEvaluation,
    replay: CausalArchitectureReplay,
    release: CausalArchitectureRelease,
    artifacts: tuple = (),
) -> CausalArchitectureQualityGate:
    compliance = assess_causal_architecture_compliance(fixture)
    metrics = causal_architecture_metrics(fixture, evaluation)
    checks = (
        _check("quality:audit", audit.accepted, audit.accepted, True, "data audit accepted"),
        _check("quality:plan", plan.accepted, plan.accepted, True, "dependency plan accepted"),
        _check(
            "quality:evaluation",
            evaluation.accepted,
            evaluation.accepted,
            True,
            "all causal receipts and checks passed",
        ),
        _check("quality:replay", replay.accepted, replay.accepted, True, "replay addresses match"),
        _check(
            "quality:release",
            release.state.value == "published",
            release.state.value,
            "published",
            "release state is published",
        ),
        _check(
            "quality:artifacts",
            causal_architecture_artifacts_are_safe(artifacts) if artifacts else True,
            True,
            True,
            "artifact visibility and addresses are safe",
        ),
        _check(
            "quality:boundary",
            fixture.boundary == "public_aggregate_non_patient",
            fixture.boundary,
            "public_aggregate_non_patient",
            "research aggregate boundary is explicit",
        ),
        _check(
            "quality:compliance",
            bool(compliance["accepted"]),
            compliance["accepted"],
            True,
            "recursive public aggregate compliance closes",
        ),
        _check(
            "quality:state-coverage",
            len(metrics["state_counts"]) >= 8,
            metrics["state_counts"],
            "at least eight result states",
            "causal result vocabulary remains visible",
        ),
        _check(
            "quality:control-surface",
            len(metrics["issue_counts"]) >= 15,
            len(metrics["issue_counts"]),
            "at least fifteen issue controls",
            "causal control vocabulary remains broad",
        ),
    )
    return CausalArchitectureQualityGate(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(checks, "causal-quality"),
    )


def causal_architecture_quality_summary(gate: CausalArchitectureQualityGate) -> dict[str, object]:
    return {
        "fixture_id": gate.fixture_id,
        "accepted": gate.accepted,
        "check_count": len(gate.checks),
        "failed_check_ids": [item.check_id for item in gate.checks if not item.passed],
    }


__all__ = ["assess_causal_architecture_quality", "causal_architecture_quality_summary"]
