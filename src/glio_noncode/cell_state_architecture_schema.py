"""Schema, field rules, and stable normalization for D08 interchange."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .cell_state_architecture_contracts import (
    CELL_STATE_ARCHITECTURE_BOUNDARY,
    CELL_STATE_ARCHITECTURE_CASE_COUNT,
    CELL_STATE_ARCHITECTURE_CASES_PER_OPERATION,
    CELL_STATE_ARCHITECTURE_CONTEXT,
    CELL_STATE_ARCHITECTURE_OPERATION_COUNT,
    CELL_STATE_ARCHITECTURE_SOURCE_COUNT,
    CellStateArchitectureFamily,
    CellStateArchitectureFixture,
    addressed,
)
from .errors import ValidationError
from .serialization import jsonable

D08_SCHEMA_ID = "cell-state-architecture.aggregate.v1"
D08_REQUIRED_TOP_LEVEL_FIELDS = (
    "fixture_id",
    "version",
    "boundary",
    "context_key",
    "sources",
    "operations",
    "cases",
    "content_address",
)
D08_CASE_REQUIRED_FIELDS = (
    "case_id",
    "operation_id",
    "capability_id",
    "operation",
    "family",
    "plane",
    "scenario",
    "context_key",
    "delegate_context_key",
    "source_ids",
    "payload",
    "expected_state",
    "expected_result_state",
    "expected_issue_codes",
    "expected_counts",
    "description",
    "content_address",
)


def normalize_cell_state_architecture_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic JSON-compatible representation without changing meaning."""
    if not isinstance(raw, Mapping):
        raise ValidationError("D08 interchange value must be an object")
    value = {str(key): jsonable(item) for key, item in raw.items()}
    for field in D08_REQUIRED_TOP_LEVEL_FIELDS:
        if field not in value:
            raise ValidationError(f"D08 interchange is missing {field}")
    if (
        not isinstance(value["sources"], list)
        or not isinstance(value["operations"], list)
        or not isinstance(value["cases"], list)
    ):
        raise ValidationError("D08 sources, operations, and cases must be arrays")
    return value


def validate_cell_state_architecture_mapping(raw: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate structural fields before the strongly typed contract is constructed."""
    value = normalize_cell_state_architecture_mapping(raw)
    errors: list[str] = []
    if value["boundary"] != CELL_STATE_ARCHITECTURE_BOUNDARY:
        errors.append("boundary")
    if value["context_key"] != CELL_STATE_ARCHITECTURE_CONTEXT:
        errors.append("context_key")
    if len(value["sources"]) != CELL_STATE_ARCHITECTURE_SOURCE_COUNT:
        errors.append("sources")
    if len(value["operations"]) != CELL_STATE_ARCHITECTURE_OPERATION_COUNT:
        errors.append("operations")
    if len(value["cases"]) != CELL_STATE_ARCHITECTURE_CASE_COUNT:
        errors.append("cases")
    for index, case in enumerate(value["cases"]):
        if not isinstance(case, Mapping):
            errors.append(f"cases[{index}]")
            continue
        errors.extend(
            f"cases[{index}].{field}" for field in D08_CASE_REQUIRED_FIELDS if field not in case
        )
        if "source_ids" in case and (
            not isinstance(case["source_ids"], list) or not case["source_ids"]
        ):
            errors.append(f"cases[{index}].source_ids")
    for index, operation in enumerate(value["operations"]):
        if not isinstance(operation, Mapping):
            errors.append(f"operations[{index}]")
        elif operation.get("ordinal") != index + 1:
            errors.append(f"operations[{index}].ordinal")
    return tuple(dict.fromkeys(errors))


def validate_cell_state_architecture_fixture(fixture: CellStateArchitectureFixture) -> bool:
    """Validate object-level joins, sequence order, and content addresses."""
    if not isinstance(fixture, CellStateArchitectureFixture):
        raise ValidationError("D08 fixture type is required")
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    if any(set(item.source_ids) - source_ids for item in (*fixture.operations, *fixture.cases)):
        raise ValidationError("D08 source join is unresolved")
    if any(item.operation_id not in operation_ids for item in fixture.cases):
        raise ValidationError("D08 case operation join is unresolved")
    if tuple(item.ordinal for item in fixture.operations) != tuple(
        range(1, CELL_STATE_ARCHITECTURE_OPERATION_COUNT + 1)
    ):
        raise ValidationError("D08 operation ordinals must be contiguous")
    if len({item.family for item in fixture.operations}) != len(CellStateArchitectureFamily):
        raise ValidationError("D08 operation families must all be represented")
    if any(
        sum(item.operation_id == operation.operation_id for item in fixture.cases)
        != CELL_STATE_ARCHITECTURE_CASES_PER_OPERATION
        for operation in fixture.operations
    ):
        raise ValidationError("D08 operations must have four scenario cases")
    if any(not item.public_aggregate for item in fixture.sources):
        raise ValidationError("D08 sources must be public aggregate records")
    if any(not item.delegate_context_key for item in fixture.cases):
        raise ValidationError("D08 case delegation context is required")
    if any(
        item.context_key
        not in (fixture.context_key, "GRCh38|glioma|pediatric|stem_like|tumor|unknown")
        for item in fixture.cases
    ):
        raise ValidationError("D08 case context is outside the declared test boundary")
    if any(
        "context_mismatch" not in item.expected_issue_codes
        for item in fixture.cases
        if item.scenario.value == "foreign_context"
    ):
        raise ValidationError("D08 foreign controls must declare context mismatch")
    return True


def schema_descriptor() -> dict[str, Any]:
    """Describe the public contract for generated documentation and client checks."""
    descriptor = {
        "schema_id": D08_SCHEMA_ID,
        "boundary": CELL_STATE_ARCHITECTURE_BOUNDARY,
        "context_key": CELL_STATE_ARCHITECTURE_CONTEXT,
        "top_level_fields": list(D08_REQUIRED_TOP_LEVEL_FIELDS),
        "source_count": CELL_STATE_ARCHITECTURE_SOURCE_COUNT,
        "operation_count": CELL_STATE_ARCHITECTURE_OPERATION_COUNT,
        "case_count": CELL_STATE_ARCHITECTURE_CASE_COUNT,
        "family_count": len(CellStateArchitectureFamily),
        "cases_per_operation": CELL_STATE_ARCHITECTURE_CASES_PER_OPERATION,
        "positive_scenarios": ["positive"],
        "control_scenarios": ["foreign_context", "malformed_input", "identity_conflict"],
    }
    return descriptor | {"content_address": addressed(descriptor, "cell-state-schema")}


__all__ = [
    "D08_CASE_REQUIRED_FIELDS",
    "D08_REQUIRED_TOP_LEVEL_FIELDS",
    "D08_SCHEMA_ID",
    "normalize_cell_state_architecture_mapping",
    "schema_descriptor",
    "validate_cell_state_architecture_fixture",
    "validate_cell_state_architecture_mapping",
]
