"""Change control receipts for fixture, schema, and threshold revisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from .serialization import content_hash, jsonable


class CohortBetaFrontierChangeClass(StrEnum):
    NON_BREAKING = "non_breaking"
    REVIEW_REQUIRED = "review_required"
    BREAKING = "breaking"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierChangeRequest:
    change_id: str
    component: str
    old_address: str
    new_address: str
    change_class: CohortBetaFrontierChangeClass
    affected_operations: tuple[str, ...]
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierChangeDecision:
    change_id: str
    accepted: bool
    required_actions: tuple[str, ...]
    decision_basis: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierChangeControlReport:
    requests: tuple[CohortBetaFrontierChangeRequest, ...]
    decisions: tuple[CohortBetaFrontierChangeDecision, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_beta_frontier_change_control(requests: Iterable[CohortBetaFrontierChangeRequest]) -> CohortBetaFrontierChangeControlReport:
    values = tuple(requests)
    decisions = []
    for request in values:
        if request.change_class is CohortBetaFrontierChangeClass.NON_BREAKING:
            accepted, actions, basis = True, ("replay", "receipt update"), "non-breaking change has deterministic follow-up"
        elif request.change_class is CohortBetaFrontierChangeClass.REVIEW_REQUIRED:
            accepted, actions, basis = False, ("review queue", "fixture expansion", "replay"), "change can alter interpretation and needs review"
        else:
            accepted, actions, basis = False, ("version bump", "migration", "full validation", "replay"), "breaking change cannot bypass a new contract"
        decisions.append(CohortBetaFrontierChangeDecision(request.change_id, accepted, actions, basis, content_hash({"change_id": request.change_id, "accepted": accepted, "actions": actions}, prefix="change-decision")))
    decisions_tuple = tuple(decisions)
    return CohortBetaFrontierChangeControlReport(values, decisions_tuple, bool(values) and all(item.accepted for item in decisions_tuple), content_hash({"requests": values, "decisions": decisions_tuple}, prefix="change-control"))


def default_cohort_beta_frontier_change_requests() -> tuple[CohortBetaFrontierChangeRequest, ...]:
    raw = (("fixture-receipt-refresh", "public_fixture", "fixture:v1", "fixture:v1", CohortBetaFrontierChangeClass.NON_BREAKING, ("C05", "C06", "C07", "C08"), "refresh public source receipt metadata"), ("threshold-review", "thresholds", "threshold:v1", "threshold:v2", CohortBetaFrontierChangeClass.REVIEW_REQUIRED, ("C05", "C06", "C07", "C08"), "reconsider a default after new calibration evidence"), ("field-removal", "schema", "schema:v1", "schema:v2", CohortBetaFrontierChangeClass.BREAKING, ("C06",), "removing callable-space evidence would change the contract"))
    return tuple(CohortBetaFrontierChangeRequest(change_id, component, old_address, new_address, change_class, operations, rationale, content_hash({"change_id": change_id, "component": component, "old_address": old_address, "new_address": new_address}, prefix="change-request")) for change_id, component, old_address, new_address, change_class, operations, rationale in raw)


__all__ = ["CohortBetaFrontierChangeClass", "CohortBetaFrontierChangeControlReport", "CohortBetaFrontierChangeDecision", "CohortBetaFrontierChangeRequest", "default_cohort_beta_frontier_change_requests", "evaluate_cohort_beta_frontier_change_control"]
