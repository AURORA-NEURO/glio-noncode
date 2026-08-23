"""Governance projections for planning review and bounded release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture, PlanningState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningClaimBoundary:
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningControlCoverage:
    operation_counts: dict[str, int]
    role_counts: dict[str, int]
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningScenarioMatrix:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningArtifactInventory:
    artifacts: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningOperationalMatrix:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_claim_boundary() -> PlanningClaimBoundary:
    allowed = (
        "public aggregate evidence organization",
        "context-aware research planning",
        "deterministic review queue construction",
        "transparent assumption and shortfall reporting",
    )
    excluded = (
        "individual-level inference",
        "model fidelity proof",
        "guide efficacy proof",
        "assay validity proof",
        "safety or clinical conclusion",
        "institutional approval",
    )
    body = {"allowed_uses": allowed, "excluded_uses": excluded, "accepted": bool(allowed and excluded)}
    return PlanningClaimBoundary(allowed, excluded, body["accepted"], content_hash(body, prefix="planning-claim-boundary"))


def build_planning_control_coverage(evaluation: PlanningEvaluation) -> PlanningControlCoverage:
    operation_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    state_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    for item in evaluation.executions:
        operation_counts[item.operation.value] = operation_counts.get(item.operation.value, 0) + 1
        role_counts[item.role.value] = role_counts.get(item.role.value, 0) + 1
        state_counts[item.observed_state.value] = state_counts.get(item.observed_state.value, 0) + 1
        for issue in item.issue_codes:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    accepted = sorted(operation_counts.values()) == [4, 4, 4, 4] and role_counts == {"positive": 4, "control": 12}
    body = {"operation_counts": operation_counts, "role_counts": role_counts, "state_counts": state_counts, "issue_counts": issue_counts, "accepted": accepted}
    return PlanningControlCoverage(operation_counts, role_counts, state_counts, issue_counts, accepted, content_hash(body, prefix="planning-control-coverage"))


def build_planning_scenario_matrix(fixture: PlanningFixture, evaluation: PlanningEvaluation) -> PlanningScenarioMatrix:
    rows = tuple({
        "scenario_id": item.record_id,
        "operation": item.operation.value,
        "role": item.role.value,
        "expected_state": item.expected_state.value,
        "observed_state": item.observed_state.value,
        "issue_codes": item.issue_codes,
        "source_ids": fixture.records[index].source_ids,
    } for index, item in enumerate(evaluation.executions))
    accepted = len(rows) == len(fixture.records) and all(row["scenario_id"] for row in rows)
    body = {"rows": rows, "accepted": accepted}
    return PlanningScenarioMatrix(rows, accepted, content_hash(body, prefix="planning-scenario-matrix"))


def build_planning_artifact_inventory(fixture: PlanningFixture, evaluation: PlanningEvaluation) -> PlanningArtifactInventory:
    artifacts = (
        {"artifact_id": "fixture", "kind": "public-aggregate-fixture", "content_address": fixture.content_address},
        {"artifact_id": "evaluation", "kind": "scenario-evaluation", "content_address": evaluation.content_address},
        *tuple({"artifact_id": item.record_id, "kind": "execution", "content_address": item.content_address} for item in evaluation.executions),
        *tuple({"artifact_id": item.check_id, "kind": "check", "content_address": item.content_address} for item in evaluation.checks),
    )
    accepted = bool(artifacts) and all(":" in str(item["content_address"]) for item in artifacts)
    body = {"artifacts": artifacts, "accepted": accepted}
    return PlanningArtifactInventory(artifacts, accepted, content_hash(body, prefix="planning-artifacts"))


def build_planning_operational_matrix(evaluation: PlanningEvaluation) -> PlanningOperationalMatrix:
    rows = tuple({
        "record_id": item.record_id,
        "state": item.observed_state.value,
        "consumer_disposition": "review_release" if item.observed_state is PlanningState.READY_FOR_REVIEW else "held_for_review",
        "requires_human_review": item.observed_state is not PlanningState.READY_FOR_REVIEW,
        "issue_count": len(item.issue_codes),
    } for item in evaluation.executions)
    accepted = len(rows) == 16 and all("consumer_disposition" in row for row in rows)
    body = {"rows": rows, "accepted": accepted}
    return PlanningOperationalMatrix(rows, accepted, content_hash(body, prefix="planning-operational-matrix"))


__all__ = [
    "PlanningArtifactInventory",
    "PlanningClaimBoundary",
    "PlanningControlCoverage",
    "PlanningOperationalMatrix",
    "PlanningScenarioMatrix",
    "build_planning_artifact_inventory",
    "build_planning_claim_boundary",
    "build_planning_control_coverage",
    "build_planning_operational_matrix",
    "build_planning_scenario_matrix",
]
