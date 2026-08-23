"""Hash-linked source-to-case-to-result lineage for D02."""

from __future__ import annotations

from typing import Any

from .structural_architecture_contracts import (
    StructuralArchitectureEvaluation,
    StructuralArchitectureFixture,
    StructuralArchitectureLedger,
    StructuralArchitectureLedgerEvent,
    addressed,
)


def build_structural_architecture_ledger(
    fixture: StructuralArchitectureFixture,
    evaluation: StructuralArchitectureEvaluation,
) -> StructuralArchitectureLedger:
    """Create an append-only receipt chain in fixture order."""

    previous = addressed(
        {"fixture_id": fixture.fixture_id, "context_key": fixture.context_key},
        "structural-ledger-root",
    )
    events: list[StructuralArchitectureLedgerEvent] = []
    for sequence, receipt in enumerate(evaluation.receipts, 1):
        case = fixture.cases[sequence - 1]
        body = {
            "sequence": sequence,
            "case_id": receipt.case_id,
            "operation_id": receipt.operation_id,
            "input_address": case.content_address,
            "output_address": receipt.output_address,
            "previous_address": previous,
            "state": receipt.observed_state,
        }
        event = StructuralArchitectureLedgerEvent(
            **body, content_address=addressed(body, "structural-ledger-event")
        )
        events.append(event)
        previous = event.content_address
    accepted = _ledger_is_contiguous(events, fixture, evaluation)
    body = {"fixture_id": fixture.fixture_id, "events": events, "accepted": accepted}
    return StructuralArchitectureLedger(
        fixture_id=fixture.fixture_id,
        events=tuple(events),
        accepted=accepted,
        content_address=addressed(body, "structural-ledger"),
    )


def audit_structural_architecture_ledger(
    ledger: StructuralArchitectureLedger,
    expected_count: int,
) -> dict[str, Any]:
    """Return a compact audit without exposing operation payloads."""

    contiguous = all(
        left.content_address == right.previous_address
        for left, right in zip(ledger.events, ledger.events[1:], strict=True)
    )
    result = {
        "fixture_id": ledger.fixture_id,
        "event_count": len(ledger.events),
        "expected_count": expected_count,
        "contiguous": contiguous,
        "unique_case_count": len({item.case_id for item in ledger.events}),
        "accepted": ledger.accepted and len(ledger.events) == expected_count and contiguous,
        "content_address": addressed(
            {"ledger": ledger.to_dict(), "expected_count": expected_count},
            "structural-ledger-audit",
        ),
    }
    return result


def _ledger_is_contiguous(
    events: list[StructuralArchitectureLedgerEvent],
    fixture: StructuralArchitectureFixture,
    evaluation: StructuralArchitectureEvaluation,
) -> bool:
    return (
        len(events) == len(fixture.cases) == len(evaluation.receipts)
        and tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1))
        and len({item.case_id for item in events}) == len(events)
        and all(item.output_address.startswith("sha256:") for item in events)
    )


__all__ = ["audit_structural_architecture_ledger", "build_structural_architecture_ledger"]
