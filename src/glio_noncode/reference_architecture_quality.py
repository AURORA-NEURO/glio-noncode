"""Release quality gate for D04 reference architecture."""

from __future__ import annotations

from .reference_architecture_contracts import (
    ReferenceArchitectureArtifact,
    ReferenceArchitectureCheck,
    ReferenceArchitectureCheckKind,
    ReferenceArchitectureEvaluation,
    ReferenceArchitectureFixture,
    ReferenceArchitectureLedger,
    ReferenceArchitecturePlan,
    ReferenceArchitectureQualityGate,
    ReferenceArchitectureRelease,
    ReferenceArchitectureReviewQueue,
    ReferenceArchitectureState,
    addressed,
)


def assess_reference_architecture_quality(
    fixture: ReferenceArchitectureFixture,
    evaluation: ReferenceArchitectureEvaluation,
    plan: ReferenceArchitecturePlan,
    review_queue: ReferenceArchitectureReviewQueue,
    ledger: ReferenceArchitectureLedger,
    artifacts: tuple[ReferenceArchitectureArtifact, ...],
    release: ReferenceArchitectureRelease,
    stage_count: int,
) -> ReferenceArchitectureQualityGate:
    checks = (
        _check(
            "fixture",
            len(fixture.operations) == 16 and len(fixture.cases) == 64,
            (len(fixture.operations), len(fixture.cases)),
            (16, 64),
            "fixture cardinality",
        ),
        _check(
            "evaluation",
            evaluation.accepted and len(evaluation.receipts) == 64,
            evaluation.accepted,
            True,
            "all reference cases pass",
        ),
        _check(
            "plan",
            plan.accepted and len(plan.nodes) == 16,
            plan.accepted,
            True,
            "plan is executable",
        ),
        _check(
            "review",
            review_queue.accepted and len(review_queue.items) == 48,
            review_queue.accepted,
            True,
            "controls are routed",
        ),
        _check(
            "lineage",
            ledger.accepted and len(ledger.events) == 64,
            ledger.accepted,
            True,
            "lineage is closed",
        ),
        _check(
            "artifacts",
            len(artifacts) == 6
            and all(item.content_address.startswith("sha256:") for item in artifacts),
            len(artifacts),
            6,
            "six artifacts are addressed",
        ),
        _check("runtime", stage_count >= 20, stage_count, 20, "runtime has complete depth"),
        _check(
            "release", release.published, release.state.value, "published", "release is publishable"
        ),
    )
    state = (
        ReferenceArchitectureState.PUBLISHED
        if all(item.passed for item in checks)
        else ReferenceArchitectureState.BLOCKED
    )
    return ReferenceArchitectureQualityGate(
        fixture.fixture_id,
        state,
        checks,
        addressed(
            {"fixture_id": fixture.fixture_id, "state": state, "checks": checks},
            "reference-quality",
        ),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> ReferenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": ReferenceArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceArchitectureCheck(
        check_id,
        ReferenceArchitectureCheckKind.RELEASE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "reference-quality-check"),
    )


__all__ = ["assess_reference_architecture_quality"]
