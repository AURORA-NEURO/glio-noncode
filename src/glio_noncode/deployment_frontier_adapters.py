"""Declarative adapter registry for deployment-governance operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .deployment_frontier_contracts import DeploymentFrontierOperation
from .deployment_frontier_operations import DeploymentFrontierOperationResult, run_deployment_frontier_operation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierAdapterSpec:
    operation: DeploymentFrontierOperation
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    deterministic: bool
    local_only: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierAdapterRegistry:
    specs: tuple[DeploymentFrontierAdapterSpec, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def spec(self, operation: DeploymentFrontierOperation | str) -> DeploymentFrontierAdapterSpec:
        value = DeploymentFrontierOperation(operation)
        return next(item for item in self.specs if item.operation is value)


def build_deployment_frontier_adapters() -> DeploymentFrontierAdapterRegistry:
    fields = {
        DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY: (("context_key", "requests", "policies"), ("allowed_ids", "denied_ids", "reason_codes")),
        DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE: (("bundle_id", "platform", "runtime_version", "artifacts", "services"), ("bundle_id", "artifact_ids", "service_ids", "manifest_address")),
        DeploymentFrontierOperation.FEDERATED_EXECUTION: (("plan_id", "context_key", "tasks", "sites", "privacy_budget"), ("plan_id", "eligible_task_ids", "denied_task_ids", "aggregate_address")),
        DeploymentFrontierOperation.RELEASE_ROLLBACK: (("release_id", "current_version", "requested_version", "checks", "action"), ("release_id", "current_version", "requested_version", "failed_checks", "decision_address")),
    }
    specs = []
    for operation in DeploymentFrontierOperation:
        inputs, outputs = fields[operation]
        body = {"operation": operation, "input_fields": inputs, "output_fields": outputs, "deterministic": True, "local_only": True}
        specs.append(DeploymentFrontierAdapterSpec(**body, content_address=deployment_address(body)))
    specs_tuple = tuple(specs)
    return DeploymentFrontierAdapterRegistry(specs_tuple, deployment_address(specs_tuple))


def execute_deployment_frontier_record_with_adapter(
    operation: DeploymentFrontierOperation | str,
    payload: Mapping[str, Any],
    registry: DeploymentFrontierAdapterRegistry | None = None,
) -> DeploymentFrontierOperationResult:
    registry = registry or build_deployment_frontier_adapters()
    registry.spec(operation)
    return run_deployment_frontier_operation(operation, payload)


__all__ = [
    "DeploymentFrontierAdapterRegistry",
    "DeploymentFrontierAdapterSpec",
    "build_deployment_frontier_adapters",
    "execute_deployment_frontier_record_with_adapter",
]
