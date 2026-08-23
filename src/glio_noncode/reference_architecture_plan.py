"""Deterministic 16-node dependency plan for D04 reference operations."""

from __future__ import annotations

from .reference_architecture_contracts import (
    ReferenceArchitectureFixture,
    ReferenceArchitecturePlan,
    ReferenceArchitecturePlanNode,
    addressed,
)


def compile_reference_architecture_plan(
    fixture: ReferenceArchitectureFixture,
) -> ReferenceArchitecturePlan:
    """Compile operation specs into ordered source and receipt dependencies."""

    nodes: list[ReferenceArchitecturePlanNode] = []
    for operation in sorted(fixture.operations, key=lambda item: item.ordinal):
        inputs = tuple(f"source:{source_id}" for source_id in operation.source_ids) + tuple(
            f"receipt:{dependency}" for dependency in operation.dependencies
        )
        outputs = (f"receipt:{operation.operation_id}", f"lineage:{operation.operation_id}")
        body = {
            "operation_id": operation.operation_id,
            "capability_id": operation.capability_id,
            "ordinal": operation.ordinal,
            "dependencies": operation.dependencies,
            "inputs": inputs,
            "outputs": outputs,
            "ready": True,
        }
        nodes.append(
            ReferenceArchitecturePlanNode(
                operation.operation_id,
                operation.capability_id,
                operation.ordinal,
                operation.dependencies,
                inputs,
                outputs,
                True,
                addressed(body, "reference-plan-node"),
            )
        )
    accepted = (
        len(nodes) == 16
        and tuple(node.ordinal for node in nodes) == tuple(range(1, 17))
        and all(
            dependency in {node.operation_id for node in nodes[:index]}
            for index, node in enumerate(nodes)
            for dependency in node.dependencies
        )
    )
    return ReferenceArchitecturePlan(
        fixture.fixture_id,
        tuple(nodes),
        accepted,
        addressed(
            {"fixture_id": fixture.fixture_id, "nodes": nodes, "accepted": accepted},
            "reference-plan",
        ),
    )


__all__ = ["compile_reference_architecture_plan"]
