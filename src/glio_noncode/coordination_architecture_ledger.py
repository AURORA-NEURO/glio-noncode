"""Hash-chained event ledger for coordination execution."""

from __future__ import annotations

from .coordination_architecture_contracts import (
    CoordinationExecution,
    CoordinationLedger,
    CoordinationLedgerEvent,
    CoordinationState,
    addressed,
)


def build_coordination_ledger(executions: tuple[CoordinationExecution, ...]) -> CoordinationLedger:
    previous = "coordination-genesis:0"
    events = []
    for ordinal, execution in enumerate(executions, start=1):
        body = {
            "event_id": f"event:{ordinal:03d}:{execution.case_id}",
            "ordinal": ordinal,
            "event_type": "coordination.case.evaluated",
            "case_id": execution.case_id,
            "state": execution.observed_state,
            "previous_address": previous,
        }
        event = CoordinationLedgerEvent(**body, content_address=addressed(body, "coordination-event"))
        events.append(event)
        previous = event.content_address
    body = {"ledger_id": "coordination-execution-ledger", "events": tuple(events), "accepted": True}
    return CoordinationLedger(**body, content_address=addressed(body, "coordination-ledger"))


def verify_coordination_ledger(ledger: CoordinationLedger) -> tuple[str, ...]:
    issues: list[str] = []
    if tuple(item.ordinal for item in ledger.events) != tuple(range(1, len(ledger.events) + 1)):
        issues.append("ordinal_gap")
    previous = "coordination-genesis:0"
    for event in ledger.events:
        if event.previous_address != previous:
            issues.append(f"broken_link:{event.event_id}")
        previous = event.content_address
    if len({item.event_id for item in ledger.events}) != len(ledger.events):
        issues.append("duplicate_event_id")
    return tuple(sorted(set(issues)))


__all__ = ["build_coordination_ledger", "verify_coordination_ledger"]
