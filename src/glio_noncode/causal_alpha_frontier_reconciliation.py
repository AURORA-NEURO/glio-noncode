"""Expected-state and observed-state reconciliation for fixture release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_adapters import CausalAlphaFrontierEvaluation
from .causal_alpha_frontier_policy import CausalAlphaFrontierDecision
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierReconciliation:
    fixture_id: str
    expected_count: int
    observed_count: int
    matched_count: int
    mismatched_record_ids: tuple[str, ...]
    disposition_counts: dict[str, int]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def match_fraction(self) -> float:
        return round(self.matched_count / max(1, self.expected_count), 6)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "expected_count": self.expected_count, "observed_count": self.observed_count, "matched_count": self.matched_count, "match_fraction": self.match_fraction, "mismatched_record_ids": self.mismatched_record_ids, "disposition_counts": dict(self.disposition_counts), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def reconcile_causal_alpha_frontier(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierEvaluation, decisions: tuple[CausalAlphaFrontierDecision, ...]) -> CausalAlphaFrontierReconciliation:
    mismatches = tuple(item.record_id for item in evaluation.evaluation.results if not item.accepted)
    dispositions: dict[str, int] = {}
    for item in decisions:
        dispositions[item.disposition.value] = dispositions.get(item.disposition.value, 0) + 1
    return CausalAlphaFrontierReconciliation(fixture.fixture_id, len(fixture.records), len(evaluation.evaluation.results), len(fixture.records) - len(mismatches), mismatches, dict(sorted(dispositions.items())), not mismatches and evaluation.accepted)


__all__ = ["CausalAlphaFrontierReconciliation", "reconcile_causal_alpha_frontier"]
