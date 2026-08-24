"""Dependency plan for D11 causal evidence operations."""

from __future__ import annotations

from .causal_architecture_contracts import (
    CausalArchitectureFixture,
    CausalArchitecturePlan,
    CausalArchitecturePlanNode,
    addressed,
)


def build_causal_architecture_plan(fixture: CausalArchitectureFixture) -> CausalArchitecturePlan:
    known = {item.operation_id for item in fixture.operations}
    nodes = []
    for operation in fixture.operations:
        ready = not (set(operation.dependencies) - known) and all(
            dependency in {item.operation_id for item in nodes}
            for dependency in operation.dependencies
        )
        body = {
            "operation_id": operation.operation_id,
            "ordinal": operation.ordinal,
            "dependencies": operation.dependencies,
            "family": operation.family,
            "plane": operation.plane,
            "ready": ready,
            "detail": (
                f"{operation.operation_id} is ready after "
                f"{', '.join(operation.dependencies) or 'fixture validation'}"
            ),
        }
        nodes.append(
            CausalArchitecturePlanNode(**body, content_address=addressed(body, "causal-plan-node"))
        )
    return CausalArchitecturePlan(
        fixture.fixture_id,
        tuple(nodes),
        len(nodes) == 16 and all(item.ready for item in nodes),
        addressed(nodes, "causal-plan"),
    )


def causal_architecture_operation_order(plan: CausalArchitecturePlan) -> tuple[str, ...]:
    return tuple(item.operation_id for item in plan.nodes)


__all__ = ["build_causal_architecture_plan", "causal_architecture_operation_order"]
