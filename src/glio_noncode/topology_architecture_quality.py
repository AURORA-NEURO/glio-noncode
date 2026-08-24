"""Quality gate over D09 audit, plan, evaluation, replay, and release."""

from __future__ import annotations

from .topology_architecture_artifacts import topology_architecture_artifacts_are_safe
from .topology_architecture_compliance import assess_topology_architecture_compliance
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
from .topology_architecture_ledger import topology_architecture_ledger_is_closed
from .topology_architecture_lineage import topology_architecture_lineage_gaps
from .topology_architecture_metrics import (
    topology_architecture_metric_invariants,
    topology_architecture_metrics,
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
    artifacts: tuple = (),
    ledger=None,
) -> TopologyArchitectureQualityGate:
    metrics = topology_architecture_metrics(fixture, evaluation)
    compliance = assess_topology_architecture_compliance(fixture)
    checks = (
        _check(
            "quality:data-audit",
            audit.accepted,
            audit.accepted,
            True,
            "topology data audit closes",
        ),
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
            "quality:artifacts",
            topology_architecture_artifacts_are_safe(artifacts),
            len(artifacts),
            "six artifacts are review safe",
            "topology artifacts remain public aggregate and review safe",
        ),
        _check(
            "quality:metrics",
            not topology_architecture_metric_invariants(metrics),
            topology_architecture_metric_invariants(metrics),
            (),
            "topology metric invariants close",
        ),
        _check(
            "quality:lineage",
            not topology_architecture_lineage_gaps(fixture),
            topology_architecture_lineage_gaps(fixture),
            (),
            "topology source and operation lineage has no gaps",
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
            "quality:ledger",
            ledger is None or topology_architecture_ledger_is_closed(ledger),
            True,
            True,
            "topology ledger closure is retained",
            TopologyArchitectureCheckKind.CONTROL,
        ),
        _check(
            "quality:compliance",
            bool(compliance["accepted"]),
            compliance["accepted"],
            True,
            "recursive public aggregate compliance closes",
            TopologyArchitectureCheckKind.CONTROL,
        ),
        _check(
            "quality:state-coverage",
            len(metrics["state_counts"]) >= 4,
            metrics["state_counts"],
            "at least four topology result states",
            "topology result state vocabulary remains visible",
            TopologyArchitectureCheckKind.OPERATION,
        ),
        _check(
            "quality:control-surface",
            len(metrics["issue_counts"]) >= 3,
            len(metrics["issue_counts"]),
            "at least three topology issue controls",
            "topology control vocabulary remains visible",
            TopologyArchitectureCheckKind.CONTROL,
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
