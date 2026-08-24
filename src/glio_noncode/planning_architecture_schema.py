"""D13 aggregate schema descriptors and typed join validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .planning_architecture_contracts import (
    PLANNING_ARCHITECTURE_BOUNDARY,
    PLANNING_ARCHITECTURE_CONTEXT,
    PlanningArchitectureFamily,
    PlanningArchitectureFixture,
)
from .serialization import jsonable

PLANNING_ARCHITECTURE_SCHEMA_ID = "planning-architecture.aggregate.v1"
PLANNING_ARCHITECTURE_REQUIRED_FIELDS = (
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


def normalize_planning_architecture_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValidationError("D13 mapping must be an object")
    result = {str(key): jsonable(value) for key, value in raw.items()}
    missing = [key for key in PLANNING_ARCHITECTURE_REQUIRED_FIELDS if key not in result]
    if missing:
        raise ValidationError(f"D13 mapping is missing: {', '.join(missing)}")
    return result


def validate_planning_architecture_mapping(raw: Mapping[str, Any]) -> tuple[str, ...]:
    value = normalize_planning_architecture_mapping(raw)
    errors: list[str] = []
    if value["boundary"] != PLANNING_ARCHITECTURE_BOUNDARY:
        errors.append("boundary")
    if value["context_key"] != PLANNING_ARCHITECTURE_CONTEXT:
        errors.append("context_key")
    if len(value["family_contexts"]) != len(PlanningArchitectureFamily):
        errors.append("family_contexts")
    for field, expected in (("sources", 20), ("operations", 16), ("cases", 64)):
        if len(value[field]) != expected:
            errors.append(field)
    return tuple(errors)


def validate_planning_architecture_fixture(
    fixture: PlanningArchitectureFixture,
) -> bool:
    if not isinstance(fixture, PlanningArchitectureFixture):
        raise ValidationError("D13 fixture type is required")
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    if any(set(item.source_ids) - source_ids for item in (*fixture.operations, *fixture.cases)):
        raise ValidationError("D13 source join is unresolved")
    if any(item.operation_id not in operation_ids for item in fixture.cases):
        raise ValidationError("D13 operation join is unresolved")
    if tuple(item.ordinal for item in fixture.operations) != tuple(range(1, 17)):
        raise ValidationError("D13 operation ordinals are not contiguous")
    return True


def planning_architecture_schema_descriptor() -> dict[str, object]:
    return {
        "schema_id": PLANNING_ARCHITECTURE_SCHEMA_ID,
        "boundary": PLANNING_ARCHITECTURE_BOUNDARY,
        "context_key": PLANNING_ARCHITECTURE_CONTEXT,
        "source_count": 20,
        "operation_count": 16,
        "case_count": 64,
        "cases_per_operation": 4,
        "families": [item.value for item in PlanningArchitectureFamily],
        "scenarios": ["positive", "control_a", "control_b", "control_c"],
        "required_case_fields": [
            "operation_id",
            "family",
            "scenario",
            "delegate_record_id",
            "aggregate_context_key",
            "delegate_context_key",
            "expected_state",
            "expected_issue_codes",
            "expected_counts",
        ],
    }


__all__ = [
    "PLANNING_ARCHITECTURE_REQUIRED_FIELDS",
    "PLANNING_ARCHITECTURE_SCHEMA_ID",
    "normalize_planning_architecture_mapping",
    "planning_architecture_schema_descriptor",
    "validate_planning_architecture_fixture",
    "validate_planning_architecture_mapping",
]
