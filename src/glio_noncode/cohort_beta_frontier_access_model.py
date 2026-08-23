"""Field-level access model for public summaries, reviews, and operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping

from .cohort_beta_frontier_policy import CohortBetaFrontierDisposition
from .cohort_beta_frontier_publication import CohortBetaFrontierArtifactAudience
from .serialization import content_hash, jsonable


class CohortBetaFrontierAccessState(StrEnum):
    ALLOW = "allow"
    MASK = "mask"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierAccessRole:
    role_id: str
    title: str
    audience: CohortBetaFrontierArtifactAudience
    allowed_dispositions: tuple[str, ...]
    allowed_fields: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierAccessRequest:
    request_id: str
    role_id: str
    field_name: str
    disposition: CohortBetaFrontierDisposition
    record_id: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierAccessDecision:
    request_id: str
    decision: CohortBetaFrontierAccessState
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierAccessReport:
    roles: tuple[CohortBetaFrontierAccessRole, ...]
    decisions: tuple[CohortBetaFrontierAccessDecision, ...]
    allow_count: int
    mask_count: int
    deny_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_access_roles() -> tuple[CohortBetaFrontierAccessRole, ...]:
    raw = (("research-review", "research reviewer", CohortBetaFrontierArtifactAudience.RESEARCH_REVIEW, ("publish", "review", "quarantine"), ("operation", "record_id", "state", "disposition", "source_receipts", "content_address")), ("public-summary", "public summary reader", CohortBetaFrontierArtifactAudience.PUBLIC_SUMMARY, ("publish",), ("operation", "state", "source_receipts", "content_address")), ("operations", "release operator", CohortBetaFrontierArtifactAudience.OPERATIONS, ("publish", "review", "quarantine"), ("operation", "record_id", "state", "disposition", "content_address")))
    return tuple(CohortBetaFrontierAccessRole(role_id, title, audience, dispositions, fields, content_hash({"role_id": role_id, "audience": audience, "fields": fields}, prefix="access-role")) for role_id, title, audience, dispositions, fields in raw)


def _decision(request: CohortBetaFrontierAccessRequest, role: CohortBetaFrontierAccessRole) -> CohortBetaFrontierAccessDecision:
    if request.disposition.value not in role.allowed_dispositions:
        selected, reason = CohortBetaFrontierAccessState.DENY, "role cannot access this policy disposition"
    elif request.field_name in role.allowed_fields:
        selected, reason = CohortBetaFrontierAccessState.ALLOW, "role and field policy match"
    elif request.field_name == "record_id" and role.audience is CohortBetaFrontierArtifactAudience.PUBLIC_SUMMARY:
        selected, reason = CohortBetaFrontierAccessState.MASK, "pseudonymous row key is masked in public summaries"
    else:
        selected, reason = CohortBetaFrontierAccessState.DENY, "field is outside the role projection"
    body = {"request_id": request.request_id, "decision": selected, "reason": reason}
    return CohortBetaFrontierAccessDecision(request.request_id, selected, reason, content_hash(body, prefix="access-decision"))


def evaluate_cohort_beta_frontier_access(requests: Iterable[CohortBetaFrontierAccessRequest], roles: Iterable[CohortBetaFrontierAccessRole] | None = None) -> CohortBetaFrontierAccessReport:
    selected_roles = tuple(roles or default_cohort_beta_frontier_access_roles())
    by_id = {role.role_id: role for role in selected_roles}
    decisions = []
    for request in requests:
        role = by_id.get(request.role_id)
        if role is None:
            decisions.append(CohortBetaFrontierAccessDecision(request.request_id, CohortBetaFrontierAccessState.DENY, "unknown role", content_hash(request.request_id, prefix="access-decision")))
        else:
            decisions.append(_decision(request, role))
    values = tuple(decisions)
    return CohortBetaFrontierAccessReport(selected_roles, values, sum(item.decision is CohortBetaFrontierAccessState.ALLOW for item in values), sum(item.decision is CohortBetaFrontierAccessState.MASK for item in values), sum(item.decision is CohortBetaFrontierAccessState.DENY for item in values), all(item.decision is not CohortBetaFrontierAccessState.DENY for item in values), content_hash({"roles": selected_roles, "decisions": values}, prefix="access-report"))


def default_cohort_beta_frontier_access_requests(record_id: str = "c05-positive") -> tuple[CohortBetaFrontierAccessRequest, ...]:
    raw = (("request-public-state", "public-summary", "state", CohortBetaFrontierDisposition.PUBLISH), ("request-public-row", "public-summary", "record_id", CohortBetaFrontierDisposition.PUBLISH), ("request-review-source", "research-review", "source_receipts", CohortBetaFrontierDisposition.REVIEW), ("request-operator-disposition", "operations", "disposition", CohortBetaFrontierDisposition.QUARANTINE), ("request-unknown-field", "public-summary", "prohibited_claims", CohortBetaFrontierDisposition.PUBLISH))
    return tuple(CohortBetaFrontierAccessRequest(request_id, role_id, field_name, disposition, record_id, content_hash({"request_id": request_id, "role_id": role_id, "field_name": field_name}, prefix="access-request")) for request_id, role_id, field_name, disposition in raw)


__all__ = ["CohortBetaFrontierAccessDecision", "CohortBetaFrontierAccessReport", "CohortBetaFrontierAccessRequest", "CohortBetaFrontierAccessRole", "CohortBetaFrontierAccessState", "default_cohort_beta_frontier_access_requests", "default_cohort_beta_frontier_access_roles", "evaluate_cohort_beta_frontier_access"]
