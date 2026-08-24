"""Dependency-safe operation plan for D15 workbench architecture."""

from __future__ import annotations

from .workbench_architecture_contracts import (
    WorkbenchArchitectureFixture,
    WorkbenchArchitecturePlan,
    WorkbenchArchitecturePlanNode,
    addressed,
)
from .workbench_architecture_public_data import default_workbench_architecture_fixture


def build_workbench_architecture_plan(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> WorkbenchArchitecturePlan:
    selected = fixture or default_workbench_architecture_fixture()
    prior = {item.operation_id for item in selected.operations}
    nodes = tuple(
        WorkbenchArchitecturePlanNode(
            operation.operation_id,
            operation.ordinal,
            operation.dependencies,
            operation.family,
            operation.plane,
            all(
                dependency
                in {item.operation_id for item in selected.operations[: operation.ordinal - 1]}
                for dependency in operation.dependencies
            ),
            (
                f"{operation.operation_id} consumes {operation.input_contract} "
                f"and emits {operation.output_contract}"
            ),
            addressed(
                {
                    "operation": operation.operation_id,
                    "ordinal": operation.ordinal,
                    "dependencies": operation.dependencies,
                },
                "workbench-architecture-plan-node",
            ),
        )
        for operation in selected.operations
    )
    body = {
        "fixture_id": selected.fixture_id,
        "nodes": nodes,
        "known_operations": tuple(sorted(prior)),
    }
    return WorkbenchArchitecturePlan(
        selected.fixture_id,
        nodes,
        bool(nodes) and all(item.ready for item in nodes),
        addressed(body, "workbench-architecture-plan"),
    )


def workbench_architecture_plan_order(plan: WorkbenchArchitecturePlan) -> tuple[str, ...]:
    return tuple(item.operation_id for item in plan.nodes)


def workbench_architecture_plan_summary(plan: WorkbenchArchitecturePlan) -> dict[str, object]:
    return {
        "fixture_id": plan.fixture_id,
        "node_count": len(plan.nodes),
        "accepted": plan.accepted,
        "operation_order": workbench_architecture_plan_order(plan),
        "dependency_count": sum(len(item.dependencies) for item in plan.nodes),
    }


__all__ = [
    "build_workbench_architecture_plan",
    "workbench_architecture_plan_order",
    "workbench_architecture_plan_summary",
]
