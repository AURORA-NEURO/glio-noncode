"""Structured operational events for D08 runtime inspection."""

from __future__ import annotations

from typing import Any

from .cell_state_architecture_contracts import (
    CellStateArchitectureEvaluation,
    CellStateArchitectureFixture,
    addressed,
)


def cell_state_architecture_events(
    fixture: CellStateArchitectureFixture, evaluation: CellStateArchitectureEvaluation
) -> tuple[dict[str, Any], ...]:
    events: list[dict[str, Any]] = []
    for index, execution in enumerate(evaluation.executions, start=1):
        event = {
            "event_id": f"d08-event-{index:03d}",
            "fixture_id": fixture.fixture_id,
            "case_id": execution.case_id,
            "operation": execution.operation.value,
            "family": execution.family.value,
            "scenario": execution.scenario.value,
            "state": execution.observed_state.value,
            "result_state": execution.observed_result_state,
            "issue_codes": list(execution.issue_codes),
            "output_address": execution.output_address,
        }
        events.append(event | {"content_address": addressed(event, "cell-state-event")})
    return tuple(events)


def observability_summary(events: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    return {
        "event_count": len(events),
        "accepted_events": sum(item["state"] == "accepted" for item in events),
        "review_events": sum(item["state"] == "review" for item in events),
        "addressed_events": sum(
            str(item.get("content_address", "")).startswith("sha256:") for item in events
        ),
        "issue_codes": sorted({code for item in events for code in item.get("issue_codes", [])}),
    }


__all__ = ["cell_state_architecture_events", "observability_summary"]
