"""Deterministic query index over deployment evaluation rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierQueryHit:
    record_id: str
    operation: str
    state: str
    score: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierQueryResult:
    query: str
    hits: tuple[DeploymentFrontierQueryHit, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def query_deployment_frontier(evaluation: DeploymentFrontierEvaluation, query: str) -> DeploymentFrontierQueryResult:
    term = str(query).strip().lower()
    hits = []
    for execution in evaluation.executions:
        haystack = " ".join((execution.record_id, execution.operation.value, execution.state.value, *execution.issue_codes)).lower()
        if not term or term in haystack:
            body = {"record_id": execution.record_id, "operation": execution.operation.value, "state": execution.state.value, "score": 100 if term and term in execution.record_id.lower() else 50}
            hits.append(DeploymentFrontierQueryHit(**body, content_address=deployment_address(body)))
    hits.sort(key=lambda item: (-item.score, item.record_id))
    return DeploymentFrontierQueryResult(query, tuple(hits), deployment_address(tuple(hits)))


__all__ = ["DeploymentFrontierQueryHit", "DeploymentFrontierQueryResult", "query_deployment_frontier"]
