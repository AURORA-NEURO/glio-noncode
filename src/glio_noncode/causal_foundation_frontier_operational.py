"""Operational matrix for repeatable C01-C04 review and release checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_policy import CausalFoundationFrontierPolicy, default_causal_foundation_frontier_policy
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierOperationalCell:
    cell_id: str
    operation: str
    role: str
    state: str
    decision: str
    issue_codes: tuple[str, ...]
    action: str
    release_effect: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def blocking(self) -> bool:
        return self.release_effect in {"blocked", "review"}

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cell_id": self.cell_id, "operation": self.operation, "role": self.role, "state": self.state, "decision": self.decision, "issue_codes": self.issue_codes, "action": self.action, "release_effect": self.release_effect, "blocking": self.blocking}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierOperationalMatrix:
    fixture_id: str
    dimensions: tuple[str, ...]
    cells: tuple[CausalFoundationFrontierOperationalCell, ...]
    retain_count: int
    review_count: int
    blocked_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[CausalFoundationFrontierOperationalCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def for_state(self, state: str) -> tuple[CausalFoundationFrontierOperationalCell, ...]:
        return tuple(item for item in self.cells if item.state == state)

    def for_effect(self, effect: str) -> tuple[CausalFoundationFrontierOperationalCell, ...]:
        return tuple(item for item in self.cells if item.release_effect == effect)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "dimensions": self.dimensions, "cells": [item.to_dict() for item in self.cells], "retain_count": self.retain_count, "review_count": self.review_count, "blocked_count": self.blocked_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _action(decision: str, state: str) -> tuple[str, str]:
    if decision == "retain":
        return "attach receipt and publish to aggregate review", "retained"
    if decision == "quarantine":
        return "preserve evidence and prevent release", "blocked"
    if decision == "abstain":
        return "request missing evidence before completion", "review"
    if state == "partial":
        return "inspect lineage or measurement coverage", "review"
    return "route to bounded review", "review"


def build_causal_foundation_frontier_operational_matrix(fixture: CausalFoundationFrontierFixture, evaluation: CausalFoundationFrontierEvaluation, policy: CausalFoundationFrontierPolicy | None = None) -> CausalFoundationFrontierOperationalMatrix:
    active = policy or default_causal_foundation_frontier_policy()
    cells: list[CausalFoundationFrontierOperationalCell] = []
    for decision in active.decide(evaluation):
        action, effect = _action(decision.decision.value, decision.state)
        cells.append(CausalFoundationFrontierOperationalCell(f"op:{decision.record_id}", decision.operation, decision.role, decision.state, decision.decision.value, decision.issue_codes, action, effect))
    values = tuple(cells)
    return CausalFoundationFrontierOperationalMatrix(fixture.fixture_id, ("operation", "role", "state", "decision", "issue_codes", "action", "release_effect"), values, sum(item.release_effect == "retained" for item in values), sum(item.release_effect == "review" for item in values), sum(item.release_effect == "blocked" for item in values), bool(values) and len(values) == len(fixture.records) and len({item.cell_id for item in values}) == len(values))


__all__ = ["CausalFoundationFrontierOperationalCell", "CausalFoundationFrontierOperationalMatrix", "build_causal_foundation_frontier_operational_matrix"]
