"""Typed adapter registry for the four platform-control operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierOperation, PlatformFrontierRecord
from .platform_frontier_operations import PlatformFrontierOperationResult, run_platform_frontier_operation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class PlatformFrontierAdapterSpec:
    operation: PlatformFrontierOperation
    input_contract: str
    output_contract: str
    deterministic: bool
    failure_modes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierAdapterRegistry:
    specs: tuple[PlatformFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def resolve(self, operation: PlatformFrontierOperation | str) -> PlatformFrontierAdapterSpec:
        operation = PlatformFrontierOperation(operation)
        for spec in self.specs:
            if spec.operation is operation:
                return spec
        raise KeyError(operation.value)


def build_platform_frontier_adapters() -> PlatformFrontierAdapterRegistry:
    specs = []
    rows = (
        (PlatformFrontierOperation.MISSION_PLANNER, "mission_request", "mission_plan", ("empty_request", "unknown_role", "claim_ceiling")),
        (PlatformFrontierOperation.WORKFLOW_COMPILER, "workflow_steps", "compiled_workflow", ("cycle", "missing_dependency", "warning")),
        (PlatformFrontierOperation.TYPED_TOOL_REGISTRY, "tool_query", "tool_descriptor", ("missing_tool", "contract_mismatch", "cardinality")),
        (PlatformFrontierOperation.EXECUTION_SANDBOX, "invocation_request", "sandbox_run", ("unregistered", "network_boundary", "sensitive_input")),
    )
    for operation, input_contract, output_contract, failure_modes in rows:
        body = {"operation": operation, "input_contract": input_contract, "output_contract": output_contract, "deterministic": True, "failure_modes": failure_modes}
        specs.append(PlatformFrontierAdapterSpec(**body, content_address=content_hash(body)))
    body = {"specs": tuple(specs), "accepted": len(specs) == 4 and len({item.operation for item in specs}) == 4}
    return PlatformFrontierAdapterRegistry(**body, content_address=content_hash(body))


def execute_platform_frontier_record_with_adapter(record: PlatformFrontierRecord, registry: PlatformFrontierAdapterRegistry | None = None) -> PlatformFrontierOperationResult:
    registry = registry or build_platform_frontier_adapters()
    registry.resolve(record.operation)
    return run_platform_frontier_operation(record.operation, record.payload)


__all__ = ["PlatformFrontierAdapterRegistry", "PlatformFrontierAdapterSpec", "build_platform_frontier_adapters", "execute_platform_frontier_record_with_adapter"]
