"""Text and structure checks that keep the planning boundary explicit."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture
from .serialization import content_hash, jsonable


FORBIDDEN_CLAIM_TERMS = (
    "proven",
    "guaranteed",
    "clinical",
    "patient-specific",
    "approved",
    "efficacious",
    "causal",
)


@dataclass(frozen=True, slots=True)
class PlanningBoundaryFinding:
    finding_id: str
    scope: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningBoundaryReport:
    findings: tuple[PlanningBoundaryFinding, ...]
    forbidden_terms_found: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _finding(finding_id: str, scope: str, passed: bool, observed: Any, required: Any, detail: str) -> PlanningBoundaryFinding:
    body = {"finding_id": finding_id, "scope": scope, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return PlanningBoundaryFinding(**body, content_address=content_hash(body, prefix="planning-boundary-finding"))


def audit_planning_boundary(fixture: PlanningFixture, evaluation: PlanningEvaluation) -> PlanningBoundaryReport:
    serialized = str({"fixture": fixture.to_dict(), "evaluation": evaluation.to_dict()}).lower()
    words = set(re.findall(r"[a-z]+", serialized))
    found = tuple(term for term in FORBIDDEN_CLAIM_TERMS if term in words)
    findings = (
        _finding("aggregate-scope", "fixture", fixture.evidence_boundary == "public_aggregate_planning_evidence", fixture.evidence_boundary, "public_aggregate_planning_evidence", "fixture boundary is aggregate"),
        _finding("state-boundary", "evaluation", all(item.observed_state.value in {"ready_for_review", "review", "blocked", "rejected", "abstained"} for item in evaluation.executions), "enumerated", "enumerated", "states are bounded"),
        _finding("held-boundary", "evaluation", any(item.observed_state.value == "blocked" for item in evaluation.executions), True, True, "foreign contexts remain held"),
        _finding("no-private-output", "evaluation", all("patient_id" not in str(item.output).lower() for item in evaluation.executions), True, True, "private marker check"),
        _finding("non-claim-language", "package", not any(term in serialized for term in ("patient-specific", "efficacious", "approved")), found, (), "release language remains bounded"),
    )
    accepted = not found and all(item.passed for item in findings)
    body = {"findings": findings, "forbidden_terms_found": found, "accepted": accepted}
    return PlanningBoundaryReport(findings, found, accepted, content_hash(body, prefix="planning-boundary"))


__all__ = ["FORBIDDEN_CLAIM_TERMS", "PlanningBoundaryFinding", "PlanningBoundaryReport", "audit_planning_boundary"]
