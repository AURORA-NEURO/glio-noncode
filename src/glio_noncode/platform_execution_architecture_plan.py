"""Dependency plan for D16 platform execution operations."""

from __future__ import annotations

from .platform_execution_architecture_contracts import (
    PlatformExecutionFixture,
    PlatformExecutionPlan,
    PlatformExecutionPlanNode,
    addressed,
)
from .platform_execution_architecture_public_data import default_platform_execution_fixture


def build_platform_execution_plan(
    fixture: PlatformExecutionFixture | None = None,
) -> PlatformExecutionPlan:
    selected = fixture or default_platform_execution_fixture()
    nodes = tuple(
        PlatformExecutionPlanNode(
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
                f"{operation.operation_id} consumes {operation.input_contract} and emits "
                f"{operation.output_contract}"
            ),
            addressed(
                {
                    "operation": operation.operation_id,
                    "ordinal": operation.ordinal,
                    "dependencies": operation.dependencies,
                },
                "platform-execution-plan-node",
            ),
        )
        for operation in selected.operations
    )
    body = {"fixture_id": selected.fixture_id, "nodes": nodes}
    return PlatformExecutionPlan(
        selected.fixture_id,
        nodes,
        bool(nodes) and all(item.ready for item in nodes),
        addressed(body, "platform-execution-plan"),
    )


def platform_execution_plan_summary(plan: PlatformExecutionPlan) -> dict[str, object]:
    return {
        "fixture_id": plan.fixture_id,
        "node_count": len(plan.nodes),
        "accepted": plan.accepted,
        "operation_order": [item.operation_id for item in plan.nodes],
        "dependency_count": sum(len(item.dependencies) for item in plan.nodes),
    }


__all__ = ["build_platform_execution_plan", "platform_execution_plan_summary"]
