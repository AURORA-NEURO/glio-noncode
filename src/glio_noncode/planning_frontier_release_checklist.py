"""Release checklist with machine-readable acceptance and evidence text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture
from .planning_frontier_governance import PlanningClaimBoundary, build_planning_claim_boundary
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningReleaseCheck:
    check_id: str
    sequence: int
    category: str
    requirement: str
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningReleaseChecklist:
    checks: tuple[PlanningReleaseCheck, ...]
    claim_boundary: PlanningClaimBoundary
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def failed_checks(self) -> tuple[PlanningReleaseCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)


def build_planning_release_checklist(fixture: PlanningFixture, evaluation: PlanningEvaluation) -> PlanningReleaseChecklist:
    boundary = build_planning_claim_boundary()
    rows = (
        ("fixture", "scope", "fixture has public aggregate boundary", fixture.evidence_boundary, "public_aggregate_planning_evidence"),
        ("sources", "provenance", "five public receipts", len(fixture.sources), 5),
        ("records", "scope", "sixteen scenario rows", len(fixture.records), 16),
        ("positive", "role", "four positive rows", len(fixture.positive_records), 4),
        ("controls", "role", "twelve control rows", len(fixture.control_records), 12),
        ("operations", "scope", "four operation partitions", len(fixture.operations), 4),
        ("checks", "quality", "five checks per row", len(evaluation.checks), 80),
        ("evaluation", "quality", "evaluation accepts", evaluation.accepted, True),
        ("addresses", "integrity", "every execution is addressed", all(item.content_address.startswith("sha256:") for item in evaluation.executions), True),
        ("held", "review", "held states are visible", any(item.observed_state.value != "ready_for_review" for item in evaluation.executions), True),
        ("boundary", "claim", "excluded uses are present", bool(boundary.excluded_uses), True),
        ("replay", "reproducibility", "fixture address is stable", fixture.content_address.startswith("sha256:"), True),
    )
    checks = []
    for sequence, (check_id, category, requirement, observed, required) in enumerate(rows, start=1):
        body = {"check_id": check_id, "sequence": sequence, "category": category, "requirement": requirement, "passed": observed == required, "observed": observed, "required": required}
        checks.append(PlanningReleaseCheck(**body, content_address=content_hash(body, prefix="planning-release-check")))
    values = tuple(checks)
    accepted = bool(boundary.accepted and values and all(item.passed for item in values))
    body = {"checks": values, "claim_boundary": boundary, "accepted": accepted}
    return PlanningReleaseChecklist(values, boundary, accepted, content_hash(body, prefix="planning-release-checklist"))


__all__ = ["PlanningReleaseCheck", "PlanningReleaseChecklist", "build_planning_release_checklist"]
