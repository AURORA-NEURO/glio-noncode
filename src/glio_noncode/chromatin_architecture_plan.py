"""Dependency planning for the D07 chromatin operation graph."""

from __future__ import annotations

from .chromatin_architecture_contracts import (
    ChromatinArchitectureFixture,
    ChromatinArchitecturePlan,
    ChromatinArchitecturePlanNode,
    addressed,
)


def compile_chromatin_architecture_plan(
    fixture: ChromatinArchitectureFixture,
) -> ChromatinArchitecturePlan:
    """Compile a deterministic, source-aware topological plan."""

    nodes = tuple(
        ChromatinArchitecturePlanNode(
            operation_id=operation.operation_id,
            ordinal=operation.ordinal,
            dependencies=operation.dependencies,
            family=operation.family,
            plane=operation.plane,
            ready=all(dependency in fixture.operation_ids for dependency in operation.dependencies)
            and set(operation.source_ids) <= {source.source_id for source in fixture.sources},
            detail=(
                "operation is ready after declared predecessor and source joins resolve"
                if operation.dependencies
                else "first operation is ready from its source joins"
            ),
            content_address=addressed(
                {
                    "operation_id": operation.operation_id,
                    "ordinal": operation.ordinal,
                    "dependencies": operation.dependencies,
                    "family": operation.family,
                    "plane": operation.plane,
                    "ready": True,
                },
                "chromatin-plan-node",
            ),
        )
        for operation in fixture.operations
    )
    body = {"fixture_id": fixture.fixture_id, "nodes": nodes}
    return ChromatinArchitecturePlan(
        fixture_id=fixture.fixture_id,
        nodes=nodes,
        accepted=bool(nodes) and all(item.ready for item in nodes),
        content_address=addressed(body, "chromatin-plan"),
    )


__all__ = ["compile_chromatin_architecture_plan"]
