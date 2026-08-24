"""D12 aggregate schema and join validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .cohort_architecture_contracts import (
    COHORT_ARCHITECTURE_BOUNDARY,
    COHORT_ARCHITECTURE_CONTEXT,
    CohortArchitectureFamily,
    CohortArchitectureFixture,
)
from .errors import ValidationError
from .serialization import jsonable

COHORT_ARCHITECTURE_SCHEMA_ID = "cohort-architecture.aggregate.v1"
COHORT_ARCHITECTURE_REQUIRED_FIELDS = (
    "fixture_id",
    "version",
    "boundary",
    "context_key",
    "foreign_context_key",
    "family_contexts",
    "sources",
    "operations",
    "cases",
    "content_address",
)


def normalize_cohort_architecture_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValidationError("D12 mapping must be an object")
    result = {str(key): jsonable(value) for key, value in raw.items()}
    missing = [key for key in COHORT_ARCHITECTURE_REQUIRED_FIELDS if key not in result]
    if missing:
        raise ValidationError(f"D12 mapping is missing: {', '.join(missing)}")
    return result


def validate_cohort_architecture_mapping(raw: Mapping[str, Any]) -> tuple[str, ...]:
    value = normalize_cohort_architecture_mapping(raw)
    errors = []
    if value["boundary"] != COHORT_ARCHITECTURE_BOUNDARY:
        errors.append("boundary")
    if value["context_key"] != COHORT_ARCHITECTURE_CONTEXT:
        errors.append("context_key")
    if len(value["family_contexts"]) != 4:
        errors.append("family_contexts")
    for field, expected in (("sources", 22), ("operations", 16), ("cases", 64)):
        if len(value[field]) != expected:
            errors.append(field)
    return tuple(errors)


def validate_cohort_architecture_fixture(fixture: CohortArchitectureFixture) -> bool:
    if not isinstance(fixture, CohortArchitectureFixture):
        raise ValidationError("D12 fixture type is required")
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    if any(set(item.source_ids) - source_ids for item in (*fixture.operations, *fixture.cases)):
        raise ValidationError("D12 source join is unresolved")
    if any(item.operation_id not in operation_ids for item in fixture.cases):
        raise ValidationError("D12 operation join is unresolved")
    return True


def cohort_architecture_schema_descriptor() -> dict[str, object]:
    return {
        "schema_id": COHORT_ARCHITECTURE_SCHEMA_ID,
        "boundary": COHORT_ARCHITECTURE_BOUNDARY,
        "context_key": COHORT_ARCHITECTURE_CONTEXT,
        "source_count": 22,
        "operation_count": 16,
        "case_count": 64,
        "cases_per_operation": 4,
        "families": [
            item.value for item in CohortArchitectureFamily
        ],
        "scenarios": ["positive", "control_a", "control_b", "control_c"],
    }


__all__ = [
    "COHORT_ARCHITECTURE_REQUIRED_FIELDS",
    "COHORT_ARCHITECTURE_SCHEMA_ID",
    "cohort_architecture_schema_descriptor",
    "normalize_cohort_architecture_mapping",
    "validate_cohort_architecture_fixture",
    "validate_cohort_architecture_mapping",
]
