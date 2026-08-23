"""Dependency plan and schedule checks for the D01 intake operations."""

from __future__ import annotations

from .intake_architecture_contracts import (
    IntakeArchitectureFixture,
    IntakeArchitecturePlan,
    IntakeArchitecturePlanNode,
    addressed,
)


def compile_intake_architecture_plan(fixture: IntakeArchitectureFixture) -> IntakeArchitecturePlan:
    nodes = tuple(
        IntakeArchitecturePlanNode(
            operation_id=spec.operation_id,
            ordinal=spec.ordinal,
            dependencies=spec.dependencies,
            contract=f"{spec.input_contract}->{spec.output_contract}",
            content_address=addressed({"operation_id": spec.operation_id, "dependencies": spec.dependencies}, "intake-plan-node"),
        )
        for spec in fixture.operations
    )
    issues: list[str] = []
    ids = {node.operation_id for node in nodes}
    for node in nodes:
        if any(dependency not in ids for dependency in node.dependencies):
            issues.append(f"missing_dependency:{node.operation_id}")
        if node.dependencies and node.dependencies[0] >= node.operation_id:
            issues.append(f"non_monotonic_dependency:{node.operation_id}")
    if tuple(node.ordinal for node in nodes) != tuple(range(1, len(nodes) + 1)):
        issues.append("ordinal_gap")
    body = {"plan_id": "intake-plan-d01", "nodes": nodes, "accepted": not issues, "issues": tuple(sorted(set(issues)))}
    return IntakeArchitecturePlan(**body, content_address=addressed(body, "intake-plan"))


def audit_intake_architecture_plan(plan: IntakeArchitecturePlan) -> tuple[str, ...]:
    issues = list(plan.issues)
    if len({node.operation_id for node in plan.nodes}) != len(plan.nodes):
        issues.append("duplicate_operation_id")
    if any(":" not in node.content_address for node in plan.nodes):
        issues.append("unaddressed_plan_node")
    return tuple(sorted(set(issues)))


__all__ = ["compile_intake_architecture_plan", "audit_intake_architecture_plan"]
