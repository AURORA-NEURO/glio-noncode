"""Deterministic query facets over sanitized coordination executions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coordination_architecture_contracts import CoordinationExecution, CoordinationRuntime, CoordinationScenario, CoordinationState, addressed


@dataclass(frozen=True, slots=True)
class CoordinationQueryResult:
    query_id: str
    matched_case_ids: tuple[str, ...]
    matched_count: int
    filters: dict[str, str]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "matched_case_ids": self.matched_case_ids,
            "matched_count": self.matched_count,
            "filters": self.filters,
            "content_address": self.content_address,
        }


def query_coordination(
    runtime: CoordinationRuntime,
    *,
    state: CoordinationState | None = None,
    scenario: CoordinationScenario | None = None,
    operation_id: str | None = None,
    issue_code: str | None = None,
) -> CoordinationQueryResult:
    executions: tuple[CoordinationExecution, ...] = runtime.evaluation.executions
    if state is not None:
        executions = tuple(item for item in executions if item.observed_state is state)
    if scenario is not None:
        executions = tuple(item for item in executions if item.scenario is scenario)
    if operation_id is not None:
        executions = tuple(item for item in executions if item.operation_id == operation_id)
    if issue_code is not None:
        executions = tuple(item for item in executions if issue_code in item.issue_codes)
    filters = {
        key: value.value if hasattr(value, "value") else str(value)
        for key, value in {
            "state": state,
            "scenario": scenario,
            "operation_id": operation_id,
            "issue_code": issue_code,
        }.items()
        if value is not None
    }
    body = {
        "query_id": f"{runtime.run_id}:query:{len(executions)}",
        "matched_case_ids": tuple(item.case_id for item in executions),
        "matched_count": len(executions),
        "filters": filters,
    }
    return CoordinationQueryResult(**body, content_address=addressed(body, "coordination-query"))


__all__ = ["CoordinationQueryResult", "query_coordination"]
