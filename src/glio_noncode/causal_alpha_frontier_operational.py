"""Operational action matrix with explicit allow/review/quarantine cells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_policy import CausalAlphaFrontierDecision, CausalAlphaFrontierDisposition
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .causal_alpha_frontier_review import CausalAlphaFrontierReviewQueue
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierOperationalCell:
    record_id: str
    operation: str
    disposition: CausalAlphaFrontierDisposition
    action: str
    blocking: bool
    reason: str
    owner_scope: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "disposition": self.disposition, "action": self.action, "blocking": self.blocking, "reason": self.reason, "owner_scope": self.owner_scope}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierOperationalMatrix:
    fixture_id: str
    cells: tuple[CausalAlphaFrontierOperationalCell, ...]
    allowed_count: int
    review_count: int
    quarantine_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cells": [item.to_dict() for item in self.cells], "allowed_count": self.allowed_count, "review_count": self.review_count, "quarantine_count": self.quarantine_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_operational_matrix(fixture: CausalAlphaFrontierFixture, decisions: tuple[CausalAlphaFrontierDecision, ...], review: CausalAlphaFrontierReviewQueue) -> CausalAlphaFrontierOperationalMatrix:
    cells: list[CausalAlphaFrontierOperationalCell] = []
    for decision in decisions:
        if decision.disposition is CausalAlphaFrontierDisposition.ALLOW_DESCRIPTIVE:
            action, blocking, scope = "allow descriptive export", False, "descriptive review"
        elif decision.disposition is CausalAlphaFrontierDisposition.QUARANTINE:
            action, blocking, scope = "quarantine and reconcile context", True, "exact-context review"
        elif decision.disposition is CausalAlphaFrontierDisposition.REVIEW:
            action, blocking, scope = "route to evidence review", False, "scientific review"
        else:
            action, blocking, scope = "retain abstention", True, "evidence review"
        cells.append(CausalAlphaFrontierOperationalCell(decision.record_id, decision.operation.value, decision.disposition, action, blocking, decision.reason, scope))
    allowed = sum(item.disposition is CausalAlphaFrontierDisposition.ALLOW_DESCRIPTIVE for item in cells)
    review_count = sum(item.disposition is CausalAlphaFrontierDisposition.REVIEW for item in cells)
    quarantine = sum(item.disposition is CausalAlphaFrontierDisposition.QUARANTINE for item in cells)
    return CausalAlphaFrontierOperationalMatrix(fixture.fixture_id, tuple(cells), allowed, review_count, quarantine, len(cells) == 16 and review.accepted and quarantine == 4)


__all__ = ["CausalAlphaFrontierOperationalCell", "CausalAlphaFrontierOperationalMatrix", "build_causal_alpha_frontier_operational_matrix"]
