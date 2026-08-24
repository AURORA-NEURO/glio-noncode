"""D12 dependency planning across cohort evidence planes."""

from __future__ import annotations

from .cohort_architecture_contracts import (
    CohortArchitectureFixture,
    CohortArchitecturePlan,
    CohortArchitecturePlanNode,
    addressed,
)


def build_cohort_architecture_plan(fixture: CohortArchitectureFixture) -> CohortArchitecturePlan:
    nodes = []
    known: set[str] = set()
    for operation in fixture.operations:
        ready = set(operation.dependencies) <= known and bool(operation.source_ids)
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
            CohortArchitecturePlanNode(
                **body,
                content_address=addressed(body, "cohort-plan-node"),
            )
        )
        if ready:
            known.add(operation.operation_id)
    body = {"fixture_id": fixture.fixture_id, "nodes": tuple(nodes)}
    return CohortArchitecturePlan(
        fixture.fixture_id,
        tuple(nodes),
        len(nodes) == 16 and all(item.ready for item in nodes),
        addressed(body, "cohort-plan"),
    )


def cohort_architecture_operation_order(
    plan: CohortArchitecturePlan,
) -> tuple[str, ...]:
    return tuple(item.operation_id for item in sorted(plan.nodes, key=lambda item: item.ordinal))


__all__ = ["build_cohort_architecture_plan", "cohort_architecture_operation_order"]
