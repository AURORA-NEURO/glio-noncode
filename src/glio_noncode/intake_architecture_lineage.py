"""Operation-to-receipt lineage projections for D01 review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .intake_architecture_contracts import IntakeArchitectureRuntime, addressed


@dataclass(frozen=True, slots=True)
class IntakeArchitectureLineageNode:
    node_id: str
    node_kind: str
    operation_id: str
    address: str
    parent_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "operation_id": self.operation_id,
            "address": self.address,
            "parent_ids": list(self.parent_ids),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class IntakeArchitectureLineage:
    lineage_id: str
    nodes: tuple[IntakeArchitectureLineageNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {"lineage_id": self.lineage_id, "nodes": [item.to_dict() for item in self.nodes], "accepted": self.accepted, "content_address": self.content_address}


def build_intake_architecture_lineage(runtime: IntakeArchitectureRuntime) -> IntakeArchitectureLineage:
    nodes: list[IntakeArchitectureLineageNode] = []
    previous_operation: str | None = None
    for result in runtime.evaluation.results:
        operation_node_id = f"operation:{result.operation_id}"
        if not any(item.node_id == operation_node_id for item in nodes):
            body = {"node_id": operation_node_id, "node_kind": "operation", "operation_id": result.operation_id, "address": result.content_address, "parent_ids": (previous_operation,) if previous_operation else ()}
            nodes.append(IntakeArchitectureLineageNode(**body, content_address=addressed(body, "intake-lineage-node")))
            previous_operation = operation_node_id
        for receipt_address in result.receipt_addresses:
            body = {"node_id": f"receipt:{result.case_id}", "node_kind": "receipt", "operation_id": result.operation_id, "address": receipt_address, "parent_ids": (operation_node_id,)}
            nodes.append(IntakeArchitectureLineageNode(**body, content_address=addressed(body, "intake-lineage-node")))
    body = {"lineage_id": "intake-lineage-d01", "nodes": tuple(nodes), "accepted": len(nodes) >= 16 and all(item.parent_ids or item.node_kind == "operation" for item in nodes)}
    return IntakeArchitectureLineage(**body, content_address=addressed(body, "intake-lineage"))


def verify_intake_architecture_lineage(lineage: IntakeArchitectureLineage) -> tuple[str, ...]:
    ids = {item.node_id for item in lineage.nodes}
    issues = []
    if len(ids) != len(lineage.nodes):
        issues.append("duplicate_node")
    if any(parent not in ids for item in lineage.nodes for parent in item.parent_ids):
        issues.append("missing_parent")
    if any(":" not in item.address for item in lineage.nodes):
        issues.append("unaddressed_node")
    return tuple(sorted(set(issues)))


__all__ = ["IntakeArchitectureLineageNode", "IntakeArchitectureLineage", "build_intake_architecture_lineage", "verify_intake_architecture_lineage"]
