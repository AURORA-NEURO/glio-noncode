"""Composed D07 quality gate across data, execution, lineage, and release."""

from __future__ import annotations

from .chromatin_architecture_contracts import (
    ChromatinArchitectureCheck,
    ChromatinArchitectureCheckKind,
    ChromatinArchitectureDataAudit,
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureFixture,
    ChromatinArchitecturePlan,
    ChromatinArchitectureQualityGate,
    ChromatinArchitectureRelease,
    ChromatinArchitectureReviewQueue,
    addressed,
)
from .chromatin_architecture_failures import ChromatinArchitectureFailureReport
from .chromatin_architecture_invariants import check_chromatin_architecture_invariants
from .chromatin_architecture_lineage import (
    ChromatinArchitectureLineage,
    verify_chromatin_architecture_lineage,
)
from .chromatin_architecture_metrics import ChromatinArchitectureMetrics
from .chromatin_architecture_policy import ChromatinArchitecturePolicyReport
from .chromatin_architecture_replay import ChromatinArchitectureReplay
from .chromatin_architecture_schema import ChromatinArchitectureSchemaReport


def _check(
    check_id: str, passed: bool, detail: str, observed: object = None, required: object = True
) -> ChromatinArchitectureCheck:
    body = {
        "check_id": check_id,
        "passed": passed,
        "observed": observed if observed is not None else passed,
        "required": required,
        "detail": detail,
    }
    return ChromatinArchitectureCheck(
        check_id,
        ChromatinArchitectureCheckKind.RELEASE,
        passed,
        body["observed"],
        required,
        detail,
        addressed(body, "chromatin-quality-check"),
    )


def assess_chromatin_architecture_quality(
    fixture: ChromatinArchitectureFixture,
    audit: ChromatinArchitectureDataAudit,
    plan: ChromatinArchitecturePlan,
    evaluation: ChromatinArchitectureEvaluation,
    policy: ChromatinArchitecturePolicyReport,
    review: ChromatinArchitectureReviewQueue,
    lineage: ChromatinArchitectureLineage,
    metrics: ChromatinArchitectureMetrics,
    schema: ChromatinArchitectureSchemaReport,
    replay: ChromatinArchitectureReplay,
    failures: ChromatinArchitectureFailureReport,
    release: ChromatinArchitectureRelease,
) -> ChromatinArchitectureQualityGate:
    invariants = check_chromatin_architecture_invariants(fixture, evaluation)
    checks = (
        _check("data-audit", audit.accepted, "public aggregate data audit accepted"),
        _check("plan", plan.accepted, "dependency plan accepted"),
        _check("evaluation", evaluation.accepted, "64 case evaluation accepted"),
        _check("policy", policy.accepted, "acceptance and review policy accepted"),
        _check(
            "review",
            review.accepted and len(review.items) == 48,
            "all 48 controls are routed to review",
        ),
        _check(
            "lineage",
            verify_chromatin_architecture_lineage(lineage, fixture, evaluation),
            "source-to-receipt lineage closes",
        ),
        _check("schema", schema.accepted, "interchange schema accepted"),
        _check("replay", replay.accepted, "replay is deterministic"),
        _check(
            "invariants",
            bool(invariants) and all(item.passed for item in invariants),
            "cross-surface invariants close",
        ),
        _check(
            "metrics",
            metrics.receipt_count == 64 and metrics.passed_receipt_count == 64,
            "metrics conserve receipts",
        ),
        _check(
            "failure-report",
            failures.accepted,
            "failure vocabulary is non-blocking for the accepted fixture",
        ),
        _check(
            "release", release.state.value == "published", "release reaches the published boundary"
        ),
        _check(
            "artifact-floor",
            len(release.artifact_ids) == 6,
            "six release artifacts are materialized",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "release": release}
    return ChromatinArchitectureQualityGate(
        fixture.fixture_id,
        checks,
        release,
        all(item.passed for item in checks),
        addressed(body, "chromatin-quality"),
    )


__all__ = ["assess_chromatin_architecture_quality"]
