"""State transition checks from primitive result to publication disposition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha import CohortAlphaState
from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierDisposition, CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierStateTransition:
    record_id: str
    observed_state: CohortAlphaState
    disposition: CohortAlphaFrontierDisposition
    allowed: bool
    rule: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierStateTransitionReport:
    transitions: tuple[CohortAlphaFrontierStateTransition, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_state_transitions(evaluation: CohortAlphaFrontierEvaluation, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierStateTransitionReport:
    transitions = []
    for row in evaluation.rows:
        disposition = policy.for_record(row.record_id).disposition
        allowed = (row.observed_state is CohortAlphaState.SUPPORTED and disposition is CohortAlphaFrontierDisposition.PUBLISH) or (row.observed_state in {CohortAlphaState.PARTIAL, CohortAlphaState.AMBIGUOUS} and disposition is CohortAlphaFrontierDisposition.REVIEW) or (row.observed_state in {CohortAlphaState.OUT_OF_DOMAIN, CohortAlphaState.ABSTAINED} and disposition is CohortAlphaFrontierDisposition.QUARANTINE)
        rule = "supported publishes; incomplete reviews; foreign or empty quarantines"
        transitions.append(CohortAlphaFrontierStateTransition(row.record_id, row.observed_state, disposition, allowed, rule, content_hash({"record_id": row.record_id, "state": row.observed_state, "disposition": disposition, "allowed": allowed}, prefix="alpha-state-transition")))
    values = tuple(transitions)
    return CohortAlphaFrontierStateTransitionReport(values, len(values) == 16 and all(item.allowed for item in values), content_hash(values, prefix="alpha-state-transitions"))


__all__ = ["CohortAlphaFrontierStateTransition", "CohortAlphaFrontierStateTransitionReport", "build_cohort_alpha_frontier_state_transitions"]
