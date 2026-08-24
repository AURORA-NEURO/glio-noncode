"""Ten-check release quality gate for D14."""

from __future__ import annotations

from .evidence_architecture_artifacts import evidence_architecture_artifacts_are_safe
from .evidence_architecture_contracts import (
    EvidenceArchitectureCheck,
    EvidenceArchitectureCheckKind,
    EvidenceArchitectureDataAudit,
    EvidenceArchitectureEvaluation,
    EvidenceArchitectureFixture,
    EvidenceArchitecturePlan,
    EvidenceArchitectureQualityGate,
    EvidenceArchitectureRelease,
    addressed,
)
from .evidence_architecture_ledger import evidence_architecture_ledger_is_closed
from .evidence_architecture_lineage import evidence_architecture_lineage_gaps
from .evidence_architecture_metrics import (
    evidence_architecture_metric_invariants,
    evidence_architecture_metrics,
)
from .evidence_architecture_replay import EvidenceArchitectureReplay


def _check(check_id: str, passed: bool, observed: object, detail: str) -> EvidenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": EvidenceArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": True,
        "detail": detail,
    }
    return EvidenceArchitectureCheck(
        **body, content_address=addressed(body, "evidence-architecture-quality-check")
    )


def assess_evidence_architecture_quality(
    fixture: EvidenceArchitectureFixture,
    audit: EvidenceArchitectureDataAudit,
    plan: EvidenceArchitecturePlan,
    evaluation: EvidenceArchitectureEvaluation,
    replay: EvidenceArchitectureReplay,
    release: EvidenceArchitectureRelease,
    artifacts,
    ledger=None,
) -> EvidenceArchitectureQualityGate:
    metrics = evidence_architecture_metrics(fixture, evaluation)
    invariants = evidence_architecture_metric_invariants(metrics)
    gaps = evidence_architecture_lineage_gaps(fixture)
    checks = (
        _check(
            "quality:data-audit", audit.accepted, audit.accepted, "public aggregate audit closes"
        ),
        _check("quality:plan", plan.accepted, plan.accepted, "dependency plan closes"),
        _check(
            "quality:evaluation", evaluation.accepted, evaluation.accepted, "all D14 receipts close"
        ),
        _check("quality:replay", replay.accepted, replay.accepted, "deterministic replay closes"),
        _check(
            "quality:artifacts",
            evidence_architecture_artifacts_are_safe(artifacts),
            len(artifacts),
            "six review-safe artifacts are present",
        ),
        _check("quality:metrics", not invariants, invariants, "metric invariants close"),
        _check("quality:lineage", not gaps, gaps, "lineage has no gaps"),
        _check(
            "quality:release",
            release.state.value == "published",
            release.state.value,
            "release follows evaluation and artifact closure",
        ),
        _check(
            "quality:ledger",
            ledger is None or evidence_architecture_ledger_is_closed(ledger),
            bool(ledger is None or evidence_architecture_ledger_is_closed(ledger)),
            "append-only ledger closure is retained",
        ),
        _check(
            "quality:state-coverage",
            len(metrics["state_counts"]) >= 10,
            metrics["state_counts"],
            "positive and held lifecycle states remain visible",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return EvidenceArchitectureQualityGate(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "evidence-architecture-quality"),
    )


def evidence_architecture_quality_summary(
    gate: EvidenceArchitectureQualityGate,
) -> dict[str, object]:
    return {
        "fixture_id": gate.fixture_id,
        "accepted": gate.accepted,
        "check_count": len(gate.checks),
        "passed_count": sum(item.passed for item in gate.checks),
        "failed_check_ids": [item.check_id for item in gate.checks if not item.passed],
    }


__all__ = ["assess_evidence_architecture_quality", "evidence_architecture_quality_summary"]
