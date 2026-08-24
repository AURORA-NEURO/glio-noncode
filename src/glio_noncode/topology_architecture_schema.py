"""Schema and object-level validation for the D09 aggregate."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .serialization import jsonable
from .topology_architecture_contracts import (
    TOPOLOGY_ARCHITECTURE_BOUNDARY,
    TOPOLOGY_ARCHITECTURE_CASE_COUNT,
    TOPOLOGY_ARCHITECTURE_CASES_PER_OPERATION,
    TOPOLOGY_ARCHITECTURE_CONTEXT,
    TOPOLOGY_ARCHITECTURE_OPERATION_COUNT,
    TOPOLOGY_ARCHITECTURE_SOURCE_COUNT,
    TopologyArchitectureFamily,
    TopologyArchitectureFixture,
)

TOPOLOGY_ARCHITECTURE_SCHEMA_ID = "topology-architecture.aggregate.v1"
TOPOLOGY_ARCHITECTURE_REQUIRED_FIELDS = (
    "fixture_id",
    "version",
    "boundary",
    "context_key",
    "sources",
    "operations",
    "cases",
    "content_address",
)


def normalize_topology_architecture_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValidationError("D09 mapping must be an object")
    result = {str(key): jsonable(value) for key, value in raw.items()}
    missing = [field for field in TOPOLOGY_ARCHITECTURE_REQUIRED_FIELDS if field not in result]
    if missing:
        raise ValidationError(f"D09 mapping is missing: {', '.join(missing)}")
    if not all(isinstance(result[field], list) for field in ("sources", "operations", "cases")):
        raise ValidationError("D09 source, operation, and case fields must be arrays")
    return result


def validate_topology_architecture_mapping(raw: Mapping[str, Any]) -> tuple[str, ...]:
    value = normalize_topology_architecture_mapping(raw)
    errors: list[str] = []
    if value["boundary"] != TOPOLOGY_ARCHITECTURE_BOUNDARY:
        errors.append("boundary")
    if value["context_key"] != TOPOLOGY_ARCHITECTURE_CONTEXT:
        errors.append("context_key")
    if len(value["sources"]) != TOPOLOGY_ARCHITECTURE_SOURCE_COUNT:
        errors.append("sources")
    if len(value["operations"]) != TOPOLOGY_ARCHITECTURE_OPERATION_COUNT:
        errors.append("operations")
    if len(value["cases"]) != TOPOLOGY_ARCHITECTURE_CASE_COUNT:
        errors.append("cases")
    if tuple(item["ordinal"] for item in value["operations"]) != tuple(
        range(1, TOPOLOGY_ARCHITECTURE_OPERATION_COUNT + 1)
    ):
        errors.append("operation_ordinals")
    if any(
        sum(item["operation_id"] == operation["operation_id"] for item in value["cases"])
        != TOPOLOGY_ARCHITECTURE_CASES_PER_OPERATION
        for operation in value["operations"]
    ):
        errors.append("case_balance")
    return tuple(errors)


def validate_topology_architecture_fixture(fixture: TopologyArchitectureFixture) -> bool:
    if not isinstance(fixture, TopologyArchitectureFixture):
        raise ValidationError("D09 fixture type is required")
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    if any(set(item.source_ids) - source_ids for item in (*fixture.operations, *fixture.cases)):
        raise ValidationError("D09 source join is unresolved")
    if any(item.operation_id not in operation_ids for item in fixture.cases):
        raise ValidationError("D09 case operation join is unresolved")
    if len(fixture.sources) != TOPOLOGY_ARCHITECTURE_SOURCE_COUNT:
        raise ValidationError("D09 source cardinality is invalid")
    if len(fixture.operations) != TOPOLOGY_ARCHITECTURE_OPERATION_COUNT:
        raise ValidationError("D09 operation cardinality is invalid")
    if len(fixture.cases) != TOPOLOGY_ARCHITECTURE_CASE_COUNT:
        raise ValidationError("D09 case cardinality is invalid")
    if tuple(item.ordinal for item in fixture.operations) != tuple(
        range(1, TOPOLOGY_ARCHITECTURE_OPERATION_COUNT + 1)
    ):
        raise ValidationError("D09 operation ordinals must be contiguous")
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    if any(set(item.source_ids) - source_ids for item in (*fixture.operations, *fixture.cases)):
        raise ValidationError("D09 source join is unresolved")
    if any(item.operation_id not in operation_ids for item in fixture.cases):
        raise ValidationError("D09 case operation join is unresolved")
    if len({item.family for item in fixture.operations}) != len(TopologyArchitectureFamily):
        raise ValidationError("D09 family coverage is incomplete")
    if any(
        sum(item.operation_id == operation.operation_id for item in fixture.cases)
        != TOPOLOGY_ARCHITECTURE_CASES_PER_OPERATION
        for operation in fixture.operations
    ):
        raise ValidationError("D09 case balance is invalid")
    if any(not item.public_aggregate for item in fixture.sources):
        raise ValidationError("D09 source visibility is not public aggregate")
    if any(not item.delegate_context_key for item in fixture.cases):
        raise ValidationError("D09 delegate context is missing")
    if any(
        item.context_key != TOPOLOGY_ARCHITECTURE_CONTEXT
        and "context_mismatch" not in item.expected_issue_codes
        for item in fixture.cases
    ):
        raise ValidationError("D09 foreign context control is not explicit")
    return True


def topology_architecture_schema_descriptor() -> dict[str, Any]:
    return {
        "schema_id": TOPOLOGY_ARCHITECTURE_SCHEMA_ID,
        "boundary": TOPOLOGY_ARCHITECTURE_BOUNDARY,
        "context_key": TOPOLOGY_ARCHITECTURE_CONTEXT,
        "source_count": TOPOLOGY_ARCHITECTURE_SOURCE_COUNT,
        "operation_count": TOPOLOGY_ARCHITECTURE_OPERATION_COUNT,
        "case_count": TOPOLOGY_ARCHITECTURE_CASE_COUNT,
        "cases_per_operation": TOPOLOGY_ARCHITECTURE_CASES_PER_OPERATION,
        "family_count": len(TopologyArchitectureFamily),
        "control_scenarios": ["foreign_context", "malformed_input", "identity_conflict"],
    }


__all__ = [
    "TOPOLOGY_ARCHITECTURE_REQUIRED_FIELDS",
    "TOPOLOGY_ARCHITECTURE_SCHEMA_ID",
    "normalize_topology_architecture_mapping",
    "topology_architecture_schema_descriptor",
    "validate_topology_architecture_fixture",
    "validate_topology_architecture_mapping",
]
