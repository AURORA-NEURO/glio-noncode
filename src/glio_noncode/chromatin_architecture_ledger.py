"""Final-disposition ledger for every D07 case receipt."""

from __future__ import annotations

from collections import Counter

from .chromatin_architecture_contracts import (
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureFixture,
    ChromatinArchitectureLedger,
    ChromatinArchitectureLedgerEvent,
    addressed,
)


def build_chromatin_architecture_ledger(
    fixture: ChromatinArchitectureFixture,
    evaluation: ChromatinArchitectureEvaluation,
) -> ChromatinArchitectureLedger:
    cases = {item.case_id: item for item in fixture.cases}
    events = tuple(
        ChromatinArchitectureLedgerEvent(
            event_id=f"ledger:{receipt.case_id}",
            case_id=receipt.case_id,
            operation_id=receipt.operation_id,
            state=receipt.observed_state.value,
            disposition="accepted"
            if receipt.expected_state.value == "accepted" and receipt.passed
            else "review",
            reason_codes=receipt.observed_issue_codes,
            source_ids=cases[receipt.case_id].source_ids,
            output_address=receipt.output_address,
            content_address=addressed(
                {
                    "case_id": receipt.case_id,
                    "operation_id": receipt.operation_id,
                    "state": receipt.observed_state,
                    "disposition": "accepted"
                    if receipt.expected_state.value == "accepted" and receipt.passed
                    else "review",
                    "reason_codes": receipt.observed_issue_codes,
                    "source_ids": cases[receipt.case_id].source_ids,
                    "output_address": receipt.output_address,
                },
                "chromatin-ledger-event",
            ),
        )
        for receipt in evaluation.receipts
    )
    state_counts = dict(Counter(item.state for item in events))
    body = {"fixture_id": fixture.fixture_id, "events": events, "state_counts": state_counts}
    return ChromatinArchitectureLedger(
        fixture.fixture_id, events, state_counts, addressed(body, "chromatin-ledger")
    )


__all__ = ["build_chromatin_architecture_ledger"]
