"""Deterministic dependency plan for the sixteen specimen operations."""

from __future__ import annotations

from .specimen_architecture_contracts import (
    SpecimenArchitectureFixture,
    SpecimenArchitecturePlan,
    SpecimenArchitecturePlanNode,
    addressed,
)


def compile_specimen_architecture_plan(
    fixture: SpecimenArchitectureFixture,
) -> SpecimenArchitecturePlan:
    """Compile operation specs into an ordered, replayable execution plan."""

    nodes: list[SpecimenArchitecturePlanNode] = []
    for operation in sorted(fixture.operations, key=lambda item: item.ordinal):
        inputs = tuple(f"source:{source_id}" for source_id in operation.source_ids) + tuple(
            f"receipt:{dependency}" for dependency in operation.dependencies
        )
        outputs = (
            f"receipt:{operation.operation_id}",
            f"lineage:{operation.operation_id}",
        )
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
            SpecimenArchitecturePlanNode(
                operation_id=operation.operation_id,
                capability_id=operation.capability_id,
                ordinal=operation.ordinal,
                dependencies=operation.dependencies,
                inputs=inputs,
                outputs=outputs,
                ready=True,
                content_address=addressed(body, "specimen-plan-node"),
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
    body = {"fixture_id": fixture.fixture_id, "nodes": nodes, "accepted": accepted}
    return SpecimenArchitecturePlan(
        fixture_id=fixture.fixture_id,
        nodes=tuple(nodes),
        accepted=accepted,
        content_address=addressed(body, "specimen-plan"),
    )


__all__ = ["compile_specimen_architecture_plan"]
