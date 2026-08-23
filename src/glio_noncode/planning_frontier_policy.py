"""Disposition policy that keeps planning artifacts review bounded."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation, PlanningState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningPolicy:
    dispositions: tuple[dict[str, Any], ...]
    publishable_count: int
    held_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def materialize_planning_policy(evaluation: PlanningEvaluation) -> PlanningPolicy:
    dispositions = []
    for item in evaluation.executions:
        publishable = item.observed_state is PlanningState.READY_FOR_REVIEW
        dispositions.append({"record_id": item.record_id, "disposition": "review_release" if publishable else "held_for_review", "publishable": publishable, "issue_codes": item.issue_codes})
    publishable = sum(bool(item["publishable"]) for item in dispositions)
    held = len(dispositions) - publishable
    body = {"dispositions": tuple(dispositions), "publishable_count": publishable, "held_count": held, "accepted": all(item["disposition"] for item in dispositions)}
    return PlanningPolicy(tuple(dispositions), publishable, held, body["accepted"], content_hash(body, prefix="planning-policy"))


__all__ = ["PlanningPolicy", "materialize_planning_policy"]
