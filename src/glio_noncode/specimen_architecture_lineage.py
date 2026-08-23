"""Hash-linked lineage ledger for every architecture case receipt."""

from __future__ import annotations

from .specimen_architecture_contracts import (
    SpecimenArchitectureCase,
    SpecimenArchitectureEvaluation,
    SpecimenArchitectureLedger,
    SpecimenArchitectureLedgerEvent,
    SpecimenArchitectureState,
    addressed,
)


def build_specimen_architecture_ledger(
    fixture_id: str,
    cases: tuple[SpecimenArchitectureCase, ...],
    evaluation: SpecimenArchitectureEvaluation,
) -> SpecimenArchitectureLedger:
    """Create a sequential input-to-output chain without raw payload copies."""

    receipts = {item.case_id: item for item in evaluation.receipts}
    previous = "sha256:genesis"
    events: list[SpecimenArchitectureLedgerEvent] = []
    for sequence, case in enumerate(cases, 1):
        receipt = receipts[case.case_id]
        body = {
            "sequence": sequence,
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "input_address": case.content_address,
            "output_address": receipt.output_address,
            "previous_address": previous,
            "state": receipt.observed_state,
        }
        event = SpecimenArchitectureLedgerEvent(
            sequence=sequence,
            case_id=case.case_id,
            operation_id=case.operation_id,
            input_address=case.content_address,
            output_address=receipt.output_address,
            previous_address=previous,
            state=receipt.observed_state,
            content_address=addressed(body, "specimen-ledger-event"),
        )
        events.append(event)
        previous = event.content_address
    accepted = _chain_is_valid(tuple(events)) and len(events) == len(cases)
    return SpecimenArchitectureLedger(
        fixture_id=fixture_id,
        events=tuple(events),
        accepted=accepted,
        content_address=addressed(
            {"fixture_id": fixture_id, "events": events, "accepted": accepted}, "specimen-ledger"
        ),
    )


def _chain_is_valid(events: tuple[SpecimenArchitectureLedgerEvent, ...]) -> bool:
    previous = "sha256:genesis"
    for sequence, event in enumerate(events, 1):
        if event.sequence != sequence or event.previous_address != previous:
            return False
        if not event.input_address or not event.output_address or not event.content_address:
            return False
        previous = event.content_address
    return True


def ledger_state_counts(ledger: SpecimenArchitectureLedger) -> dict[str, int]:
    """Count published-facing ledger states without exposing payloads."""

    return {
        state.value: sum(event.state is state for event in ledger.events)
        for state in SpecimenArchitectureState
    }


__all__ = ["build_specimen_architecture_ledger", "ledger_state_counts"]
