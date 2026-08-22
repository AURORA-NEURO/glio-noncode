"""Fixture evaluation facade with deterministic operation summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_adapters import CausalAlphaFrontierEvaluation, evaluate_causal_alpha_frontier_fixture
from .causal_alpha_frontier_public_data import CausalAlphaFrontierOperation
from .causal_reasoning import CausalState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierOperationSummary:
    """Counts and state surface for one operation."""

    operation: CausalAlphaFrontierOperation
    record_count: int
    accepted_count: int
    states: dict[str, int]
    issue_codes: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"operation": self.operation, "record_count": self.record_count, "accepted_count": self.accepted_count, "states": dict(self.states), "issue_codes": self.issue_codes, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierFixtureEvaluation:
    """Evaluation plus operation-level closure summaries."""

    evaluation: CausalAlphaFrontierEvaluation
    summaries: tuple[CausalAlphaFrontierOperationSummary, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def summary(self, operation: CausalAlphaFrontierOperation | str) -> CausalAlphaFrontierOperationSummary:
        value = CausalAlphaFrontierOperation(str(operation))
        return next(item for item in self.summaries if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"evaluation": self.evaluation.to_dict(), "summaries": [item.to_dict() for item in self.summaries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_causal_alpha_frontier_fixture_deep(fixture: Any) -> CausalAlphaFrontierFixtureEvaluation:
    evaluation = evaluate_causal_alpha_frontier_fixture(fixture)
    summaries: list[CausalAlphaFrontierOperationSummary] = []
    for operation in CausalAlphaFrontierOperation:
        rows = evaluation.for_operation(operation)
        states: dict[str, int] = {}
        codes: set[str] = set()
        for row in rows:
            key = row.observed_state.value
            states[key] = states.get(key, 0) + 1
            codes.update(row.observed_issue_codes)
        summaries.append(CausalAlphaFrontierOperationSummary(operation, len(rows), sum(item.accepted for item in rows), dict(sorted(states.items())), tuple(sorted(codes)), all(item.accepted for item in rows)))
    accepted = bool(evaluation.accepted and len(summaries) == len(tuple(CausalAlphaFrontierOperation)) and all(item.accepted for item in summaries))
    return CausalAlphaFrontierFixtureEvaluation(evaluation, tuple(summaries), accepted)


__all__ = ["CausalAlphaFrontierFixtureEvaluation", "CausalAlphaFrontierOperationSummary", "evaluate_causal_alpha_frontier_fixture_deep"]
