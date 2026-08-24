"""Dependency-safe operation plan for D14 evidence architecture."""

from __future__ import annotations

from .evidence_architecture_contracts import (
    EvidenceArchitectureFixture,
    EvidenceArchitecturePlan,
    EvidenceArchitecturePlanNode,
    addressed,
)
from .evidence_architecture_public_data import default_evidence_architecture_fixture


def build_evidence_architecture_plan(
    fixture: EvidenceArchitectureFixture | None = None,
) -> EvidenceArchitecturePlan:
    selected = fixture or default_evidence_architecture_fixture()
    nodes = tuple(
        EvidenceArchitecturePlanNode(
            operation.operation_id,
            operation.ordinal,
            operation.dependencies,
            operation.family,
            operation.plane,
            all(
                dependency
                in {prior.operation_id for prior in selected.operations[: operation.ordinal - 1]}
                for dependency in operation.dependencies
            ),
            (
                f"{operation.operation_id} consumes {operation.input_contract} "
                f"and emits {operation.output_contract}"
            ),
            addressed(
                {
                    "operation": operation.operation_id,
                    "ordinal": operation.ordinal,
                    "dependencies": operation.dependencies,
                },
                "evidence-architecture-plan-node",
            ),
        )
        for operation in selected.operations
    )
    body = {"fixture_id": selected.fixture_id, "nodes": nodes}
    return EvidenceArchitecturePlan(
        selected.fixture_id,
        nodes,
        bool(nodes) and all(item.ready for item in nodes),
        addressed(body, "evidence-architecture-plan"),
    )


def evidence_architecture_plan_order(
    plan: EvidenceArchitecturePlan,
) -> tuple[str, ...]:
    return tuple(item.operation_id for item in plan.nodes)


def evidence_architecture_plan_summary(
    plan: EvidenceArchitecturePlan,
) -> dict[str, object]:
    return {
        "fixture_id": plan.fixture_id,
        "node_count": len(plan.nodes),
        "accepted": plan.accepted,
        "operation_order": evidence_architecture_plan_order(plan),
        "dependency_count": sum(len(item.dependencies) for item in plan.nodes),
    }


__all__ = [
    "build_evidence_architecture_plan",
    "evidence_architecture_plan_order",
    "evidence_architecture_plan_summary",
]
