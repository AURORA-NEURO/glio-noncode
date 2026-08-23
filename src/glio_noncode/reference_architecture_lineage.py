"""Hash-linked case lineage for the D04 reference architecture."""

from __future__ import annotations

from .reference_architecture_contracts import (
    ReferenceArchitectureCase,
    ReferenceArchitectureEvaluation,
    ReferenceArchitectureLedger,
    ReferenceArchitectureLedgerEvent,
    ReferenceArchitectureState,
    addressed,
)


def build_reference_architecture_ledger(
    fixture_id: str,
    cases: tuple[ReferenceArchitectureCase, ...],
    evaluation: ReferenceArchitectureEvaluation,
) -> ReferenceArchitectureLedger:
    """Link every case declaration to its sanitized execution output."""

    receipt_map = {item.case_id: item for item in evaluation.receipts}
    events: list[ReferenceArchitectureLedgerEvent] = []
    previous = "sha256:genesis"
    for sequence, case in enumerate(cases, 1):
        receipt = receipt_map[case.case_id]
        body = {
            "sequence": sequence,
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "input_address": case.content_address,
            "output_address": receipt.output_address,
            "previous_address": previous,
            "state": receipt.observed_state,
        }
        event = ReferenceArchitectureLedgerEvent(
            sequence,
            case.case_id,
            case.operation_id,
            case.content_address,
            receipt.output_address,
            previous,
            receipt.observed_state,
            addressed(body, "reference-ledger-event"),
        )
        events.append(event)
        previous = event.content_address
    accepted = _chain_is_valid(tuple(events)) and len(events) == len(cases)
    return ReferenceArchitectureLedger(
        fixture_id,
        tuple(events),
        accepted,
        addressed(
            {"fixture_id": fixture_id, "events": events, "accepted": accepted}, "reference-ledger"
        ),
    )


def _chain_is_valid(events: tuple[ReferenceArchitectureLedgerEvent, ...]) -> bool:
    previous = "sha256:genesis"
    for sequence, event in enumerate(events, 1):
        if (
            event.sequence != sequence
            or event.previous_address != previous
            or not event.input_address
            or not event.output_address
        ):
            return False
        previous = event.content_address
    return True


def reference_ledger_state_counts(ledger: ReferenceArchitectureLedger) -> dict[str, int]:
    """Return state counts without publishing raw payloads."""

    return {
        state.value: sum(event.state is state for event in ledger.events)
        for state in ReferenceArchitectureState
    }


__all__ = ["build_reference_architecture_ledger", "reference_ledger_state_counts"]
