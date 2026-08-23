"""Research-use policy for the C01-C04 platform runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PLATFORM_FRONTIER_BOUNDARY, PlatformFrontierEvaluation, PlatformFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierPolicyRule:
    rule_id: str
    category: str
    decision: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierPolicy:
    policy_id: str
    version: str
    boundary: str
    allowed_uses: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    rules: tuple[PlatformFrontierPolicyRule, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_platform_frontier_policy() -> PlatformFrontierPolicy:
    rows = (
        ("research-use", "intended_use", "allow", "planning and execution are research-only"),
        ("typed-tools", "tool-scope", "allow", "only registered tool contracts may run"),
        ("local-default", "network", "deny", "local sandbox denies network egress by default"),
        ("private-fields", "privacy", "deny", "direct identifiers are not admitted"),
        ("claim-boundary", "claims", "deny", "clinical and treatment claims are outside scope"),
        ("replay", "provenance", "allow", "input and event addresses are retained"),
    )
    rules = []
    for rule_id, category, decision, detail in rows:
        body = {"rule_id": rule_id, "category": category, "decision": decision, "detail": detail}
        rules.append(PlatformFrontierPolicyRule(**body, content_address=content_hash(body)))
    body = {"policy_id": "platform-frontier-policy", "version": "2026.08", "boundary": PLATFORM_FRONTIER_BOUNDARY, "allowed_uses": ("research_workflow", "aggregate_runtime", "replay_and_review"), "prohibited_claims": ("diagnosis", "treatment_recommendation", "clinical_eligibility"), "rules": tuple(rules), "accepted": True}
    return PlatformFrontierPolicy(**body, content_address=content_hash(body))


def evaluate_platform_frontier_policy(policy: PlatformFrontierPolicy, fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation) -> tuple[str, ...]:
    issues = []
    if policy.boundary != fixture.evidence_boundary:
        issues.append("boundary_mismatch")
    if not policy.accepted:
        issues.append("policy_not_accepted")
    if any("clinical" in str(item.output).lower() for item in evaluation.executions):
        issues.append("prohibited_claim_surface")
    if not evaluation.accepted:
        issues.append("evaluation_not_accepted")
    return tuple(issues)


__all__ = ["PlatformFrontierPolicy", "PlatformFrontierPolicyRule", "default_platform_frontier_policy", "evaluate_platform_frontier_policy"]
