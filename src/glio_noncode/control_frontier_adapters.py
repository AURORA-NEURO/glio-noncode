"""Typed adapter registry for the eight control frontier operation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .control_frontier_contracts import ControlFrontierOperation
from .control_frontier_operations import ControlFrontierOperationResult, run_control_frontier_operation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ControlFrontierAdapterSpec:
    operation: ControlFrontierOperation
    input_contract: str
    output_contract: str
    deterministic: bool
    review_on_control: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierAdapterRegistry:
    specs: tuple[ControlFrontierAdapterSpec, ...]
    content_address: str

    def spec(self, operation: ControlFrontierOperation | str) -> ControlFrontierAdapterSpec:
        selected = operation.value if isinstance(operation, ControlFrontierOperation) else str(operation)
        return next(item for item in self.specs if item.operation.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_adapters() -> ControlFrontierAdapterRegistry:
    """Materialize all input/output contracts and their safety boundaries."""

    labels = {
        ControlFrontierOperation.POLICY_CLAIM_GATE: ("policy-request", "policy-receipt"),
        ControlFrontierOperation.BUDGET_RESOURCE_SCHEDULER: ("budget-plan", "schedule-receipt"),
        ControlFrontierOperation.DETERMINISTIC_FALLBACK: ("failure-context", "fallback-receipt"),
        ControlFrontierOperation.HUMAN_REVIEW_ROUTER: ("review-items", "review-queue"),
        ControlFrontierOperation.EXECUTION_LEDGER: ("execution-events", "ledger-receipt"),
        ControlFrontierOperation.MODEL_REGISTRY: ("model-query", "model-resolution"),
        ControlFrontierOperation.DATA_REFERENCE_REGISTRY: ("reference-query", "reference-resolution"),
        ControlFrontierOperation.DRIFT_OOD_MONITOR: ("drift-observations", "monitor-report"),
    }
    specs = []
    for operation in ControlFrontierOperation:
        input_contract, output_contract = labels[operation]
        body = {"operation": operation, "input_contract": input_contract, "output_contract": output_contract, "deterministic": True, "review_on_control": True}
        specs.append(ControlFrontierAdapterSpec(**body, content_address=content_hash(body)))
    return ControlFrontierAdapterRegistry(tuple(specs), content_hash(tuple(specs)))


def execute_control_frontier_record_with_adapter(operation: ControlFrontierOperation | str, payload: Mapping[str, Any]) -> ControlFrontierOperationResult:
    """Run one allowlisted adapter through the shared dispatch boundary."""

    require_non_empty(str(operation), "operation")
    return run_control_frontier_operation(operation, payload)


__all__ = ["ControlFrontierAdapterRegistry", "ControlFrontierAdapterSpec", "build_control_frontier_adapters", "execute_control_frontier_record_with_adapter"]
