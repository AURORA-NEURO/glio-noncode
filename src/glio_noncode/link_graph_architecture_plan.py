"""Dependency plan for D10 link-graph operations."""

from __future__ import annotations

from .link_graph_architecture_contracts import (
    LinkGraphArchitectureFixture,
    LinkGraphArchitecturePlan,
    LinkGraphArchitecturePlanNode,
    addressed,
)


def build_link_graph_architecture_plan(
    fixture: LinkGraphArchitectureFixture,
) -> LinkGraphArchitecturePlan:
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
            LinkGraphArchitecturePlanNode(**body, content_address=addressed(body, "link-plan-node"))
        )
    return LinkGraphArchitecturePlan(
        fixture.fixture_id,
        tuple(nodes),
        len(nodes) == 16 and all(item.ready for item in nodes),
        addressed(nodes, "link-plan"),
    )


def link_graph_architecture_operation_order(plan: LinkGraphArchitecturePlan) -> tuple[str, ...]:
    return tuple(item.operation_id for item in plan.nodes)


__all__ = ["build_link_graph_architecture_plan", "link_graph_architecture_operation_order"]
