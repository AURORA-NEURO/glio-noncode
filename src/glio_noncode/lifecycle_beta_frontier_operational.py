"""Operational matrix connecting states to review actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierOperationalRow:
    record_id: str
    state: LifecycleBetaFrontierState
    action: str
    owner_roles: tuple[str, ...]
    blocking: bool
    issue_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierOperationalMatrix:
    rows: tuple[LifecycleBetaFrontierOperationalRow, ...]
    blocking_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_operational_matrix(evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierOperationalMatrix:
    actions = {LifecycleBetaFrontierState.SUPPORTED: "retain", LifecycleBetaFrontierState.READY_FOR_REVIEW: "review", LifecycleBetaFrontierState.ADJUDICATED: "review", LifecycleBetaFrontierState.APPROVED: "record_research_release", LifecycleBetaFrontierState.REVIEW_REQUIRED: "hold", LifecycleBetaFrontierState.PARTIAL: "quarantine", LifecycleBetaFrontierState.CONTRADICTORY: "resolve_disagreement", LifecycleBetaFrontierState.OUT_OF_DOMAIN: "exclude_context", LifecycleBetaFrontierState.ABSTAINED: "request_input", LifecycleBetaFrontierState.SPLIT_DECISION: "escalate", LifecycleBetaFrontierState.REJECTED: "retain_rejection"}
    rows = []
    for item in evaluation.executions:
        blocking = item.state not in {LifecycleBetaFrontierState.SUPPORTED, LifecycleBetaFrontierState.READY_FOR_REVIEW, LifecycleBetaFrontierState.ADJUDICATED, LifecycleBetaFrontierState.APPROVED}
        body = {"record_id": item.record_id, "state": item.state, "action": actions[item.state], "owner_roles": ("domain_expert", "data_provenance") if blocking else ("data_provenance",), "blocking": blocking, "issue_count": len(item.issue_codes)}
        rows.append(LifecycleBetaFrontierOperationalRow(**body, content_address=content_hash(body)))
    return LifecycleBetaFrontierOperationalMatrix(tuple(rows), sum(item.blocking for item in rows), content_hash({"rows": tuple(rows)}))


__all__ = ["LifecycleBetaFrontierOperationalMatrix", "LifecycleBetaFrontierOperationalRow", "build_lifecycle_beta_frontier_operational_matrix"]
