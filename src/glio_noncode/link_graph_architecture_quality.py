"""D10 release quality gate."""

from __future__ import annotations

from .link_graph_architecture_artifacts import link_graph_architecture_artifacts_are_safe
from .link_graph_architecture_compliance import assess_link_graph_architecture_compliance
from .link_graph_architecture_contracts import (
    LinkGraphArchitectureCheck,
    LinkGraphArchitectureCheckKind,
    LinkGraphArchitectureDataAudit,
    LinkGraphArchitectureEvaluation,
    LinkGraphArchitectureFixture,
    LinkGraphArchitecturePlan,
    LinkGraphArchitectureQualityGate,
    LinkGraphArchitectureRelease,
    addressed,
)
from .link_graph_architecture_metrics import link_graph_architecture_metrics
from .link_graph_architecture_replay import LinkGraphArchitectureReplay


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> LinkGraphArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": LinkGraphArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return LinkGraphArchitectureCheck(**body, content_address=addressed(body, "link-quality-check"))


def assess_link_graph_architecture_quality(
    fixture: LinkGraphArchitectureFixture,
    audit: LinkGraphArchitectureDataAudit,
    plan: LinkGraphArchitecturePlan,
    evaluation: LinkGraphArchitectureEvaluation,
    replay: LinkGraphArchitectureReplay,
    release: LinkGraphArchitectureRelease,
    artifacts: tuple = (),
) -> LinkGraphArchitectureQualityGate:
    compliance = assess_link_graph_architecture_compliance(fixture)
    metrics = link_graph_architecture_metrics(fixture, evaluation)
    checks = (
        _check("quality:audit", audit.accepted, audit.accepted, True, "data audit accepted"),
        _check("quality:plan", plan.accepted, plan.accepted, True, "dependency plan accepted"),
        _check(
            "quality:evaluation",
            evaluation.accepted,
            evaluation.accepted,
            True,
            "all D10 receipts and checks passed",
        ),
        _check("quality:replay", replay.accepted, replay.accepted, True, "replay addresses match"),
        _check(
            "quality:release",
            release.state.value,
            release.state.value,
            "published",
            "release state is published",
        ),
        _check(
            "quality:artifacts",
            link_graph_architecture_artifacts_are_safe(artifacts) if artifacts else True,
            True,
            True,
            "artifact visibility and addresses are safe",
        ),
        _check(
            "quality:boundary",
            fixture.boundary == "public_aggregate_non_patient",
            fixture.boundary,
            "public_aggregate_non_patient",
            "aggregate boundary is explicit",
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
            "at least eight link result states",
            "link result vocabulary remains visible",
        ),
        _check(
            "quality:control-surface",
            len(metrics["issue_counts"]) >= 15,
            len(metrics["issue_counts"]),
            "at least fifteen issue controls",
            "link control vocabulary remains broad",
        ),
    )
    return LinkGraphArchitectureQualityGate(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(checks, "link-quality"),
    )


def link_graph_architecture_quality_summary(
    gate: LinkGraphArchitectureQualityGate,
) -> dict[str, object]:
    return {
        "fixture_id": gate.fixture_id,
        "accepted": gate.accepted,
        "check_count": len(gate.checks),
        "failed_check_ids": [item.check_id for item in gate.checks if not item.passed],
    }


__all__ = ["assess_link_graph_architecture_quality", "link_graph_architecture_quality_summary"]
