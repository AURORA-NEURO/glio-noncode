"""Explicit lifecycle transitions for a C09-C12 release."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable


class CohortAlphaFrontierLifecycle(StrEnum):
    RECEIVED = "received"
    NORMALIZED = "normalized"
    EVALUATED = "evaluated"
    RECONCILED = "reconciled"
    REVIEWED = "reviewed"
    PACKAGED = "packaged"
    RELEASED = "released"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierTransition:
    order: int
    before: CohortAlphaFrontierLifecycle
    after: CohortAlphaFrontierLifecycle
    gate: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierLifecycleReport:
    transitions: tuple[CohortAlphaFrontierTransition, ...]
    final_state: CohortAlphaFrontierLifecycle
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_lifecycle(accepted: bool = True) -> CohortAlphaFrontierLifecycleReport:
    raw = ((CohortAlphaFrontierLifecycle.RECEIVED, CohortAlphaFrontierLifecycle.NORMALIZED, "normalization"), (CohortAlphaFrontierLifecycle.NORMALIZED, CohortAlphaFrontierLifecycle.EVALUATED, "evaluation"), (CohortAlphaFrontierLifecycle.EVALUATED, CohortAlphaFrontierLifecycle.RECONCILED, "reconciliation"), (CohortAlphaFrontierLifecycle.RECONCILED, CohortAlphaFrontierLifecycle.REVIEWED, "policy"), (CohortAlphaFrontierLifecycle.REVIEWED, CohortAlphaFrontierLifecycle.PACKAGED, "quality"), (CohortAlphaFrontierLifecycle.PACKAGED, CohortAlphaFrontierLifecycle.RELEASED, "manifest"))
    transitions = tuple(CohortAlphaFrontierTransition(index, before, after, gate, accepted, content_hash({"order": index, "before": before, "after": after, "gate": gate, "accepted": accepted}, prefix="alpha-transition")) for index, (before, after, gate) in enumerate(raw, 1))
    return CohortAlphaFrontierLifecycleReport(transitions, transitions[-1].after, accepted and len(transitions) == 6, content_hash(transitions, prefix="alpha-lifecycle"))


__all__ = ["CohortAlphaFrontierLifecycle", "CohortAlphaFrontierLifecycleReport", "CohortAlphaFrontierTransition", "build_cohort_alpha_frontier_lifecycle"]
