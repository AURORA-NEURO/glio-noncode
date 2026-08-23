"""Release quality gate for the composed D05 atlas."""

from __future__ import annotations

from .atlas_architecture_contracts import (
    AtlasArchitectureArtifact,
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    AtlasArchitectureEvaluation,
    AtlasArchitectureFixture,
    AtlasArchitectureLedger,
    AtlasArchitecturePlan,
    AtlasArchitectureQualityGate,
    AtlasArchitectureRelease,
    AtlasArchitectureReviewQueue,
    AtlasArchitectureState,
    addressed,
)


def assess_atlas_architecture_quality(
    fixture: AtlasArchitectureFixture,
    evaluation: AtlasArchitectureEvaluation,
    plan: AtlasArchitecturePlan,
    review_queue: AtlasArchitectureReviewQueue,
    ledger: AtlasArchitectureLedger,
    artifacts: tuple[AtlasArchitectureArtifact, ...],
    release: AtlasArchitectureRelease,
    stage_count: int,
) -> AtlasArchitectureQualityGate:
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
            "all atlas cases pass",
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
        AtlasArchitectureState.PUBLISHED
        if all(item.passed for item in checks)
        else AtlasArchitectureState.BLOCKED
    )
    body = {"fixture_id": fixture.fixture_id, "state": state, "checks": checks}
    return AtlasArchitectureQualityGate(
        fixture.fixture_id, state, checks, addressed(body, "atlas-quality")
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> AtlasArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": AtlasArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return AtlasArchitectureCheck(
        check_id,
        AtlasArchitectureCheckKind.RELEASE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "atlas-quality-check"),
    )


__all__ = ["assess_atlas_architecture_quality"]
