"""Append-only D16 operation and execution ledger."""

from __future__ import annotations

from typing import Any

from .platform_execution_architecture_contracts import (
    PlatformExecutionEvaluation,
    PlatformExecutionFixture,
    PlatformExecutionLedger,
    addressed,
)
from .platform_execution_architecture_public_data import default_platform_execution_fixture


def build_platform_execution_ledger(
    fixture: PlatformExecutionFixture | None = None,
    evaluation: PlatformExecutionEvaluation | None = None,
) -> PlatformExecutionLedger:
    selected = fixture or default_platform_execution_fixture()
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
        events.append(body | {"event_address": addressed(body, "platform-execution-ledger-event")})
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
                body | {"event_address": addressed(body, "platform-execution-ledger-event")}
            )
    body = {"fixture_id": selected.fixture_id, "events": events}
    return PlatformExecutionLedger(
        selected.fixture_id, tuple(events), addressed(body, "platform-execution-ledger")
    )


def platform_execution_ledger_is_closed(ledger: PlatformExecutionLedger) -> bool:
    return (
        bool(ledger.events)
        and tuple(item["sequence"] for item in ledger.events)
        == tuple(range(1, len(ledger.events) + 1))
        and all(item.get("event_address") for item in ledger.events)
    )


__all__ = ["build_platform_execution_ledger", "platform_execution_ledger_is_closed"]
