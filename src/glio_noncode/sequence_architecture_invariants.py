"""Cross-module cardinality, join, and state invariants for D06."""

from __future__ import annotations

from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureEvaluation,
    SequenceArchitectureFixture,
    SequenceArchitectureLedger,
    SequenceArchitecturePlan,
    SequenceArchitectureReviewQueue,
    addressed,
)


def check_sequence_architecture_invariants(
    fixture: SequenceArchitectureFixture,
    evaluation: SequenceArchitectureEvaluation,
    plan: SequenceArchitecturePlan,
    review_queue: SequenceArchitectureReviewQueue,
    ledger: SequenceArchitectureLedger,
) -> tuple[SequenceArchitectureCheck, ...]:
    checks = (
        _check(
            "invariant-source-join",
            all(
                set(item.source_ids) <= {source.source_id for source in fixture.sources}
                for item in fixture.operations
            ),
            True,
            True,
            "operation sources join fixture sources",
        ),
        _check(
            "invariant-case-operation-join",
            {item.operation_id for item in fixture.cases} == set(fixture.operation_ids),
            len({item.operation_id for item in fixture.cases}),
            16,
            "cases join every operation",
        ),
        _check(
            "invariant-receipt-case-join",
            {item.case_id for item in evaluation.receipts}
            == {item.case_id for item in fixture.cases},
            len(evaluation.receipts),
            64,
            "receipts join every case",
        ),
        _check(
            "invariant-plan-operation-join",
            {item.operation_id for item in plan.nodes} == set(fixture.operation_ids),
            len(plan.nodes),
            16,
            "plan joins every operation",
        ),
        _check(
            "invariant-review-control-join",
            {item.case_id for item in review_queue.items}
            == {item.case_id for item in fixture.control_cases},
            len(review_queue.items),
            48,
            "review queue contains every control",
        ),
        _check(
            "invariant-ledger-receipt-join",
            {item.case_id for item in ledger.events}
            == {item.case_id for item in evaluation.receipts},
            len(ledger.events),
            64,
            "ledger contains every receipt",
        ),
    )
    return checks


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.INVARIANT,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.INVARIANT,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-invariant-check"),
    )


__all__ = ["check_sequence_architecture_invariants"]
