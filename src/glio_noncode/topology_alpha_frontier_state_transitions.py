"""State vocabulary and transition rules for alpha operation results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha import TopologyAlphaState
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierTransitionRule:
    operation: str
    source_state: str
    target_state: str
    trigger: str
    permitted: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierTransitionObservation:
    record_id: str
    operation: str
    state: str
    matched_rule: bool
    transition_class: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierStateTransitionReport:
    vocabulary: tuple[str, ...]
    rules: tuple[TopologyAlphaFrontierTransitionRule, ...]
    observations: tuple[TopologyAlphaFrontierTransitionObservation, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_state(self, state: str) -> tuple[TopologyAlphaFrontierTransitionObservation, ...]:
        return tuple(item for item in self.observations if item.state == state)

    def for_operation(self, operation: str) -> tuple[TopologyAlphaFrontierTransitionObservation, ...]:
        return tuple(item for item in self.observations if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"vocabulary": self.vocabulary, "rules": [item.to_dict() for item in self.rules], "observations": [item.to_dict() for item in self.observations], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _rules() -> tuple[TopologyAlphaFrontierTransitionRule, ...]:
    operations = ("boundary_motif", "ctcf_cohesin", "idh_insulator", "sv_rewire")
    return tuple(TopologyAlphaFrontierTransitionRule(operation, source, target, trigger, True, rationale) for operation in operations for source, target, trigger, rationale in (("supported", "partial", "required channel or edge field missing", "missingness lowers support"), ("supported", "ambiguous", "competing labels or channel disagreement", "disagreement prevents collapse"), ("supported", "out_of_domain", "exact context differs", "foreign context blocks transport"), ("partial", "invalid", "controlled vocabulary violation", "invalid input is retained")))


def audit_topology_alpha_frontier_state_transitions(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierStateTransitionReport:
    vocabulary = tuple(item.value for item in TopologyAlphaState)
    rules = _rules()
    observations = []
    for row in evaluation.rows:
        transition_class = "support" if row.observed_state == "supported" else "review"
        trigger = "exact replay state"
        if row.observed_issue_codes:
            trigger = ",".join(row.observed_issue_codes)
        matched = row.observed_state in vocabulary and bool(row.adapter.content_address)
        observations.append(TopologyAlphaFrontierTransitionObservation(row.record_id, row.operation, row.observed_state, matched, transition_class, trigger))
    return TopologyAlphaFrontierStateTransitionReport(vocabulary, rules, tuple(observations), len(observations) == 16 and all(item.matched_rule for item in observations))


__all__ = ["TopologyAlphaFrontierStateTransitionReport", "TopologyAlphaFrontierTransitionObservation", "TopologyAlphaFrontierTransitionRule", "audit_topology_alpha_frontier_state_transitions"]
