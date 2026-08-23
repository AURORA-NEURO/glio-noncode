"""Quality gate over data audit, execution receipts, replay, and release."""

from __future__ import annotations

from .cell_state_architecture_contracts import (
    CellStateArchitectureCheck,
    CellStateArchitectureCheckKind,
    CellStateArchitectureDataAudit,
    CellStateArchitectureEvaluation,
    CellStateArchitectureFixture,
    CellStateArchitecturePlan,
    CellStateArchitectureQualityGate,
    CellStateArchitectureRelease,
    addressed,
)
from .cell_state_architecture_replay import CellStateArchitectureReplay


def _check(
    check_id: str,
    passed: bool,
    observed: object,
    required: object,
    detail: str,
    kind: CellStateArchitectureCheckKind = CellStateArchitectureCheckKind.RELEASE,
) -> CellStateArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CellStateArchitectureCheck(
        **body, content_address=addressed(body, "cell-state-quality-check")
    )


def assess_cell_state_architecture_quality(
    fixture: CellStateArchitectureFixture,
    audit: CellStateArchitectureDataAudit,
    plan: CellStateArchitecturePlan,
    evaluation: CellStateArchitectureEvaluation,
    replay: CellStateArchitectureReplay,
    release: CellStateArchitectureRelease,
) -> CellStateArchitectureQualityGate:
    checks = (
        *audit.checks,
        _check(
            "quality:plan",
            plan.accepted,
            plan.accepted,
            True,
            "all operation dependencies are ready",
            CellStateArchitectureCheckKind.OPERATION,
        ),
        _check(
            "quality:evaluation",
            evaluation.accepted,
            evaluation.accepted,
            True,
            "all case receipts and checks pass",
            CellStateArchitectureCheckKind.REVIEW,
        ),
        _check(
            "quality:replay",
            replay.accepted,
            replay.accepted,
            True,
            "two deterministic evaluations share an address",
            CellStateArchitectureCheckKind.INVARIANT,
        ),
        _check(
            "quality:release",
            release.state.value == "published",
            release.state.value,
            "published",
            "release boundary is open only after quality inputs pass",
            CellStateArchitectureCheckKind.RELEASE,
        ),
        _check(
            "quality:fixture-identity",
            fixture.fixture_id == evaluation.fixture_id,
            evaluation.fixture_id,
            fixture.fixture_id,
            "fixture and evaluation identities agree",
            CellStateArchitectureCheckKind.IDENTITY,
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "fixture_id": fixture.fixture_id,
        "checks": checks,
        "release": release.content_address,
        "accepted": accepted,
    }
    return CellStateArchitectureQualityGate(
        fixture.fixture_id, tuple(checks), release, accepted, addressed(body, "cell-state-quality")
    )


def quality_summary(gate: CellStateArchitectureQualityGate) -> dict[str, object]:
    return {
        "fixture_id": gate.fixture_id,
        "accepted": gate.accepted,
        "check_count": len(gate.checks),
        "failed_check_ids": [item.check_id for item in gate.checks if not item.passed],
        "release_state": gate.release.state.value,
        "content_address": gate.content_address,
    }


__all__ = ["assess_cell_state_architecture_quality", "quality_summary"]
