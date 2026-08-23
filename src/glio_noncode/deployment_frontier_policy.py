"""Research-use policy rules for deployment-governance outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .deployment_frontier_contracts import DeploymentFrontierState
from .deployment_frontier_support import contains_forbidden_output, deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierPolicyRule:
    rule_id: str
    operation: str
    required_state: tuple[str, ...]
    allowed_scope: str
    deny_if_sensitive: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierPolicy:
    version: str
    rules: tuple[DeploymentFrontierPolicyRule, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierPolicyDecision:
    rule_id: str
    passed: bool
    state: str
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_deployment_frontier_policy() -> DeploymentFrontierPolicy:
    rules = (
        DeploymentFrontierPolicyRule("D16-C13-research-read", "privacy_security_policy", ("ready",), "aggregate", True, "privacy decisions require explicit allowed scope"),
        DeploymentFrontierPolicyRule("D16-C14-offline-bundle", "local_deployment_bundle", ("ready",), "local", True, "local bundles require digest and offline readiness"),
        DeploymentFrontierPolicyRule("D16-C15-site-local", "federated_execution", ("ready",), "aggregate", True, "coordination exposes assignments without raw site data"),
        DeploymentFrontierPolicyRule("D16-C16-release-gates", "release_rollback", ("released", "rolled_back"), "local", True, "release transitions require every declared gate"),
    )
    body = {"version": "deployment-frontier-policy-v1", "rules": rules}
    return DeploymentFrontierPolicy(**body, content_address=deployment_address(body))


def evaluate_deployment_frontier_policy(
    operation: str,
    state: DeploymentFrontierState | str,
    output: Mapping[str, Any],
    policy: DeploymentFrontierPolicy | None = None,
) -> DeploymentFrontierPolicyDecision:
    policy = policy or default_deployment_frontier_policy()
    rule = next(item for item in policy.rules if item.operation == str(operation))
    state_text = state.value if isinstance(state, DeploymentFrontierState) else str(state)
    issues = []
    if state_text not in rule.required_state:
        issues.append("state_not_releaseable")
    if rule.deny_if_sensitive and contains_forbidden_output(output):
        issues.append("sensitive_output")
    body = {"rule_id": rule.rule_id, "passed": not issues, "state": state_text, "issue_codes": tuple(issues)}
    return DeploymentFrontierPolicyDecision(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierPolicy", "DeploymentFrontierPolicyDecision", "DeploymentFrontierPolicyRule", "default_deployment_frontier_policy", "evaluate_deployment_frontier_policy"]
