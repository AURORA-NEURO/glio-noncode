"""Hash-linked provenance and custody ledger for public intake receipts."""

from __future__ import annotations

from .intake_architecture_contracts import (
    IntakeArchitectureEvaluation,
    IntakeArchitectureLedger,
    IntakeArchitectureLedgerEvent,
    IntakeArchitectureState,
    addressed,
)


def build_intake_architecture_ledger(evaluation: IntakeArchitectureEvaluation) -> IntakeArchitectureLedger:
    events: list[IntakeArchitectureLedgerEvent] = []
    previous = "genesis:intake-d01"
    for ordinal, result in enumerate(evaluation.results, start=1):
        body = {
            "event_id": f"intake-event:{ordinal:03d}",
            "ordinal": ordinal,
            "case_id": result.case_id,
            "event_type": "operation_evaluated",
            "state": result.observed_state,
            "previous_address": previous,
        }
        event = IntakeArchitectureLedgerEvent(**body, content_address=addressed(body, "intake-ledger-event"))
        events.append(event)
        previous = event.content_address
    body = {"ledger_id": "intake-ledger-d01", "events": tuple(events), "accepted": bool(events) and len(events) == 64}
    return IntakeArchitectureLedger(**body, content_address=addressed(body, "intake-ledger"))


def verify_intake_architecture_ledger(ledger: IntakeArchitectureLedger) -> tuple[str, ...]:
    issues: list[str] = []
    previous = "genesis:intake-d01"
    for ordinal, event in enumerate(ledger.events, start=1):
        if event.ordinal != ordinal:
            issues.append(f"ordinal_gap:{event.event_id}")
        if event.previous_address != previous:
            issues.append(f"broken_link:{event.event_id}")
        previous = event.content_address
    if not ledger.events:
        issues.append("empty_ledger")
    return tuple(sorted(set(issues)))


__all__ = ["build_intake_architecture_ledger", "verify_intake_architecture_ledger"]
