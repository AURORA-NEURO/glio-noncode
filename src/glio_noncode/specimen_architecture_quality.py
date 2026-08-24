"""Release quality gate for the composed specimen runtime."""

from __future__ import annotations

from typing import Any

from .specimen_architecture_compliance import assess_specimen_architecture_compliance
from .specimen_architecture_contracts import (
    SpecimenArchitectureArtifact,
    SpecimenArchitectureCheck,
    SpecimenArchitectureCheckKind,
    SpecimenArchitectureEvaluation,
    SpecimenArchitectureFixture,
    SpecimenArchitectureLedger,
    SpecimenArchitecturePlan,
    SpecimenArchitectureQualityGate,
    SpecimenArchitectureRelease,
    SpecimenArchitectureReviewQueue,
    SpecimenArchitectureScenario,
    SpecimenArchitectureState,
    addressed,
)


def assess_specimen_architecture_quality(
    fixture: SpecimenArchitectureFixture,
    evaluation: SpecimenArchitectureEvaluation,
    plan: SpecimenArchitecturePlan,
    review_queue: SpecimenArchitectureReviewQueue,
    ledger: SpecimenArchitectureLedger,
    artifacts: tuple[SpecimenArchitectureArtifact, ...],
    release: SpecimenArchitectureRelease,
    stage_count: int,
    compliance: Any | None = None,
) -> SpecimenArchitectureQualityGate:
    """Close publication only when every depth and integrity assertion passes."""

    compliance_report = compliance or assess_specimen_architecture_compliance(fixture)
    context_closed = all(
        bool(item.delegate_context_key)
        and (
            item.scenario is not SpecimenArchitectureScenario.FOREIGN_CONTEXT
            or item.context_key != item.delegate_context_key
        )
        for item in fixture.cases
    )
    state_count = len({item.observed_result_state for item in evaluation.receipts})
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
            "all cases passed",
        ),
        _check(
            "plan",
            plan.accepted and len(plan.nodes) == 16,
            plan.accepted,
            True,
            "dependency plan is executable",
        ),
        _check(
            "review",
            review_queue.accepted and len(review_queue.items) == 48,
            review_queue.accepted,
            True,
            "all controls route to review",
        ),
        _check(
            "lineage",
            ledger.accepted and len(ledger.events) == 64,
            ledger.accepted,
            True,
            "lineage chain is closed",
        ),
        _check(
            "artifacts",
            len(artifacts) == 6
            and all(item.content_address.startswith("sha256:") for item in artifacts),
            len(artifacts),
            6,
            "six artifacts are addressed",
        ),
        _check("runtime", stage_count == 24, stage_count, 24, "runtime has complete stage depth"),
        _check(
            "release", release.published, release.state.value, "published", "release is publishable"
        ),
        _check(
            "evaluation-check-count",
            len(evaluation.checks) == 458,
            len(evaluation.checks),
            458,
            "case and global evaluation checks are closed",
        ),
        _check(
            "result-state-count",
            state_count >= 6,
            state_count,
            ">=6",
            "result states cover positive and held outcomes",
        ),
        _check(
            "context-boundary",
            context_closed,
            context_closed,
            True,
            "delegated contexts and foreign controls are explicit",
        ),
        _check(
            "compliance",
            compliance_report.accepted,
            compliance_report.accepted,
            True,
            "public aggregate compliance is accepted",
        ),
    )
    state = (
        SpecimenArchitectureState.PUBLISHED
        if all(item.passed for item in checks)
        else SpecimenArchitectureState.BLOCKED
    )
    return SpecimenArchitectureQualityGate(
        fixture.fixture_id,
        state,
        checks,
        addressed(
            {"fixture_id": fixture.fixture_id, "state": state, "checks": checks}, "specimen-quality"
        ),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SpecimenArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SpecimenArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SpecimenArchitectureCheck(
        check_id,
        SpecimenArchitectureCheckKind.RELEASE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "specimen-quality-check"),
    )


__all__ = ["assess_specimen_architecture_quality"]
