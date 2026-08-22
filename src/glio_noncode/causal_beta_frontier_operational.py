"""Operational readiness matrix for bounded C05-C08 use."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_bundle import CausalBetaFrontierReleaseBundle
from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_policy import CausalBetaFrontierPolicyDecision
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .causal_beta_frontier_review import CausalBetaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierOperationalCell:
    cell_id: str
    operation: str
    scenario: str
    state: str
    decision: str
    action: str
    expected_effect: str
    release_allowed: bool
    review_required: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cell_id": self.cell_id, "operation": self.operation, "scenario": self.scenario, "state": self.state, "decision": self.decision, "action": self.action, "expected_effect": self.expected_effect, "release_allowed": self.release_allowed, "review_required": self.review_required}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierOperationalMatrix:
    fixture_id: str
    cells: tuple[CausalBetaFrontierOperationalCell, ...]
    allowed_count: int
    review_count: int
    blocked_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[CausalBetaFrontierOperationalCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def for_scenario(self, scenario: str) -> tuple[CausalBetaFrontierOperationalCell, ...]:
        return tuple(item for item in self.cells if item.scenario == scenario)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cells": [item.to_dict() for item in self.cells], "cell_count": len(self.cells), "allowed_count": self.allowed_count, "review_count": self.review_count, "blocked_count": self.blocked_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _scenario(row_state: str, issue_codes: tuple[str, ...]) -> str:
    if row_state == "supported":
        return "positive"
    if row_state in {"contradictory", "ambiguous"}:
        return "conflict_or_ambiguity"
    if row_state == "out_of_domain":
        return "foreign_context"
    return "minimum_or_missing"


def _cell_action(decision: CausalBetaFrontierPolicyDecision) -> tuple[str, str, bool, bool]:
    value = decision.decision.value
    if value == "retain":
        return "retain_for_bounded_analysis", "retain positive receipt", True, False
    if value == "review":
        return "route_to_review", "hold until missing evidence is resolved", False, True
    if value == "abstain":
        return "abstain_from_claim", "do not infer state without alternate support", False, True
    return "quarantine", "exclude from downstream claim", False, True


def build_causal_beta_frontier_operational_matrix(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation, decisions: tuple[CausalBetaFrontierPolicyDecision, ...], review: CausalBetaFrontierReviewQueue, bundle: CausalBetaFrontierReleaseBundle) -> CausalBetaFrontierOperationalMatrix:
    evaluation_map = {item.record_id: item for item in evaluation.rows}
    review_map = {item.record_id: item for item in review.items}
    cells: list[CausalBetaFrontierOperationalCell] = []
    for decision in decisions:
        row = evaluation_map[decision.record_id]
        action, effect, allowed, review_required = _cell_action(decision)
        review_item = review_map[decision.record_id]
        cells.append(CausalBetaFrontierOperationalCell(f"cell:{decision.record_id}", row.operation, _scenario(row.observed_state, row.observed_issue_codes), row.observed_state, decision.decision.value, action, effect, allowed and bundle.publishable, review_required or review_item.blocking))
    values = tuple(cells)
    accepted = bool(values) and len(values) == len(fixture.records) and all(item.operation and item.action for item in values)
    return CausalBetaFrontierOperationalMatrix(fixture.fixture_id, values, sum(item.release_allowed for item in values), sum(item.review_required and not item.decision == "quarantine" for item in values), sum(item.decision == "quarantine" for item in values), accepted)


__all__ = ["CausalBetaFrontierOperationalCell", "CausalBetaFrontierOperationalMatrix", "build_causal_beta_frontier_operational_matrix"]
