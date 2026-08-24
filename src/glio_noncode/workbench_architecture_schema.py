"""D15 aggregate schema descriptors and typed join validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .serialization import jsonable
from .workbench_architecture_contracts import (
    WORKBENCH_ARCHITECTURE_BOUNDARY,
    WORKBENCH_ARCHITECTURE_CASE_COUNT,
    WORKBENCH_ARCHITECTURE_CASES_PER_OPERATION,
    WORKBENCH_ARCHITECTURE_CONTEXT,
    WORKBENCH_ARCHITECTURE_OPERATION_COUNT,
    WORKBENCH_ARCHITECTURE_SOURCE_COUNT,
    WorkbenchArchitectureFamily,
    WorkbenchArchitectureFixture,
)

WORKBENCH_ARCHITECTURE_SCHEMA_ID = "workbench-architecture.aggregate.v1"
WORKBENCH_ARCHITECTURE_REQUIRED_FIELDS = (
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


def normalize_workbench_architecture_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValidationError("D15 mapping must be an object")
    result = {str(key): jsonable(value) for key, value in raw.items()}
    missing = [key for key in WORKBENCH_ARCHITECTURE_REQUIRED_FIELDS if key not in result]
    if missing:
        raise ValidationError(f"D15 mapping is missing: {', '.join(missing)}")
    return result


def validate_workbench_architecture_mapping(raw: Mapping[str, Any]) -> tuple[str, ...]:
    value = normalize_workbench_architecture_mapping(raw)
    errors = []
    if value["boundary"] != WORKBENCH_ARCHITECTURE_BOUNDARY:
        errors.append("boundary")
    if value["context_key"] != WORKBENCH_ARCHITECTURE_CONTEXT:
        errors.append("context_key")
    if len(value["family_contexts"]) != len(WorkbenchArchitectureFamily):
        errors.append("family_contexts")
    for field, expected in (
        ("sources", WORKBENCH_ARCHITECTURE_SOURCE_COUNT),
        ("operations", WORKBENCH_ARCHITECTURE_OPERATION_COUNT),
        ("cases", WORKBENCH_ARCHITECTURE_CASE_COUNT),
    ):
        if len(value[field]) != expected:
            errors.append(field)
    return tuple(errors)


def validate_workbench_architecture_fixture(fixture: WorkbenchArchitectureFixture) -> bool:
    if not isinstance(fixture, WorkbenchArchitectureFixture):
        raise ValidationError("D15 fixture type is required")
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    if any(set(item.source_ids) - source_ids for item in (*fixture.operations, *fixture.cases)):
        raise ValidationError("D15 source join is unresolved")
    if any(item.operation_id not in operation_ids for item in fixture.cases):
        raise ValidationError("D15 operation join is unresolved")
    if tuple(item.ordinal for item in fixture.operations) != tuple(
        range(1, WORKBENCH_ARCHITECTURE_OPERATION_COUNT + 1)
    ):
        raise ValidationError("D15 operation ordinals are not contiguous")
    if any(
        len([case for case in fixture.cases if case.operation_id == item.operation_id])
        != WORKBENCH_ARCHITECTURE_CASES_PER_OPERATION
        for item in fixture.operations
    ):
        raise ValidationError("D15 operation case balance is not closed")
    return True


def workbench_architecture_schema_descriptor() -> dict[str, object]:
    return {
        "schema_id": WORKBENCH_ARCHITECTURE_SCHEMA_ID,
        "boundary": WORKBENCH_ARCHITECTURE_BOUNDARY,
        "context_key": WORKBENCH_ARCHITECTURE_CONTEXT,
        "source_count": WORKBENCH_ARCHITECTURE_SOURCE_COUNT,
        "operation_count": WORKBENCH_ARCHITECTURE_OPERATION_COUNT,
        "case_count": WORKBENCH_ARCHITECTURE_CASE_COUNT,
        "cases_per_operation": WORKBENCH_ARCHITECTURE_CASES_PER_OPERATION,
        "families": [item.value for item in WorkbenchArchitectureFamily],
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
    "WORKBENCH_ARCHITECTURE_REQUIRED_FIELDS",
    "WORKBENCH_ARCHITECTURE_SCHEMA_ID",
    "normalize_workbench_architecture_mapping",
    "validate_workbench_architecture_mapping",
    "validate_workbench_architecture_fixture",
    "workbench_architecture_schema_descriptor",
]
