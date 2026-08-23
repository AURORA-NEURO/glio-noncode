"""Append-only receipt ledger for D08 case executions."""

from __future__ import annotations

from collections import Counter

from .cell_state_architecture_contracts import (
    CellStateArchitectureEvaluation,
    CellStateArchitectureFixture,
    CellStateArchitectureLedger,
    CellStateArchitectureLedgerEvent,
    addressed,
)


def build_cell_state_architecture_ledger(
    fixture: CellStateArchitectureFixture, evaluation: CellStateArchitectureEvaluation
) -> CellStateArchitectureLedger:
    events: list[CellStateArchitectureLedgerEvent] = []
    for index, (case, execution) in enumerate(
        zip(fixture.cases, evaluation.executions, strict=True), start=1
    ):
        body = {
            "event_id": f"d08-ledger-{index:03d}",
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "state": execution.observed_state.value,
            "disposition": "delegated" if case.scenario.value == "positive" else "held",
            "reason_codes": execution.issue_codes,
            "source_ids": case.source_ids,
            "output_address": execution.output_address,
        }
        events.append(
            CellStateArchitectureLedgerEvent(
                **body, content_address=addressed(body, "cell-state-ledger-event")
            )
        )
    counts = Counter(event.state for event in events)
    body = {
        "fixture_id": fixture.fixture_id,
        "events": events,
        "state_counts": dict(sorted(counts.items())),
    }
    return CellStateArchitectureLedger(
        fixture.fixture_id,
        tuple(events),
        dict(sorted(counts.items())),
        addressed(body, "cell-state-ledger"),
    )


def verify_ledger(ledger: CellStateArchitectureLedger) -> bool:
    return (
        len(ledger.events) == 64
        and all(event.output_address.startswith("sha256:") for event in ledger.events)
        and sum(ledger.state_counts.values()) == len(ledger.events)
    )


__all__ = ["build_cell_state_architecture_ledger", "verify_ledger"]
