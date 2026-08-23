"""Typed, deterministic coordination tool registry."""

from __future__ import annotations

from typing import Any

from .coordination_architecture_contracts import (
    CoordinationFixture,
    CoordinationToolRegistry,
    CoordinationToolSpec,
    addressed,
)


def build_coordination_tool_registry(fixture: CoordinationFixture) -> CoordinationToolRegistry:
    tools = []
    for spec in fixture.operations:
        body = {
            "tool_id": f"coordination-tool:{spec.operation_id}",
            "operation_id": spec.operation_id,
            "input_contract": spec.input_contract,
            "output_contract": spec.output_contract,
            "deterministic": True,
            "network_allowed": False,
            "public_aggregate_only": True,
        }
        tools.append(CoordinationToolSpec(**body, content_address=addressed(body, "coordination-tool")))
    issues: list[str] = []
    operation_ids = {item.operation_id for item in fixture.operations}
    if len(tools) != len(operation_ids):
        issues.append("tool_cardinality_mismatch")
    if any(item.operation_id not in operation_ids for item in tools):
        issues.append("tool_operation_missing")
    if any(not item.deterministic or item.network_allowed or not item.public_aggregate_only for item in tools):
        issues.append("tool_boundary_mismatch")
    body: dict[str, Any] = {
        "registry_id": f"{fixture.fixture_id}:tools",
        "tools": tuple(tools),
        "accepted": not issues,
        "issues": tuple(sorted(set(issues))),
    }
    return CoordinationToolRegistry(**body, content_address=addressed(body, "coordination-tool-registry"))


def validate_coordination_tool_registry(registry: CoordinationToolRegistry, expected_count: int = 16) -> tuple[str, ...]:
    issues: list[str] = list(registry.issues)
    if len(registry.tools) != expected_count:
        issues.append("tool_count_mismatch")
    if len({item.tool_id for item in registry.tools}) != len(registry.tools):
        issues.append("duplicate_tool_id")
    if any(item.network_allowed or not item.public_aggregate_only for item in registry.tools):
        issues.append("unsafe_tool_boundary")
    return tuple(sorted(set(issues)))


__all__ = ["build_coordination_tool_registry", "validate_coordination_tool_registry"]
