"""Append-only D15 operation and case event ledger."""

from __future__ import annotations

from typing import Any

from .workbench_architecture_contracts import (
    WorkbenchArchitectureEvaluation,
    WorkbenchArchitectureFixture,
    WorkbenchArchitectureLedger,
    addressed,
)
from .workbench_architecture_public_data import default_workbench_architecture_fixture


def build_workbench_architecture_ledger(
    fixture: WorkbenchArchitectureFixture | None = None,
    evaluation: WorkbenchArchitectureEvaluation | None = None,
) -> WorkbenchArchitectureLedger:
    selected = fixture or default_workbench_architecture_fixture()
    events: list[dict[str, Any]] = []
    for operation in selected.operations:
        body = {
            "sequence": len(events) + 1,
            "event_type": "operation_declared",
            "operation_id": operation.operation_id,
            "capability_id": operation.capability_id,
            "family": operation.family,
            "plane": operation.plane,
            "content_address": operation.content_address,
        }
        events.append(
            body | {"event_address": addressed(body, "workbench-architecture-ledger-event")}
        )
    if evaluation is not None:
        for execution in evaluation.executions:
            body = {
                "sequence": len(events) + 1,
                "event_type": "case_executed",
                "case_id": execution.case_id,
                "operation": execution.operation,
                "family": execution.family,
                "scenario": execution.scenario,
                "state": execution.observed_state,
                "issue_codes": execution.observed_issue_codes,
                "output_address": execution.output_address,
            }
            events.append(
                body | {"event_address": addressed(body, "workbench-architecture-ledger-event")}
            )
    body = {"fixture_id": selected.fixture_id, "events": events}
    return WorkbenchArchitectureLedger(
        selected.fixture_id, tuple(events), addressed(body, "workbench-architecture-ledger")
    )


def workbench_architecture_ledger_is_closed(ledger: WorkbenchArchitectureLedger) -> bool:
    return (
        bool(ledger.events)
        and tuple(item["sequence"] for item in ledger.events)
        == tuple(range(1, len(ledger.events) + 1))
        and all(item.get("event_address") for item in ledger.events)
    )


def workbench_architecture_ledger_summary(ledger: WorkbenchArchitectureLedger) -> dict[str, object]:
    return {
        "fixture_id": ledger.fixture_id,
        "event_count": len(ledger.events),
        "closed": workbench_architecture_ledger_is_closed(ledger),
        "operation_events": sum(
            item["event_type"] == "operation_declared" for item in ledger.events
        ),
        "case_events": sum(item["event_type"] == "case_executed" for item in ledger.events),
        "last_sequence": ledger.events[-1]["sequence"] if ledger.events else 0,
    }


__all__ = [
    "build_workbench_architecture_ledger",
    "workbench_architecture_ledger_is_closed",
    "workbench_architecture_ledger_summary",
]
