"""Quality gate over D09 audit, plan, evaluation, replay, and release."""

from __future__ import annotations

from .topology_architecture_contracts import (
    TopologyArchitectureCheck,
    TopologyArchitectureCheckKind,
    TopologyArchitectureDataAudit,
    TopologyArchitectureEvaluation,
    TopologyArchitectureFixture,
    TopologyArchitecturePlan,
    TopologyArchitectureQualityGate,
    TopologyArchitectureRelease,
    addressed,
)
from .topology_architecture_replay import TopologyArchitectureReplay


def _check(
    check_id: str,
    passed: bool,
    observed: object,
    required: object,
    detail: str,
    kind: TopologyArchitectureCheckKind = TopologyArchitectureCheckKind.RELEASE,
) -> TopologyArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return TopologyArchitectureCheck(
        **body, content_address=addressed(body, "topology-quality-check")
    )


def assess_topology_architecture_quality(
    fixture: TopologyArchitectureFixture,
    audit: TopologyArchitectureDataAudit,
    plan: TopologyArchitecturePlan,
    evaluation: TopologyArchitectureEvaluation,
    replay: TopologyArchitectureReplay,
    release: TopologyArchitectureRelease,
) -> TopologyArchitectureQualityGate:
    checks = (
        *audit.checks,
        _check(
            "quality:plan",
            plan.accepted,
            plan.accepted,
            True,
            "topology dependencies are ready",
            TopologyArchitectureCheckKind.OPERATION,
        ),
        _check(
            "quality:evaluation",
            evaluation.accepted,
            evaluation.accepted,
            True,
            "all topology receipts and checks pass",
            TopologyArchitectureCheckKind.CONTROL,
        ),
        _check(
            "quality:replay",
            replay.accepted,
            replay.accepted,
            True,
            "topology replay is deterministic",
            TopologyArchitectureCheckKind.REPLAY,
        ),
        _check(
            "quality:release",
            release.state.value == "published",
            release.state.value,
            "published",
            "topology release is gated",
            TopologyArchitectureCheckKind.RELEASE,
        ),
        _check(
            "quality:identity",
            fixture.fixture_id == evaluation.fixture_id,
            evaluation.fixture_id,
            fixture.fixture_id,
            "topology fixture and evaluation identities agree",
            TopologyArchitectureCheckKind.IDENTITY,
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "fixture_id": fixture.fixture_id,
        "checks": checks,
        "release": release.content_address,
        "accepted": accepted,
    }
    return TopologyArchitectureQualityGate(
        fixture.fixture_id, tuple(checks), release, accepted, addressed(body, "topology-quality")
    )


def topology_architecture_quality_summary(
    gate: TopologyArchitectureQualityGate,
) -> dict[str, object]:
    return {
        "fixture_id": gate.fixture_id,
        "accepted": gate.accepted,
        "check_count": len(gate.checks),
        "failed_check_ids": [item.check_id for item in gate.checks if not item.passed],
        "release_state": gate.release.state.value,
    }


__all__ = ["assess_topology_architecture_quality", "topology_architecture_quality_summary"]
