"""Deterministic partitions for operation and role-oriented review slices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation, TopologyAlphaFrontierEvaluationRow


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierPartition:
    partition_id: str
    dimension: str
    value: str
    record_ids: tuple[str, ...]
    row_count: int
    review_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierPartitionReport:
    partitions: tuple[TopologyAlphaFrontierPartition, ...]
    dimensions: tuple[str, ...]
    covered_record_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_dimension(self, dimension: str) -> tuple[TopologyAlphaFrontierPartition, ...]:
        return tuple(item for item in self.partitions if item.dimension == dimension)

    def find(self, dimension: str, value: str) -> TopologyAlphaFrontierPartition:
        for item in self.partitions:
            if item.dimension == dimension and item.value == value:
                return item
        raise KeyError((dimension, value))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"partitions": [item.to_dict() for item in self.partitions], "dimensions": self.dimensions, "covered_record_count": self.covered_record_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _partition(dimension: str, value: str, rows: tuple[TopologyAlphaFrontierEvaluationRow, ...]) -> TopologyAlphaFrontierPartition:
    ids = tuple(item.record_id for item in rows)
    return TopologyAlphaFrontierPartition(f"{dimension}:{value}", dimension, value, ids, len(ids), sum(item.role == "control" for item in rows), content_hash({"dimension": dimension, "value": value, "record_ids": ids}))


def build_topology_alpha_frontier_partitions(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierPartitionReport:
    dimensions = ("operation", "role", "state")
    partitions = []
    for dimension in dimensions:
        values = sorted({getattr(row, "operation" if dimension == "operation" else "role" if dimension == "role" else "observed_state") for row in evaluation.rows})
        for value in values:
            rows = tuple(row for row in evaluation.rows if (row.operation if dimension == "operation" else row.role if dimension == "role" else row.observed_state) == value)
            partitions.append(_partition(dimension, value, rows))
    values = tuple(partitions)
    return TopologyAlphaFrontierPartitionReport(values, dimensions, len({record_id for item in values for record_id in item.record_ids}), len(values) == 10 and all(item.content_address.startswith("sha256:") for item in values))


__all__ = ["TopologyAlphaFrontierPartition", "TopologyAlphaFrontierPartitionReport", "build_topology_alpha_frontier_partitions"]
