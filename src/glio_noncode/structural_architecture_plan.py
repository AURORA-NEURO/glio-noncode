"""Dependency plan and operation registry for C01-C16."""

from __future__ import annotations

from collections.abc import Iterable

from .structural_architecture_contracts import (
    StructuralArchitectureFixture,
    StructuralArchitecturePlan,
    StructuralArchitecturePlanNode,
    addressed,
)


def compile_structural_architecture_plan(
    fixture: StructuralArchitectureFixture,
) -> StructuralArchitecturePlan:
    """Compile a topologically ordered plan from the closed fixture specs."""

    declared = {item.operation_id for item in fixture.operations}
    seen: set[str] = set()
    nodes: list[StructuralArchitecturePlanNode] = []
    for spec in sorted(fixture.operations, key=lambda item: item.ordinal):
        dependencies = tuple(spec.dependencies)
        ready = (
            spec.operation_id in declared
            and all(dependency in seen for dependency in dependencies)
            and all(source_id in fixture.source_ids for source_id in spec.source_ids)
        )
        body = {
            "operation_id": spec.operation_id,
            "capability_id": spec.capability_id,
            "ordinal": spec.ordinal,
            "dependencies": dependencies,
            "inputs": tuple(f"source:{source_id}" for source_id in spec.source_ids),
            "outputs": (f"result:{spec.operation_id}", f"receipt:{spec.capability_id}"),
            "ready": ready,
        }
        nodes.append(
            StructuralArchitecturePlanNode(
                **body, content_address=addressed(body, "structural-plan-node")
            )
        )
        if ready:
            seen.add(spec.operation_id)
    accepted = (
        len(nodes) == len(fixture.operations)
        and all(item.ready for item in nodes)
        and _ordinals(nodes)
    )
    body = {"fixture_id": fixture.fixture_id, "nodes": nodes, "accepted": accepted}
    return StructuralArchitecturePlan(
        fixture_id=fixture.fixture_id,
        nodes=tuple(nodes),
        accepted=accepted,
        content_address=addressed(body, "structural-plan"),
    )


def plan_is_executable(plan: StructuralArchitecturePlan) -> bool:
    """Return whether every plan node is ready and dependency-ordered."""

    return plan.accepted and _ordinals(plan.nodes)


def _ordinals(nodes: Iterable[StructuralArchitecturePlanNode]) -> bool:
    values = tuple(nodes)
    return tuple(item.ordinal for item in values) == tuple(range(1, len(values) + 1))


__all__ = ["compile_structural_architecture_plan", "plan_is_executable"]
