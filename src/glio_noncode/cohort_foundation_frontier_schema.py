"""Field-level schema closure for the public C01-C04 aggregate fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_public_data import CohortFoundationOperation


@dataclass(frozen=True, slots=True)
class CohortFoundationSchemaCheck:
    operation: CohortFoundationOperation
    required_fields: tuple[str, ...]
    typed_fields: tuple[tuple[str, str], ...]
    context_required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationSchemaReport:
    schema_id: str
    version: str
    checks: tuple[CohortFoundationSchemaCheck, ...]
    accepted: bool
    content_address: str

    def by_operation(self, operation: CohortFoundationOperation) -> CohortFoundationSchemaCheck:
        return next(item for item in self.checks if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_foundation_frontier_schema() -> CohortFoundationSchemaReport:
    definitions = (
        (CohortFoundationOperation.COHORT_QUERY, ("query_id", "rows", "context_key"), (("query_id", "str"), ("rows", "list"), ("context_key", "str"))),
        (CohortFoundationOperation.BACKGROUND_RATE, ("background_records", "callable_intervals", "target_callable_bases"), (("background_records", "list"), ("callable_intervals", "list"), ("target_callable_bases", "positive_int"))),
        (CohortFoundationOperation.SEQUENCE_CONTROL, ("target", "candidates", "max_controls", "max_distance"), (("target", "object"), ("candidates", "list"), ("max_controls", "positive_int"), ("max_distance", "unit_interval"))),
        (CohortFoundationOperation.CHROMATIN_CONTROL, ("target", "candidates", "feature_ranges", "max_controls", "max_distance"), (("target", "object"), ("candidates", "list"), ("feature_ranges", "object"), ("max_controls", "positive_int"), ("max_distance", "nonnegative_float"))),
    )
    checks = tuple(
        CohortFoundationSchemaCheck(operation, fields, typed, True, content_hash((operation, fields, typed, True)))
        for operation, fields, typed in definitions
    )
    body = {"schema_id": "cohort-foundation-frontier-schema", "version": "1.0.0", "checks": checks}
    return CohortFoundationSchemaReport(body["schema_id"], body["version"], checks, True, content_hash(body))


def validate_cohort_foundation_frontier_schema(report: CohortFoundationSchemaReport | None = None) -> bool:
    value = report or default_cohort_foundation_frontier_schema()
    return value.accepted and len(value.checks) == len(CohortFoundationOperation) and all(item.context_required for item in value.checks)


__all__ = [
    "CohortFoundationSchemaCheck",
    "CohortFoundationSchemaReport",
    "default_cohort_foundation_frontier_schema",
    "validate_cohort_foundation_frontier_schema",
]
