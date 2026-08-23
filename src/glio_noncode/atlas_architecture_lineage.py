"""Append-only hash-linked lineage for D05 case receipts."""

from __future__ import annotations

from .atlas_architecture_contracts import (
    AtlasArchitectureCase,
    AtlasArchitectureEvaluation,
    AtlasArchitectureLedger,
    AtlasArchitectureLedgerEvent,
    addressed,
)


def build_atlas_architecture_ledger(
    fixture_id: str,
    cases: tuple[AtlasArchitectureCase, ...],
    evaluation: AtlasArchitectureEvaluation,
) -> AtlasArchitectureLedger:
    receipts = {item.case_id: item for item in evaluation.receipts}
    events: list[AtlasArchitectureLedgerEvent] = []
    previous = "sha256:genesis"
    for sequence, case in enumerate(cases, start=1):
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
        event = AtlasArchitectureLedgerEvent(
            sequence,
            case.case_id,
            case.operation_id,
            case.content_address,
            receipt.output_address,
            previous,
            receipt.observed_state,
            addressed(body, "atlas-ledger-event"),
        )
        events.append(event)
        previous = event.content_address
    accepted = _chain_is_valid(tuple(events)) and len(events) == len(cases)
    body = {"fixture_id": fixture_id, "events": events, "accepted": accepted}
    return AtlasArchitectureLedger(
        fixture_id, tuple(events), accepted, addressed(body, "atlas-ledger")
    )


def audit_atlas_architecture_ledger(ledger: AtlasArchitectureLedger) -> bool:
    return ledger.accepted and _chain_is_valid(ledger.events)


def atlas_ledger_state_counts(ledger: AtlasArchitectureLedger) -> dict[str, int]:
    return {
        state: sum(item.state.value == state for item in ledger.events)
        for state in ("accepted", "review")
    }


def _chain_is_valid(events: tuple[AtlasArchitectureLedgerEvent, ...]) -> bool:
    previous = "sha256:genesis"
    for sequence, event in enumerate(events, start=1):
        if event.sequence != sequence or event.previous_address != previous:
            return False
        previous = event.content_address
    return True


__all__ = [
    "audit_atlas_architecture_ledger",
    "atlas_ledger_state_counts",
    "build_atlas_architecture_ledger",
]
