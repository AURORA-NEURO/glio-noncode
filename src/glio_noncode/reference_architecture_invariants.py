"""Cross-plane invariants for D04 composition."""

from __future__ import annotations

from .reference_architecture_contracts import (
    ReferenceArchitectureCheck,
    ReferenceArchitectureCheckKind,
    ReferenceArchitectureEvaluation,
    ReferenceArchitectureFixture,
    ReferenceArchitectureLedger,
    ReferenceArchitecturePlan,
    ReferenceArchitectureReviewQueue,
    addressed,
)


def check_reference_architecture_invariants(
    fixture: ReferenceArchitectureFixture,
    evaluation: ReferenceArchitectureEvaluation,
    plan: ReferenceArchitecturePlan,
    review_queue: ReferenceArchitectureReviewQueue,
    ledger: ReferenceArchitectureLedger,
) -> tuple[ReferenceArchitectureCheck, ...]:
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
            "operation-cardinality",
            all(
                sum(case.operation_id == node.operation_id for case in fixture.cases) == 4
                for node in plan.nodes
            ),
            len(fixture.cases),
            64,
            "four cases per operation",
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
) -> ReferenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": ReferenceArchitectureCheckKind.INVARIANT,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceArchitectureCheck(
        check_id,
        ReferenceArchitectureCheckKind.INVARIANT,
        passed,
        observed,
        required,
        detail,
        addressed(body, "reference-invariant-check"),
    )


__all__ = ["check_reference_architecture_invariants"]
