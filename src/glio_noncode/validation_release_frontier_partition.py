"""Deterministic operation partitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleasePartition:
    operation: str
    record_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleasePartitionReport:
    partitions: tuple[ValidationReleasePartition, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_partitions(evaluation: ValidationReleaseEvaluation) -> ValidationReleasePartitionReport:
    rows = []
    for operation in sorted({item.operation.value for item in evaluation.executions}):
        ids = tuple(sorted(item.record_id for item in evaluation.executions if item.operation.value == operation))
        body = {"operation": operation, "record_ids": ids}
        rows.append(ValidationReleasePartition(**body, content_address=content_hash(body)))
    return ValidationReleasePartitionReport(tuple(rows), len(rows) == 4, content_hash(tuple(rows)))


__all__ = ["ValidationReleasePartition", "ValidationReleasePartitionReport", "build_validation_release_partitions"]
