"""Detailed reviewer protocol for D13 C09-C12 planning artifacts.

This protocol is executable documentation.  It gives each review step an
owner, an input, an acceptance condition, an escalation condition, and a
prohibited interpretation.  The protocol deliberately keeps review work
separate from biological execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture, PlanningOperation, PlanningState
from .planning_frontier_governance import PlanningClaimBoundary, build_planning_claim_boundary
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningProtocolStep:
    step_id: str
    sequence: int
    operation: PlanningOperation | None
    owner: str
    input_artifact: str
    acceptance_condition: str
    escalation_condition: str
    prohibited_interpretation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningProtocolDecision:
    record_id: str
    step_id: str
    disposition: str
    rationale: str
    issue_codes: tuple[str, ...]
    next_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningReviewProtocol:
    protocol_id: str
    steps: tuple[PlanningProtocolStep, ...]
    decisions: tuple[PlanningProtocolDecision, ...]
    claim_boundary: PlanningClaimBoundary
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def markdown(self) -> str:
        lines = [f"# {self.protocol_id}", "", "| Step | Owner | Input | Acceptance | Escalation |", "|---|---|---|---|---|"]
        for step in self.steps:
            lines.append(f"| {step.sequence}. {step.step_id} | {step.owner} | {step.input_artifact} | {step.acceptance_condition} | {step.escalation_condition} |")
        lines.extend(("", "## Decisions", ""))
        for decision in self.decisions:
            lines.append(f"- `{decision.record_id}`: `{decision.disposition}` — {decision.next_action}")
        return "\n".join(lines) + "\n"


def _step(step_id: str, sequence: int, operation: PlanningOperation | None, owner: str, input_artifact: str, acceptance: str, escalation: str, prohibited: str) -> PlanningProtocolStep:
    body = {"step_id": step_id, "sequence": sequence, "operation": operation, "owner": owner, "input_artifact": input_artifact, "acceptance_condition": acceptance, "escalation_condition": escalation, "prohibited_interpretation": prohibited}
    return PlanningProtocolStep(**body, content_address=content_hash(body, prefix="planning-protocol-step"))


def default_planning_protocol_steps() -> tuple[PlanningProtocolStep, ...]:
    return (
        _step("scope", 1, None, "reviewer", "fixture boundary", "fixture is public aggregate", "any private marker", "scope is not a biological conclusion"),
        _step("source-closure", 2, None, "evidence reviewer", "source registry", "all joins resolve to HTTPS receipts", "unknown or duplicate source IDs", "a receipt is not a validation result"),
        _step("context-lock", 3, None, "context reviewer", "context key", "requested key is exact", "foreign context or missing context", "context similarity is not context identity"),
        _step("eligibility-review", 4, PlanningOperation.MODEL_ELIGIBILITY, "model reviewer", "eligibility results", "declared support and threshold are visible", "weak evidence or blockers", "eligibility is not fidelity proof"),
        _step("guide-review", 5, PlanningOperation.GUIDE_OLIGO, "design reviewer", "adapted guide rows", "identity and sequence are preserved", "malformed or foreign row", "adaptation is not activity proof"),
        _step("control-review", 6, PlanningOperation.CONTROLS_RANDOMIZATION, "assay planner", "assignment plan", "seed and replicate dimensions are explicit", "missing target or foreign target", "assignment is not execution"),
        _step("power-review", 7, PlanningOperation.POWER_REPLICATION, "statistics reviewer", "power estimates", "assumptions and shortfall are explicit", "invalid effect or variance", "approximation is not a guarantee"),
        _step("issue-review", 8, None, "quality reviewer", "issue codes", "every held row has a reason", "silent state or missing issue", "a held row is not negative evidence"),
        _step("role-review", 9, None, "quality reviewer", "positive/control partitions", "one positive and three controls per operation", "unbalanced scenario set", "controls do not establish validity"),
        _step("replay-review", 10, None, "reproducibility reviewer", "replay receipt", "addresses repeat exactly", "address drift", "replay is not independent replication"),
        _step("release-review", 11, None, "release reviewer", "release package", "ready rows and held rows are separated", "held row proposed for release", "release is not approval"),
        _step("handoff", 12, None, "operator", "handoff package", "next actions and exclusions are present", "boundary omitted", "handoff is not a clinical instruction"),
    )


def _decision(record_id: str, operation: PlanningOperation, state: PlanningState, issues: tuple[str, ...]) -> PlanningProtocolDecision:
    disposition = "review-release" if state is PlanningState.READY_FOR_REVIEW else "hold"
    if state is PlanningState.BLOCKED:
        next_action = "resolve context or source boundary before reconsidering"
    elif state is PlanningState.ABSTAINED:
        next_action = "obtain a public aggregate observation before reconsidering"
    elif state is PlanningState.REJECTED:
        next_action = "repair the payload shape and rerun contract validation"
    elif state is PlanningState.REVIEW:
        next_action = "inspect assumptions, controls, and issue codes"
    else:
        next_action = "retain as bounded research-planning output"
    body = {"record_id": record_id, "step_id": f"{operation.value}:decision", "disposition": disposition, "rationale": "state and issue codes determine disposition", "issue_codes": issues, "next_action": next_action}
    return PlanningProtocolDecision(**body, content_address=content_hash(body, prefix="planning-protocol-decision"))


def build_planning_review_protocol(fixture: PlanningFixture, evaluation: PlanningEvaluation, *, protocol_id: str = "planning-review-protocol") -> PlanningReviewProtocol:
    steps = default_planning_protocol_steps()
    decisions = tuple(_decision(item.record_id, item.operation, item.observed_state, item.issue_codes) for item in evaluation.executions)
    boundary = build_planning_claim_boundary()
    accepted = bool(len(steps) == 12 and len(decisions) == len(fixture.records) and boundary.accepted and all(item.content_address for item in decisions))
    body = {"protocol_id": protocol_id, "steps": steps, "decisions": decisions, "claim_boundary": boundary, "accepted": accepted}
    return PlanningReviewProtocol(**body, content_address=content_hash(body, prefix="planning-review-protocol"))


def protocol_disposition_counts(protocol: PlanningReviewProtocol) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision in protocol.decisions:
        counts[decision.disposition] = counts.get(decision.disposition, 0) + 1
    return counts


__all__ = [
    "PlanningProtocolDecision",
    "PlanningProtocolStep",
    "PlanningReviewProtocol",
    "build_planning_review_protocol",
    "default_planning_protocol_steps",
    "protocol_disposition_counts",
]
