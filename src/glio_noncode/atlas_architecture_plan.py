"""Deterministic dependency plan for the sixteen D05 atlas operations."""

from __future__ import annotations

from .atlas_architecture_contracts import (
    AtlasArchitectureFixture,
    AtlasArchitecturePlan,
    AtlasArchitecturePlanNode,
    addressed,
)


def compile_atlas_architecture_plan(fixture: AtlasArchitectureFixture) -> AtlasArchitecturePlan:
    """Compile operation order and require every dependency to be earlier."""

    nodes = tuple(
        AtlasArchitecturePlanNode(
            operation_id=spec.operation_id,
            capability_id=spec.capability_id,
            ordinal=spec.ordinal,
            dependencies=spec.dependencies,
            inputs=(spec.input_contract, *spec.source_ids),
            outputs=(spec.output_contract, "atlas_architecture.case_receipt"),
            ready=all(
                dependency in {item.operation_id for item in fixture.operations[: spec.ordinal - 1]}
                for dependency in spec.dependencies
            ),
            content_address=addressed(
                {
                    "operation_id": spec.operation_id,
                    "ordinal": spec.ordinal,
                    "dependencies": spec.dependencies,
                    "inputs": (spec.input_contract, *spec.source_ids),
                    "outputs": (spec.output_contract, "atlas_architecture.case_receipt"),
                },
                "atlas-plan-node",
            ),
        )
        for spec in fixture.operations
    )
    accepted = (
        len(nodes) == 16
        and tuple(item.ordinal for item in nodes) == tuple(range(1, 17))
        and all(item.ready for item in nodes)
    )
    body = {"fixture_id": fixture.fixture_id, "nodes": nodes, "accepted": accepted}
    return AtlasArchitecturePlan(
        fixture.fixture_id,
        nodes,
        accepted,
        addressed(body, "atlas-plan"),
    )


__all__ = ["compile_atlas_architecture_plan"]
