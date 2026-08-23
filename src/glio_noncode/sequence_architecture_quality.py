"""D06 release quality gate joining all runtime surfaces."""

from __future__ import annotations

from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureArtifact,
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureEvaluation,
    SequenceArchitectureFixture,
    SequenceArchitectureLedger,
    SequenceArchitecturePlan,
    SequenceArchitectureQualityGate,
    SequenceArchitectureRelease,
    SequenceArchitectureReviewQueue,
    SequenceArchitectureState,
    addressed,
)


def assess_sequence_architecture_quality(
    fixture: SequenceArchitectureFixture,
    evaluation: SequenceArchitectureEvaluation,
    plan: SequenceArchitecturePlan,
    review_queue: SequenceArchitectureReviewQueue,
    ledger: SequenceArchitectureLedger,
    artifacts: tuple[SequenceArchitectureArtifact, ...],
    release: SequenceArchitectureRelease,
    stage_count: int,
) -> SequenceArchitectureQualityGate:
    checks = (
        _check(
            "quality-evaluation",
            evaluation.accepted,
            evaluation.accepted,
            True,
            "all D06 evaluation receipts and checks pass",
        ),
        _check("quality-plan", plan.accepted, plan.accepted, True, "dependency plan is closed"),
        _check(
            "quality-review",
            review_queue.accepted and len(review_queue.items) == 48,
            len(review_queue.items),
            48,
            "all controls are held for review",
        ),
        _check(
            "quality-lineage",
            ledger.accepted and len(ledger.events) == 64,
            len(ledger.events),
            64,
            "all receipts have linked lineage",
        ),
        _check(
            "quality-artifacts",
            len(artifacts) == 6
            and all(item.content_address.startswith("sha256:") for item in artifacts),
            len(artifacts),
            6,
            "six addressed artifacts are materialized",
        ),
        _check(
            "quality-release",
            release.state is SequenceArchitectureState.PUBLISHED,
            release.state.value,
            "published",
            "release state is published",
        ),
        _check(
            "quality-stage-count",
            stage_count == 20,
            stage_count,
            20,
            "twenty ordered stages are closed",
        ),
        _check(
            "quality-source-count",
            len(fixture.sources) == 17,
            len(fixture.sources),
            17,
            "all public family source receipts are retained",
        ),
    )
    passed = all(item.passed for item in checks)
    body = {
        "fixture_id": fixture.fixture_id,
        "checks": checks,
        "passed": passed,
        "release_state": release.state,
    }
    return SequenceArchitectureQualityGate(
        fixture_id=fixture.fixture_id,
        checks=checks,
        passed=passed,
        release_state=SequenceArchitectureState.PUBLISHED
        if passed
        else SequenceArchitectureState.BLOCKED,
        content_address=addressed(body, "sequence-quality"),
    )


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.RELEASE,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-quality-check"),
    )


__all__ = ["assess_sequence_architecture_quality"]
