"""Partition rows by capability for independent review ownership."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleasePartitionReport:
    partitions: dict[str, tuple[str, ...]]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_partitions(evaluation: Any) -> EvidenceReleasePartitionReport:
    partitions: dict[str, list[str]] = {}
    for item in evaluation.executions:
        partitions.setdefault(item.capability, []).append(item.record_id)
    body = {"partitions": {key: tuple(sorted(value)) for key, value in sorted(partitions.items())}, "accepted": len(partitions) == 4 and sum(map(len, partitions.values())) == len(evaluation.executions)}
    return EvidenceReleasePartitionReport(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleasePartitionReport", "build_evidence_release_partitions"]
