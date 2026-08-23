"""Append-only D09 topology disposition ledger."""

from __future__ import annotations

from collections import Counter

from .topology_architecture_contracts import (
    TopologyArchitectureEvaluation,
    TopologyArchitectureFixture,
    TopologyArchitectureLedger,
    TopologyArchitectureLedgerEvent,
    addressed,
)


def build_topology_architecture_ledger(
    fixture: TopologyArchitectureFixture, evaluation: TopologyArchitectureEvaluation
) -> TopologyArchitectureLedger:
    events: list[TopologyArchitectureLedgerEvent] = []
    for index, (case, execution) in enumerate(
        zip(fixture.cases, evaluation.executions, strict=True), start=1
    ):
        body = {
            "event_id": f"d09-ledger-{index:03d}",
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "state": execution.observed_state.value,
            "disposition": "delegated" if case.scenario.value == "positive" else "held",
            "reason_codes": execution.issue_codes,
            "source_ids": case.source_ids,
            "output_address": execution.output_address,
        }
        events.append(
            TopologyArchitectureLedgerEvent(
                **body, content_address=addressed(body, "topology-ledger-event")
            )
        )
    counts = Counter(item.state for item in events)
    body = {
        "fixture_id": fixture.fixture_id,
        "events": events,
        "state_counts": dict(sorted(counts.items())),
    }
    return TopologyArchitectureLedger(
        fixture.fixture_id,
        tuple(events),
        dict(sorted(counts.items())),
        addressed(body, "topology-ledger"),
    )


def topology_architecture_ledger_is_closed(ledger: TopologyArchitectureLedger) -> bool:
    return (
        len(ledger.events) == 64
        and sum(ledger.state_counts.values()) == 64
        and all(item.output_address.startswith("sha256:") for item in ledger.events)
    )


__all__ = ["build_topology_architecture_ledger", "topology_architecture_ledger_is_closed"]
