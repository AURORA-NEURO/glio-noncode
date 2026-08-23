"""Hash-linked D06 receipt lineage."""

from __future__ import annotations

from .sequence_architecture_contracts import (
    SequenceArchitectureCase,
    SequenceArchitectureEvaluation,
    SequenceArchitectureLedger,
    SequenceArchitectureLedgerEvent,
    addressed,
)


def build_sequence_architecture_ledger(
    fixture_id: str,
    cases: tuple[SequenceArchitectureCase, ...],
    evaluation: SequenceArchitectureEvaluation,
) -> SequenceArchitectureLedger:
    receipts = {item.case_id: item for item in evaluation.receipts}
    previous = "sha256:genesis"
    events: list[SequenceArchitectureLedgerEvent] = []
    for index, case in enumerate(cases, 1):
        receipt = receipts[case.case_id]
        body = {
            "sequence": index,
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "input_address": case.content_address,
            "output_address": receipt.output_address,
            "previous_address": previous,
            "state": receipt.observed_state,
        }
        event = SequenceArchitectureLedgerEvent(
            sequence=index,
            case_id=case.case_id,
            operation_id=case.operation_id,
            input_address=case.content_address,
            output_address=receipt.output_address,
            previous_address=previous,
            state=receipt.observed_state,
            content_address=addressed(body, "sequence-ledger-event"),
        )
        events.append(event)
        previous = event.content_address
    accepted = len(events) == len(cases) and _chain_is_valid(tuple(events))
    body = {"fixture_id": fixture_id, "events": events, "accepted": accepted}
    return SequenceArchitectureLedger(
        fixture_id=fixture_id,
        events=tuple(events),
        accepted=accepted,
        content_address=addressed(body, "sequence-ledger"),
    )


def audit_sequence_architecture_ledger(ledger: SequenceArchitectureLedger) -> bool:
    return ledger.accepted and _chain_is_valid(ledger.events)


def sequence_ledger_state_counts(ledger: SequenceArchitectureLedger) -> dict[str, int]:
    return {
        state.value: sum(item.state.value == state.value for item in ledger.events)
        for state in sorted({item.state for item in ledger.events}, key=lambda value: value.value)
    }


def _chain_is_valid(events: tuple[SequenceArchitectureLedgerEvent, ...]) -> bool:
    previous = "sha256:genesis"
    for index, event in enumerate(events, 1):
        if (
            event.sequence != index
            or event.previous_address != previous
            or not event.content_address.startswith("sha256:")
        ):
            return False
        previous = event.content_address
    return True


__all__ = [
    "audit_sequence_architecture_ledger",
    "build_sequence_architecture_ledger",
    "sequence_ledger_state_counts",
]
