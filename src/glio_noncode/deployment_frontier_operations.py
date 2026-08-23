"""Functional adapters for D16 C13-C16 deployment-governance operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .errors import GlioError
from .frontier_release_alpha import (
    FederatedExecutionCoordinator,
    LocalDeploymentBundleBuilder,
    PrivacySecurityPolicyEngine,
    ReleaseRollbackController,
)
from .serialization import content_hash, jsonable
from .deployment_frontier_contracts import (
    DeploymentFrontierOperation,
    DeploymentFrontierState,
)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOperationResult:
    operation: DeploymentFrontierOperation
    state: DeploymentFrontierState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _result(
    operation: DeploymentFrontierOperation,
    state: DeploymentFrontierState,
    issue_codes: tuple[str, ...],
    output: Mapping[str, Any],
) -> DeploymentFrontierOperationResult:
    normalized = tuple(dict.fromkeys(issue_codes))
    body = {"operation": operation, "state": state, "issue_codes": normalized, "output": output}
    return DeploymentFrontierOperationResult(operation, state, normalized, output, content_hash(body))


def _prefix_codes(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item).split(":", 1)[0] for item in values if str(item)))


def _privacy(payload: Mapping[str, Any]) -> DeploymentFrontierOperationResult:
    context_key = str(payload["context_key"])
    report = PrivacySecurityPolicyEngine().evaluate(
        payload.get("requests", ()), context_key=context_key, policies=payload.get("policies", {})
    )
    reasons = tuple(reason for item in report.decisions for reason in item.reasons)
    issues = _prefix_codes(reasons)
    output = {
        "allowed_ids": report.allowed_ids,
        "denied_ids": report.denied_ids,
        "decision_count": len(report.decisions),
        "decision_states": tuple(item.state.value for item in report.decisions),
        "reason_codes": issues,
        "report_address": report.content_address,
    }
    state = DeploymentFrontierState.READY if report.allowed_ids and not report.denied_ids else DeploymentFrontierState.DENIED
    return _result(DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY, state, issues, output)


def _bundle(payload: Mapping[str, Any]) -> DeploymentFrontierOperationResult:
    offline = bool(payload.get("offline", True))
    try:
        bundle = LocalDeploymentBundleBuilder().build(
            payload,
            bundle_id=str(payload["bundle_id"]),
            platform=str(payload["platform"]),
            runtime_version=str(payload["runtime_version"]),
            offline=offline,
        )
    except (GlioError, KeyError, TypeError, ValueError) as exc:
        return _result(
            DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE,
            DeploymentFrontierState.HOLD,
            ("bundle_requirements_missing",),
            {"error_type": type(exc).__name__, "error_class": getattr(exc, "code", "bundle_error")},
        )
    issues: list[str] = []
    if any(not item.digest.startswith("sha256:") for item in bundle.artifacts):
        issues.append("invalid_digest")
    if not bundle.offline:
        issues.append("offline_mode_required")
    output = {
        "bundle_id": bundle.bundle_id,
        "platform": bundle.platform,
        "runtime_version": bundle.runtime_version,
        "artifact_ids": tuple(item.artifact_id for item in bundle.artifacts),
        "artifact_count": len(bundle.artifacts),
        "service_ids": tuple(str(item.get("service_id", "")) for item in bundle.services),
        "service_count": len(bundle.services),
        "offline": bundle.offline,
        "state": bundle.state.value,
        "manifest_address": bundle.manifest_address,
    }
    state = DeploymentFrontierState.READY if not issues and bundle.state.value == "ready" else DeploymentFrontierState.HOLD
    return _result(DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE, state, tuple(issues), output)


def _federated(payload: Mapping[str, Any]) -> DeploymentFrontierOperationResult:
    context_key = str(payload["context_key"])
    plan = FederatedExecutionCoordinator().coordinate(
        payload.get("tasks", ()),
        payload.get("sites", ()),
        plan_id=str(payload["plan_id"]),
        context_key=context_key,
        privacy_budget=int(payload.get("privacy_budget", 0)),
        minimum_site_count=int(payload.get("minimum_site_count", 1)),
    )
    reasons = tuple(
        reason
        for item in plan.assignments
        if not item.eligible
        for reason in str(item.reason).split(";")
    )
    issues = _prefix_codes(reasons)
    output = {
        "plan_id": plan.plan_id,
        "eligible_task_ids": plan.eligible_task_ids,
        "denied_task_ids": plan.denied_task_ids,
        "assignment_count": len(plan.assignments),
        "eligible_assignment_count": sum(item.eligible for item in plan.assignments),
        "aggregate_address": plan.aggregate_address,
        "assignment_states": tuple(item.state.value for item in plan.assignments),
    }
    state = DeploymentFrontierState.READY if plan.eligible_task_ids and not plan.denied_task_ids else DeploymentFrontierState.HOLD
    return _result(DeploymentFrontierOperation.FEDERATED_EXECUTION, state, issues, output)


def _release(payload: Mapping[str, Any]) -> DeploymentFrontierOperationResult:
    decision = ReleaseRollbackController().decide(
        release_id=str(payload["release_id"]),
        current_version=str(payload["current_version"]),
        requested_version=str(payload["requested_version"]),
        action=str(payload.get("action", "release")),
        previous_version=payload.get("previous_version"),
        checks=payload.get("checks", {}),
        required_checks=tuple(str(item) for item in payload.get("required_checks", ("tests", "integrity", "compatibility", "policy"))),
    )
    issues = tuple(f"failed_check:{item}" if item not in {"previous_version_missing", "version_already_current"} else item for item in decision.failed_checks)
    output = {
        "release_id": decision.release_id,
        "current_version": decision.current_version,
        "requested_version": decision.requested_version,
        "action": decision.action,
        "failed_checks": decision.failed_checks,
        "check_names": tuple(sorted(decision.checks)),
        "state": decision.state.value,
        "decision_address": decision.content_address,
    }
    state = DeploymentFrontierState(decision.state.value)
    return _result(DeploymentFrontierOperation.RELEASE_ROLLBACK, state, issues, output)


def _error(operation: DeploymentFrontierOperation, exc: Exception) -> DeploymentFrontierOperationResult:
    if operation is DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY:
        issue = "policy_contract_failure"
        state = DeploymentFrontierState.DENIED
    elif operation is DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE:
        issue = "bundle_contract_failure"
        state = DeploymentFrontierState.HOLD
    elif operation is DeploymentFrontierOperation.FEDERATED_EXECUTION:
        issue = "federation_contract_failure"
        state = DeploymentFrontierState.HOLD
    else:
        issue = "release_contract_failure"
        state = DeploymentFrontierState.DENIED
    return _result(operation, state, (issue,), {"error_type": type(exc).__name__, "error_class": getattr(exc, "code", "deployment_error")})


def run_deployment_frontier_operation(
    operation: DeploymentFrontierOperation | str,
    payload: Mapping[str, Any],
) -> DeploymentFrontierOperationResult:
    """Run one deployment operation and normalize expected failures."""

    op = DeploymentFrontierOperation(operation)
    try:
        if op is DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY:
            return _privacy(payload)
        if op is DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE:
            return _bundle(payload)
        if op is DeploymentFrontierOperation.FEDERATED_EXECUTION:
            return _federated(payload)
        return _release(payload)
    except (GlioError, KeyError, TypeError, ValueError) as exc:
        return _error(op, exc)


__all__ = ["DeploymentFrontierOperationResult", "run_deployment_frontier_operation"]
