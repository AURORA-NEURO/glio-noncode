"""Redacted, deterministic queries over platform evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierOperation, PlatformFrontierRole, PlatformFrontierState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierQuery:
    operation: PlatformFrontierOperation | None = None
    role: PlatformFrontierRole | None = None
    states: tuple[PlatformFrontierState, ...] = ()
    issue_code: str | None = None
    accepted: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierQueryHit:
    record_id: str
    operation: PlatformFrontierOperation
    role: PlatformFrontierRole
    state: PlatformFrontierState
    accepted: bool
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierQueryResult:
    fixture_id: str
    query: PlatformFrontierQuery
    hits: tuple[PlatformFrontierQueryHit, ...]
    total_matches: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def query_platform_frontier_evaluation(evaluation: PlatformFrontierEvaluation, query: PlatformFrontierQuery | None = None) -> PlatformFrontierQueryResult:
    query = query or PlatformFrontierQuery()
    states = set(query.states)
    hits = []
    for row in evaluation.executions:
        if query.operation is not None and row.operation is not query.operation:
            continue
        if query.role is not None and row.role is not query.role:
            continue
        if states and row.state not in states:
            continue
        if query.issue_code is not None and query.issue_code not in row.issue_codes:
            continue
        if query.accepted is not None and row.accepted is not query.accepted:
            continue
        body = {"record_id": row.record_id, "operation": row.operation, "role": row.role, "state": row.state, "accepted": row.accepted, "issue_codes": row.issue_codes}
        hits.append(PlatformFrontierQueryHit(**body, content_address=content_hash(body)))
    body = {"fixture_id": evaluation.fixture_id, "query": query, "hits": tuple(hits), "total_matches": len(hits), "accepted": all(item.content_address.startswith("sha256:") for item in hits)}
    return PlatformFrontierQueryResult(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierQuery", "PlatformFrontierQueryHit", "PlatformFrontierQueryResult", "query_platform_frontier_evaluation"]
