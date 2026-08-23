"""Stable partitions for positive, control, and operation projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierPartition:
    partition_id: str
    record_ids: tuple[str, ...]
    predicate: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierPartitionReport:
    partitions: tuple[DeploymentFrontierPartition, ...]
    disjoint: bool
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_partitions(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierPartitionReport:
    definitions = (("positive", lambda item: item.role.value == "positive"), ("control", lambda item: item.role.value == "control"), ("ready", lambda item: item.state.value in {"ready", "released"}), ("review", lambda item: bool(item.issue_codes)))
    partitions = []
    for partition_id, predicate in definitions:
        ids = tuple(item.record_id for item in evaluation.executions if predicate(item))
        body = {"partition_id": partition_id, "record_ids": ids, "predicate": partition_id}
        partitions.append(DeploymentFrontierPartition(**body, content_address=deployment_address(body)))
    all_ids = set(item.record_id for item in evaluation.executions)
    base = [item.record_id for item in partitions[0].record_ids + partitions[1].record_ids]
    return DeploymentFrontierPartitionReport(tuple(partitions), len(base) == len(set(base)), set(base) == all_ids, deployment_address(tuple(partitions)))


__all__ = ["DeploymentFrontierPartition", "DeploymentFrontierPartitionReport", "build_deployment_frontier_partitions"]
