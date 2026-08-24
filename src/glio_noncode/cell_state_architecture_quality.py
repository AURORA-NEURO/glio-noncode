"""Quality gate over data audit, execution receipts, replay, and release."""

from __future__ import annotations

from .cell_state_architecture_artifacts import artifacts_are_review_safe
from .cell_state_architecture_compliance import assess_cell_state_architecture_compliance
from .cell_state_architecture_contracts import (
    CellStateArchitectureCheck,
    CellStateArchitectureCheckKind,
    CellStateArchitectureDataAudit,
    CellStateArchitectureEvaluation,
    CellStateArchitectureFixture,
    CellStateArchitecturePlan,
    CellStateArchitectureQualityGate,
    CellStateArchitectureRelease,
    CellStateArchitectureScenario,
    addressed,
)
from .cell_state_architecture_ledger import verify_ledger
from .cell_state_architecture_lineage import lineage_gaps
from .cell_state_architecture_metrics import metric_invariants
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
    artifacts: tuple = (),
    ledger=None,
) -> CellStateArchitectureQualityGate:
    checks = (
        _check(
            "quality:data-audit",
            audit.accepted,
            audit.accepted,
            True,
            "public aggregate data audit passes",
            CellStateArchitectureCheckKind.SOURCE,
        ),
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
            "quality:artifacts",
            artifacts_are_review_safe(artifacts),
            len(artifacts),
            6,
            "all release artifacts are review-safe public aggregates",
            CellStateArchitectureCheckKind.RELEASE,
        ),
        _check(
            "quality:metrics",
            not metric_invariants({
                "source_count": len(fixture.sources),
                "operation_count": len(fixture.operations),
                "case_count": len(fixture.cases),
                "positive_count": evaluation.positive_count,
                "control_count": evaluation.control_count,
                "scenario_counts": {
                    scenario.value: sum(item.scenario is scenario for item in fixture.cases)
                    for scenario in CellStateArchitectureScenario
                },
                "check_count": len(evaluation.checks),
            }),
            len(evaluation.checks),
            458,
            "coverage metrics conserve the D08 surface",
            CellStateArchitectureCheckKind.INVARIANT,
        ),
        _check(
            "quality:lineage",
            not lineage_gaps(fixture),
            len(lineage_gaps(fixture)),
            0,
            "source, operation, and case lineage is closed",
            CellStateArchitectureCheckKind.LINEAGE,
        ),
        _check(
            "quality:ledger",
            ledger is not None and verify_ledger(ledger),
            len(ledger.events) if ledger is not None else 0,
            64,
            "append-only execution ledger is reconciled",
            CellStateArchitectureCheckKind.INVARIANT,
        ),
        _check(
            "quality:compliance",
            assess_cell_state_architecture_compliance(fixture)["accepted"] is True,
            assess_cell_state_architecture_compliance(fixture)["accepted"],
            True,
            "aggregate boundary and review-safe payload rules pass",
            CellStateArchitectureCheckKind.SOURCE,
        ),
        _check(
            "quality:state-coverage",
            len({item.observed_result_state for item in evaluation.executions}) >= 6,
            len({item.observed_result_state for item in evaluation.executions}),
            ">=6",
            "positive and held paths cover the D08 state surface",
            CellStateArchitectureCheckKind.OPERATION,
        ),
        _check(
            "quality:control-surface",
            len({issue for item in evaluation.executions for issue in item.issue_codes}) >= 3,
            len({issue for item in evaluation.executions for issue in item.issue_codes}),
            ">=3",
            "control outcomes expose distinct issue codes",
            CellStateArchitectureCheckKind.CONTEXT,
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
