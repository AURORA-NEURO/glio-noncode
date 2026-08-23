"""Ordered operational runbook for executing and holding C05-C08 releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierRunbookStep:
    ordinal: int
    step_id: str
    action: str
    success_condition: str
    failure_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierRunbook:
    steps: tuple[CohortBetaFrontierRunbookStep, ...]
    executable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_runbook() -> CohortBetaFrontierRunbook:
    raw = (("load", "load public aggregate fixture", "fixture audit accepted", "hold release"), ("evaluate", "execute C05-C08 testers", "sixteen rows evaluated", "quarantine failed row"), ("reconcile", "compare expected and observed states", "zero mismatches", "open review item"), ("review", "inspect partial and quarantined paths", "policy disposition recorded", "retain hold"), ("replay", "repeat the same fixture", "content address matches", "hold release"), ("publish", "emit bounded release projections", "release manifest ready", "do not publish"))
    steps = tuple(CohortBetaFrontierRunbookStep(index, step_id, action, success, failure, content_hash({"ordinal": index, "step_id": step_id, "action": action}, prefix="runbook-step")) for index, (step_id, action, success, failure) in enumerate(raw, start=1))
    return CohortBetaFrontierRunbook(steps, len(steps) == 6 and tuple(item.ordinal for item in steps) == tuple(range(1, 7)), content_hash(steps, prefix="runbook"))


__all__ = ["CohortBetaFrontierRunbook", "CohortBetaFrontierRunbookStep", "build_cohort_beta_frontier_runbook"]
