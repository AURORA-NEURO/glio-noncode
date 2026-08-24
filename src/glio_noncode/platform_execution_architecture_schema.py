"""D16 schema descriptors and join validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .platform_execution_architecture_contracts import (
    PLATFORM_EXECUTION_ARCHITECTURE_BOUNDARY,
    PLATFORM_EXECUTION_ARCHITECTURE_CASE_COUNT,
    PLATFORM_EXECUTION_ARCHITECTURE_CASES_PER_OPERATION,
    PLATFORM_EXECUTION_ARCHITECTURE_CONTEXT,
    PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT,
    PLATFORM_EXECUTION_ARCHITECTURE_SOURCE_COUNT,
    PlatformExecutionFamily,
    PlatformExecutionFixture,
)
from .serialization import jsonable

PLATFORM_EXECUTION_ARCHITECTURE_SCHEMA_ID = "platform-execution-architecture.aggregate.v1"
PLATFORM_EXECUTION_ARCHITECTURE_REQUIRED_FIELDS = (
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


def normalize_platform_execution_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValidationError("D16 mapping must be an object")
    value = {str(key): jsonable(child) for key, child in raw.items()}
    missing = [key for key in PLATFORM_EXECUTION_ARCHITECTURE_REQUIRED_FIELDS if key not in value]
    if missing:
        raise ValidationError(f"D16 mapping is missing: {', '.join(missing)}")
    return value


def validate_platform_execution_mapping(raw: Mapping[str, Any]) -> tuple[str, ...]:
    value = normalize_platform_execution_mapping(raw)
    errors = []
    if value["boundary"] != PLATFORM_EXECUTION_ARCHITECTURE_BOUNDARY:
        errors.append("boundary")
    if value["context_key"] != PLATFORM_EXECUTION_ARCHITECTURE_CONTEXT:
        errors.append("context_key")
    if len(value["family_contexts"]) != len(PlatformExecutionFamily):
        errors.append("family_contexts")
    for field, expected in (
        ("sources", PLATFORM_EXECUTION_ARCHITECTURE_SOURCE_COUNT),
        ("operations", PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT),
        ("cases", PLATFORM_EXECUTION_ARCHITECTURE_CASE_COUNT),
    ):
        if len(value[field]) != expected:
            errors.append(field)
    return tuple(errors)


def validate_platform_execution_fixture(fixture: PlatformExecutionFixture) -> bool:
    if not isinstance(fixture, PlatformExecutionFixture):
        raise ValidationError("D16 fixture type is required")
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    if any(set(item.source_ids) - source_ids for item in (*fixture.operations, *fixture.cases)):
        raise ValidationError("D16 source join is unresolved")
    if any(item.operation_id not in operation_ids for item in fixture.cases):
        raise ValidationError("D16 operation join is unresolved")
    if tuple(item.ordinal for item in fixture.operations) != tuple(
        range(1, PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT + 1)
    ):
        raise ValidationError("D16 ordinals are not contiguous")
    if any(
        sum(case.operation_id == operation.operation_id for case in fixture.cases)
        != PLATFORM_EXECUTION_ARCHITECTURE_CASES_PER_OPERATION
        for operation in fixture.operations
    ):
        raise ValidationError("D16 case balance is not closed")
    return True


def platform_execution_schema_descriptor() -> dict[str, object]:
    return {
        "schema_id": PLATFORM_EXECUTION_ARCHITECTURE_SCHEMA_ID,
        "boundary": PLATFORM_EXECUTION_ARCHITECTURE_BOUNDARY,
        "context_key": PLATFORM_EXECUTION_ARCHITECTURE_CONTEXT,
        "source_count": PLATFORM_EXECUTION_ARCHITECTURE_SOURCE_COUNT,
        "operation_count": PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT,
        "case_count": PLATFORM_EXECUTION_ARCHITECTURE_CASE_COUNT,
        "cases_per_operation": PLATFORM_EXECUTION_ARCHITECTURE_CASES_PER_OPERATION,
        "families": [item.value for item in PlatformExecutionFamily],
        "scenarios": ["positive", "control_a", "control_b", "control_c"],
    }


__all__ = [
    "PLATFORM_EXECUTION_ARCHITECTURE_REQUIRED_FIELDS",
    "PLATFORM_EXECUTION_ARCHITECTURE_SCHEMA_ID",
    "normalize_platform_execution_mapping",
    "validate_platform_execution_mapping",
    "validate_platform_execution_fixture",
    "platform_execution_schema_descriptor",
]
