"""D12 immutable event ledger projection."""

from __future__ import annotations

from .cohort_architecture_contracts import (
    CohortArchitectureEvaluation,
    CohortArchitectureFixture,
    CohortArchitectureLedger,
    addressed,
)


def build_cohort_architecture_ledger(
    fixture: CohortArchitectureFixture,
    evaluation: CohortArchitectureEvaluation,
) -> CohortArchitectureLedger:
    events = []
    for operation in fixture.operations:
        events.append(
            {
                "event_id": f"operation:{operation.operation_id}",
                "event_kind": "operation-declared",
                "operation_id": operation.operation_id,
                "address": operation.content_address,
            }
        )
    for receipt in evaluation.receipts:
        events.append(
            {
                "event_id": f"case:{receipt.case_id}",
                "event_kind": "case-evaluated",
                "operation_id": receipt.operation_id,
                "state": receipt.observed_state.value,
                "passed": receipt.passed,
                "address": receipt.content_address,
            }
        )
    body = {"fixture_id": fixture.fixture_id, "events": tuple(events)}
    return CohortArchitectureLedger(
        fixture.fixture_id,
        tuple(events),
        addressed(body, "cohort-ledger"),
    )


def cohort_architecture_ledger_is_closed(ledger: CohortArchitectureLedger) -> bool:
    return (
        len(ledger.events) == 80
        and len({item["event_id"] for item in ledger.events}) == 80
        and all(item.get("address") for item in ledger.events)
    )


__all__ = ["build_cohort_architecture_ledger", "cohort_architecture_ledger_is_closed"]
