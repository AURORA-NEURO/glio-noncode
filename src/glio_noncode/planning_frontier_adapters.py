"""Operation adapters with explicit registry closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .planning_frontier_contracts import PlanningOperation, PlanningOperationResult
from .planning_frontier_operations import (
    evaluate_controls_randomization,
    evaluate_guide_oligo_adaptation,
    evaluate_model_system_eligibility,
    evaluate_power_replication,
)
from .planning_frontier_support import mapping
from .serialization import content_hash, jsonable


Planner = Callable[[Mapping[str, Any]], PlanningOperationResult]


@dataclass(frozen=True, slots=True)
class PlanningAdapter:
    operation: PlanningOperation
    capability_id: str
    planner: Planner
    accepted_input_shapes: tuple[str, ...]
    output_boundary: str
    content_address: str

    def execute(self, payload: Mapping[str, Any]) -> PlanningOperationResult:
        return self.planner(mapping(payload, "payload"))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"planner": self.planner.__name__}


@dataclass(frozen=True, slots=True)
class PlanningAdapterRegistry:
    adapters: tuple[PlanningAdapter, ...]
    content_address: str

    def __post_init__(self) -> None:
        if tuple(item.operation for item in self.adapters) != tuple(PlanningOperation):
            raise ValueError("planning adapters must cover operations in stable order")

    def for_operation(self, operation: PlanningOperation | str) -> PlanningAdapter:
        selected = operation if isinstance(operation, PlanningOperation) else PlanningOperation(str(operation))
        return next(item for item in self.adapters if item.operation is selected)

    def to_dict(self) -> dict[str, Any]:
        return {"adapters": tuple(item.to_dict() for item in self.adapters), "content_address": self.content_address}


def build_planning_adapters() -> PlanningAdapterRegistry:
    values = (
        (PlanningOperation.MODEL_ELIGIBILITY, "GNC-D13-C09", evaluate_model_system_eligibility, ("observations", "model_system", "minimum_evidence_strength")),
        (PlanningOperation.GUIDE_OLIGO, "GNC-D13-C10", evaluate_guide_oligo_adaptation, ("source_id", "source_version", "input_format", "text")),
        (PlanningOperation.CONTROLS_RANDOMIZATION, "GNC-D13-C11", evaluate_controls_randomization, ("targets", "plan_id", "control_types", "biological_replicates", "technical_replicates", "randomization_seed")),
        (PlanningOperation.POWER_REPLICATION, "GNC-D13-C12", evaluate_power_replication, ("observations",)),
    )
    adapters = tuple(
        PlanningAdapter(
            operation=operation,
            capability_id=capability_id,
            planner=planner,
            accepted_input_shapes=inputs,
            output_boundary="research_planning_only",
            content_address=content_hash({"operation": operation, "capability_id": capability_id, "inputs": inputs}, prefix="planning-adapter"),
        )
        for operation, capability_id, planner, inputs in values
    )
    return PlanningAdapterRegistry(
        adapters,
        content_hash(tuple(item.content_address for item in adapters), prefix="planning-adapter-registry"),
    )


def execute_planning_adapter(registry: PlanningAdapterRegistry, operation: PlanningOperation | str, payload: Mapping[str, Any]) -> PlanningOperationResult:
    return registry.for_operation(operation).execute(payload)


__all__ = ["PlanningAdapter", "PlanningAdapterRegistry", "build_planning_adapters", "execute_planning_adapter"]
