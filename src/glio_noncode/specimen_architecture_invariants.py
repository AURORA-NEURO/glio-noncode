"""Cross-module invariants for D03 composition."""

from __future__ import annotations

from .specimen_architecture_contracts import (
    SpecimenArchitectureCheck,
    SpecimenArchitectureCheckKind,
    SpecimenArchitectureEvaluation,
    SpecimenArchitectureFixture,
    SpecimenArchitectureLedger,
    SpecimenArchitecturePlan,
    SpecimenArchitectureReviewQueue,
    addressed,
)


def check_specimen_architecture_invariants(
    fixture: SpecimenArchitectureFixture,
    evaluation: SpecimenArchitectureEvaluation,
    plan: SpecimenArchitecturePlan,
    review_queue: SpecimenArchitectureReviewQueue,
    ledger: SpecimenArchitectureLedger,
) -> tuple[SpecimenArchitectureCheck, ...]:
    """Check joins that are easy for an individual plane to miss."""

    checks = (
        _check(
            "fixture-evaluation-join",
            fixture.fixture_id == evaluation.fixture_id,
            fixture.fixture_id,
            evaluation.fixture_id,
            "fixture and evaluation IDs join",
        ),
        _check(
            "fixture-plan-join",
            fixture.fixture_id == plan.fixture_id,
            fixture.fixture_id,
            plan.fixture_id,
            "fixture and plan IDs join",
        ),
        _check(
            "review-ledger-join",
            review_queue.fixture_id == ledger.fixture_id,
            review_queue.fixture_id,
            ledger.fixture_id,
            "review and lineage IDs join",
        ),
        _check(
            "case-operation-cardinality",
            all(
                sum(case.operation_id == node.operation_id for case in fixture.cases) == 4
                for node in plan.nodes
            ),
            len(fixture.cases),
            64,
            "four cases per plan node",
        ),
        _check(
            "ledger-cardinality",
            len(ledger.events) == len(evaluation.receipts),
            len(ledger.events),
            len(evaluation.receipts),
            "ledger covers every receipt",
        ),
        _check(
            "address-coverage",
            all(case.content_address.startswith("sha256:") for case in fixture.cases),
            len(fixture.cases),
            64,
            "case declarations are addressed",
        ),
    )
    return checks


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SpecimenArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SpecimenArchitectureCheckKind.INVARIANT,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SpecimenArchitectureCheck(
        check_id,
        SpecimenArchitectureCheckKind.INVARIANT,
        passed,
        observed,
        required,
        detail,
        addressed(body, "specimen-invariant-check"),
    )


__all__ = ["check_specimen_architecture_invariants"]
