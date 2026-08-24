"""Append-only D13 event ledger."""

from __future__ import annotations

from typing import Any

from .planning_architecture_contracts import (
    PlanningArchitectureEvaluation,
    PlanningArchitectureFixture,
    PlanningArchitectureLedger,
    addressed,
)
from .planning_architecture_public_data import default_planning_architecture_fixture


def build_planning_architecture_ledger(
    fixture: PlanningArchitectureFixture | None = None,
    evaluation: PlanningArchitectureEvaluation | None = None,
) -> PlanningArchitectureLedger:
    selected = fixture or default_planning_architecture_fixture()
    events: list[dict[str, Any]] = []
    for operation in selected.operations:
        body = {
            "sequence": len(events) + 1,
            "event_type": "operation_declared",
            "operation_id": operation.operation_id,
            "capability_id": operation.capability_id,
            "family": operation.family,
            "content_address": operation.content_address,
        }
        events.append(body | {"event_address": addressed(body, "planning-ledger-event")})
    if evaluation is not None:
        for execution in evaluation.executions:
            body = {
                "sequence": len(events) + 1,
                "event_type": "case_executed",
                "case_id": execution.case_id,
                "family": execution.family,
                "scenario": execution.scenario,
                "state": execution.observed_state,
                "output_address": execution.output_address,
            }
            events.append(body | {"event_address": addressed(body, "planning-ledger-event")})
    body = {"fixture_id": selected.fixture_id, "events": events}
    return PlanningArchitectureLedger(
        selected.fixture_id,
        tuple(events),
        addressed(body, "planning-ledger"),
    )


def planning_architecture_ledger_is_closed(ledger: PlanningArchitectureLedger) -> bool:
    return (
        bool(ledger.events)
        and tuple(item["sequence"] for item in ledger.events)
        == tuple(range(1, len(ledger.events) + 1))
        and all(item.get("event_address") for item in ledger.events)
    )


def planning_architecture_ledger_summary(
    ledger: PlanningArchitectureLedger,
) -> dict[str, object]:
    return {
        "fixture_id": ledger.fixture_id,
        "event_count": len(ledger.events),
        "closed": planning_architecture_ledger_is_closed(ledger),
        "operation_events": sum(
            item["event_type"] == "operation_declared" for item in ledger.events
        ),
        "case_events": sum(item["event_type"] == "case_executed" for item in ledger.events),
        "last_sequence": ledger.events[-1]["sequence"] if ledger.events else 0,
    }


__all__ = [
    "build_planning_architecture_ledger",
    "planning_architecture_ledger_is_closed",
    "planning_architecture_ledger_summary",
]
