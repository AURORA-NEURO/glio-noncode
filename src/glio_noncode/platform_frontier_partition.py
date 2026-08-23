"""Operation and role partitions for platform review exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierOperation, PlatformFrontierRole
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierPartition:
    partition_id: str
    operation: PlatformFrontierOperation
    role: PlatformFrontierRole
    record_ids: tuple[str, ...]
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    accepted_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierPartitionReport:
    fixture_id: str
    partitions: tuple[PlatformFrontierPartition, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_partitions(evaluation: PlatformFrontierEvaluation) -> PlatformFrontierPartitionReport:
    partitions = []
    for operation in PlatformFrontierOperation:
        for role in (PlatformFrontierRole.POSITIVE, PlatformFrontierRole.CONTROL):
            rows = tuple(item for item in evaluation.executions if item.operation is operation and item.role is role)
            state_counts: dict[str, int] = {}
            issue_counts: dict[str, int] = {}
            for row in rows:
                state_counts[row.state.value] = state_counts.get(row.state.value, 0) + 1
                for issue in row.issue_codes:
                    issue_counts[issue] = issue_counts.get(issue, 0) + 1
            body = {"partition_id": f"{operation.value}:{role.value}", "operation": operation, "role": role, "record_ids": tuple(item.record_id for item in rows), "state_counts": state_counts, "issue_counts": issue_counts, "accepted_count": sum(item.accepted for item in rows)}
            partitions.append(PlatformFrontierPartition(**body, content_address=content_hash(body)))
    return PlatformFrontierPartitionReport(evaluation.fixture_id, tuple(partitions), len(partitions) == 8 and all(item.record_ids for item in partitions), content_hash(tuple(partitions)))


__all__ = ["PlatformFrontierPartition", "PlatformFrontierPartitionReport", "build_platform_frontier_partitions"]
