"""Publication and research-use policy for workspace views."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_public_data import WorkspaceFrontierOperation


class WorkspaceFrontierDecision(StrEnum):
    ALLOW_RESEARCH_VIEW = "allow_research_view"
    HOLD_FOR_REVIEW = "hold_for_review"
    WITHHOLD_OUT_OF_DOMAIN = "withhold_out_of_domain"


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierPolicyRule:
    rule_id: str
    operation: WorkspaceFrontierOperation
    allowed_states: tuple[str, ...]
    excluded_issue_codes: tuple[str, ...]
    decision: WorkspaceFrontierDecision
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierPolicyDecision:
    record_id: str
    operation: WorkspaceFrontierOperation
    decision: WorkspaceFrontierDecision
    publishable: bool
    state: str
    issue_codes: tuple[str, ...]
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierPolicy:
    rules: tuple[WorkspaceFrontierPolicyRule, ...]
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    content_address: str

    def decide(self, evaluation: WorkspaceFrontierEvaluation) -> tuple[WorkspaceFrontierPolicyDecision, ...]:
        output = []
        for execution in evaluation.executions:
            rule = next(item for item in self.rules if item.operation is execution.operation)
            if execution.state == "out_of_domain":
                decision = WorkspaceFrontierDecision.WITHHOLD_OUT_OF_DOMAIN
                publishable = False
                rationale = "context mismatch is withheld from the requested workspace"
            elif execution.issue_codes or execution.state in {"partial", "absent", "abstained", "invalid"}:
                decision = WorkspaceFrontierDecision.HOLD_FOR_REVIEW
                publishable = False
                rationale = "incomplete or unresolved workspace state remains review-only"
            else:
                decision = rule.decision
                publishable = decision is WorkspaceFrontierDecision.ALLOW_RESEARCH_VIEW
                rationale = rule.rationale
            body = {"record_id": execution.record_id, "operation": execution.operation, "decision": decision, "publishable": publishable, "state": execution.state, "issue_codes": execution.issue_codes, "rationale": rationale}
            output.append(WorkspaceFrontierPolicyDecision(**body, content_address=content_hash(body)))
        return tuple(output)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _rule(operation: WorkspaceFrontierOperation, allowed_states: tuple[str, ...], issues: tuple[str, ...], rationale: str) -> WorkspaceFrontierPolicyRule:
    body = {"rule_id": f"workspace-policy:{operation.value}", "operation": operation, "allowed_states": allowed_states, "excluded_issue_codes": issues, "decision": WorkspaceFrontierDecision.ALLOW_RESEARCH_VIEW, "rationale": rationale}
    return WorkspaceFrontierPolicyRule(**body, content_address=content_hash(body))


def default_workspace_frontier_policy() -> WorkspaceFrontierPolicy:
    rules = tuple(
        _rule(operation, ("supported",), issues, rationale)
        for operation, issues, rationale in (
            (WorkspaceFrontierOperation.CASE_WORKSPACE, ("missing_dossier", "context_mismatch", "invalid_workspace_input", "duplicate_variant_id"), "case navigation is allowed only as a research read model"),
            (WorkspaceFrontierOperation.COHORT_WORKSPACE, ("context_mismatch", "no_matching_records", "invalid_workspace_input"), "cohort records are descriptive and source-accounted"),
            (WorkspaceFrontierOperation.VARIANT_EXPLORER, ("context_mismatch", "variant_absent", "invalid_workspace_input"), "variant detail exposes declared relationships without inference"),
            (WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, ("context_mismatch", "track_parse_issue", "invalid_track_input"), "track intervals remain annotation-only research navigation"),
        )
    )
    allowed = (
        "research navigation",
        "source and context review",
        "bounded interval exploration",
        "accessibility evaluation",
        "fixture replay and testing",
    )
    excluded = (
        "diagnosis",
        "treatment recommendation",
        "clinical risk calculation",
        "causal conclusion from overlap",
        "cross-context record transport",
    )
    body = {"rules": rules, "allowed_uses": allowed, "excluded_uses": excluded}
    return WorkspaceFrontierPolicy(rules=rules, allowed_uses=allowed, excluded_uses=excluded, content_address=content_hash(body))


__all__ = [
    "WorkspaceFrontierDecision",
    "WorkspaceFrontierPolicy",
    "WorkspaceFrontierPolicyDecision",
    "WorkspaceFrontierPolicyRule",
    "default_workspace_frontier_policy",
]
