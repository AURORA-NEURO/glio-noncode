"""Publication partitions derived from explicit policy dispositions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierDisposition, CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPartition:
    name: str
    record_ids: tuple[str, ...]
    count: int
    rule: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPartitionSet:
    partitions: tuple[CohortAlphaFrontierPartition, ...]
    total_count: int
    disjoint: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_partitions(policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierPartitionSet:
    partitions = []
    for disposition in CohortAlphaFrontierDisposition:
        ids = tuple(item.record_id for item in policy.decisions if item.disposition is disposition)
        rule = "supported exact-context only" if disposition is CohortAlphaFrontierDisposition.PUBLISH else "retain evidence boundary before publication"
        partitions.append(CohortAlphaFrontierPartition(disposition.value, ids, len(ids), rule, content_hash({"name": disposition.value, "ids": ids, "rule": rule}, prefix="alpha-partition")))
    values = tuple(partitions)
    all_ids = [record_id for item in values for record_id in item.record_ids]
    return CohortAlphaFrontierPartitionSet(values, len(all_ids), len(all_ids) == len(set(all_ids)), len(all_ids) == len(policy.decisions) and len(values) == 3, content_hash(values, prefix="alpha-partitions"))


__all__ = ["CohortAlphaFrontierPartition", "CohortAlphaFrontierPartitionSet", "build_cohort_alpha_frontier_partitions"]
