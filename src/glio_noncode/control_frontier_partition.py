"""Deterministic partitions for review, metrics, and release projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierOperation, ControlFrontierRole, ControlFrontierState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierPartition:
    partition_id: str
    operation: ControlFrontierOperation
    role: ControlFrontierRole
    record_ids: tuple[str, ...]
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    accepted_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierPartitionReport:
    fixture_id: str
    partitions: tuple[ControlFrontierPartition, ...]
    partition_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_partitions(evaluation: ControlFrontierEvaluation) -> ControlFrontierPartitionReport:
    """Build one positive and one control partition for each operation."""

    partitions = []
    for operation in ControlFrontierOperation:
        for role in (ControlFrontierRole.POSITIVE, ControlFrontierRole.CONTROL):
            rows = tuple(item for item in evaluation.executions if item.operation is operation and item.role is role)
            state_counts = {state.value: sum(item.state is state for item in rows) for state in ControlFrontierState if any(item.state is state for item in rows)}
            issue_counts: dict[str, int] = {}
            for row in rows:
                for issue in row.issue_codes:
                    issue_counts[issue] = issue_counts.get(issue, 0) + 1
            body = {
                "partition_id": f"{operation.value}:{role.value}",
                "operation": operation,
                "role": role,
                "record_ids": tuple(item.record_id for item in rows),
                "state_counts": state_counts,
                "issue_counts": issue_counts,
                "accepted_count": sum(item.accepted for item in rows),
            }
            partitions.append(ControlFrontierPartition(**body, content_address=content_hash(body)))
    body = {"fixture_id": evaluation.fixture_id, "partitions": tuple(partitions), "partition_count": len(partitions), "accepted": len(partitions) == 16 and all(item.record_ids for item in partitions)}
    return ControlFrontierPartitionReport(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierPartition", "ControlFrontierPartitionReport", "build_control_frontier_partitions"]
