"""Input/output schema manifest for the deployment-governance frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .deployment_frontier_contracts import DeploymentFrontierOperation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierFieldSpec:
    field_id: str
    operation: DeploymentFrontierOperation
    required: bool
    value_type: str
    sensitive: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierSchema:
    version: str
    fields: tuple[DeploymentFrontierFieldSpec, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def fields_for(self, operation: DeploymentFrontierOperation | str) -> tuple[DeploymentFrontierFieldSpec, ...]:
        value = DeploymentFrontierOperation(operation)
        return tuple(item for item in self.fields if item.operation is value)


def default_deployment_frontier_schema() -> DeploymentFrontierSchema:
    rows = (
        (DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY, "context_key", True, "string", False, "exact research context"),
        (DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY, "requests", True, "array", False, "policy requests"),
        (DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY, "policies", True, "object", False, "named policy rules"),
        (DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE, "bundle_id", True, "string", False, "bundle identity"),
        (DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE, "artifacts", True, "array", False, "digest-addressed artifacts"),
        (DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE, "services", True, "array", False, "service dependency inventory"),
        (DeploymentFrontierOperation.FEDERATED_EXECUTION, "plan_id", True, "string", False, "coordination plan identity"),
        (DeploymentFrontierOperation.FEDERATED_EXECUTION, "tasks", True, "array", False, "aggregate tasks"),
        (DeploymentFrontierOperation.FEDERATED_EXECUTION, "sites", True, "array", False, "site capability declarations"),
        (DeploymentFrontierOperation.FEDERATED_EXECUTION, "privacy_budget", True, "integer", False, "declared privacy budget"),
        (DeploymentFrontierOperation.RELEASE_ROLLBACK, "release_id", True, "string", False, "release identity"),
        (DeploymentFrontierOperation.RELEASE_ROLLBACK, "requested_version", True, "string", False, "requested version"),
        (DeploymentFrontierOperation.RELEASE_ROLLBACK, "checks", True, "object", False, "release gate results"),
        (DeploymentFrontierOperation.RELEASE_ROLLBACK, "action", True, "string", False, "release or rollback"),
    )
    fields = tuple(DeploymentFrontierFieldSpec(f"{operation.value}.{field}", operation, required, value_type, sensitive, description) for operation, field, required, value_type, sensitive, description in rows)
    body = {"version": "deployment-frontier-schema-v1", "fields": fields}
    return DeploymentFrontierSchema(**body, content_address=deployment_address(body))


def validate_deployment_frontier_schema(payload: Mapping[str, Any], operation: DeploymentFrontierOperation | str, schema: DeploymentFrontierSchema | None = None) -> tuple[str, ...]:
    schema = schema or default_deployment_frontier_schema()
    missing = tuple(item.field_id.split(".", 1)[1] for item in schema.fields_for(operation) if item.required and item.field_id.split(".", 1)[1] not in payload)
    return missing


__all__ = ["DeploymentFrontierFieldSpec", "DeploymentFrontierSchema", "default_deployment_frontier_schema", "validate_deployment_frontier_schema"]
