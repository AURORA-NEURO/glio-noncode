"""Stable query projections over control frontier evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierOperation, ControlFrontierRole, ControlFrontierState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierQuery:
    """Optional filters for a bounded evaluation query."""

    operation: ControlFrontierOperation | None = None
    role: ControlFrontierRole | None = None
    states: tuple[ControlFrontierState, ...] = ()
    issue_code: str | None = None
    accepted: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierQueryHit:
    """Redacted row projection returned from a query."""

    record_id: str
    operation: ControlFrontierOperation
    role: ControlFrontierRole
    state: ControlFrontierState
    accepted: bool
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierQueryResult:
    """Deterministic query envelope with stable hit ordering."""

    fixture_id: str
    query: ControlFrontierQuery
    hits: tuple[ControlFrontierQueryHit, ...]
    total_matches: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def query_control_frontier_evaluation(evaluation: ControlFrontierEvaluation, query: ControlFrontierQuery | None = None) -> ControlFrontierQueryResult:
    """Filter executions without exposing operation payloads."""

    query = query or ControlFrontierQuery()
    state_values = set(query.states)
    hits = []
    for execution in evaluation.executions:
        if query.operation is not None and execution.operation is not query.operation:
            continue
        if query.role is not None and execution.role is not query.role:
            continue
        if state_values and execution.state not in state_values:
            continue
        if query.issue_code is not None and query.issue_code not in execution.issue_codes:
            continue
        if query.accepted is not None and execution.accepted is not query.accepted:
            continue
        body = {
            "record_id": execution.record_id,
            "operation": execution.operation,
            "role": execution.role,
            "state": execution.state,
            "accepted": execution.accepted,
            "issue_codes": execution.issue_codes,
        }
        hits.append(ControlFrontierQueryHit(**body, content_address=content_hash(body)))
    body = {
        "fixture_id": evaluation.fixture_id,
        "query": query,
        "hits": tuple(hits),
        "total_matches": len(hits),
        "accepted": all(item.content_address.startswith("sha256:") for item in hits),
    }
    return ControlFrontierQueryResult(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierQuery", "ControlFrontierQueryHit", "ControlFrontierQueryResult", "query_control_frontier_evaluation"]
