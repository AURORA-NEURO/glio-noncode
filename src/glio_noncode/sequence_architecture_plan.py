"""Dependency plan for D06 sequence operations."""

from __future__ import annotations

from .sequence_architecture_contracts import (
    SequenceArchitectureFixture,
    SequenceArchitecturePlan,
    SequenceArchitecturePlanNode,
    addressed,
)


def compile_sequence_architecture_plan(
    fixture: SequenceArchitectureFixture,
) -> SequenceArchitecturePlan:
    nodes = tuple(
        SequenceArchitecturePlanNode(
            operation_id=item.operation_id,
            capability_id=item.capability_id,
            ordinal=item.ordinal,
            dependencies=item.dependencies,
            inputs=item.source_ids,
            outputs=(f"{item.operation_id}.receipt", f"{item.operation_id}.lineage"),
            ready=all(
                any(previous.operation_id == dependency for previous in fixture.operations)
                for dependency in item.dependencies
            ),
            content_address=addressed(
                {
                    "operation_id": item.operation_id,
                    "dependencies": item.dependencies,
                    "inputs": item.source_ids,
                    "outputs": (f"{item.operation_id}.receipt", f"{item.operation_id}.lineage"),
                },
                "sequence-plan-node",
            ),
        )
        for item in fixture.operations
    )
    accepted = (
        len(nodes) == 16
        and tuple(item.ordinal for item in nodes) == tuple(range(1, 17))
        and all(item.ready for item in nodes[1:])
    )
    body = {"fixture_id": fixture.fixture_id, "nodes": nodes, "accepted": accepted}
    return SequenceArchitecturePlan(
        fixture_id=fixture.fixture_id,
        nodes=nodes,
        accepted=accepted,
        content_address=addressed(body, "sequence-plan"),
    )


__all__ = ["compile_sequence_architecture_plan"]
