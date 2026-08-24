"""D10 aggregate schema checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .link_graph_architecture_contracts import (
    LINK_GRAPH_ARCHITECTURE_BOUNDARY,
    LINK_GRAPH_ARCHITECTURE_CASE_COUNT,
    LINK_GRAPH_ARCHITECTURE_CASES_PER_OPERATION,
    LINK_GRAPH_ARCHITECTURE_CONTEXT,
    LINK_GRAPH_ARCHITECTURE_OPERATION_COUNT,
    LINK_GRAPH_ARCHITECTURE_SOURCE_COUNT,
    LinkGraphArchitectureFamily,
    LinkGraphArchitectureFixture,
)
from .serialization import jsonable

LINK_GRAPH_ARCHITECTURE_SCHEMA_ID = "link-graph-architecture.aggregate.v1"
LINK_GRAPH_ARCHITECTURE_REQUIRED_FIELDS = (
    "fixture_id",
    "version",
    "boundary",
    "context_key",
    "foreign_context_key",
    "sources",
    "operations",
    "cases",
    "content_address",
)


def normalize_link_graph_architecture_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValidationError("D10 mapping must be an object")
    result = {str(key): jsonable(value) for key, value in raw.items()}
    missing = [key for key in LINK_GRAPH_ARCHITECTURE_REQUIRED_FIELDS if key not in result]
    if missing:
        raise ValidationError(f"D10 mapping is missing: {', '.join(missing)}")
    return result


def validate_link_graph_architecture_mapping(raw: Mapping[str, Any]) -> tuple[str, ...]:
    value = normalize_link_graph_architecture_mapping(raw)
    errors = []
    if value["boundary"] != LINK_GRAPH_ARCHITECTURE_BOUNDARY:
        errors.append("boundary")
    if value["context_key"] != LINK_GRAPH_ARCHITECTURE_CONTEXT:
        errors.append("context_key")
    for field, expected in (
        ("sources", LINK_GRAPH_ARCHITECTURE_SOURCE_COUNT),
        ("operations", LINK_GRAPH_ARCHITECTURE_OPERATION_COUNT),
        ("cases", LINK_GRAPH_ARCHITECTURE_CASE_COUNT),
    ):
        if len(value[field]) != expected:
            errors.append(field)
    if tuple(item["ordinal"] for item in value["operations"]) != tuple(
        range(1, LINK_GRAPH_ARCHITECTURE_OPERATION_COUNT + 1)
    ):
        errors.append("operation_ordinals")
    if any(
        sum(item["operation_id"] == operation["operation_id"] for item in value["cases"])
        != LINK_GRAPH_ARCHITECTURE_CASES_PER_OPERATION
        for operation in value["operations"]
    ):
        errors.append("case_balance")
    return tuple(errors)


def validate_link_graph_architecture_fixture(fixture: LinkGraphArchitectureFixture) -> bool:
    if not isinstance(fixture, LinkGraphArchitectureFixture):
        raise ValidationError("D10 fixture type is required")
    if len(fixture.sources) != LINK_GRAPH_ARCHITECTURE_SOURCE_COUNT:
        raise ValidationError("D10 source cardinality is invalid")
    if len(fixture.operations) != LINK_GRAPH_ARCHITECTURE_OPERATION_COUNT:
        raise ValidationError("D10 operation cardinality is invalid")
    if len(fixture.cases) != LINK_GRAPH_ARCHITECTURE_CASE_COUNT:
        raise ValidationError("D10 case cardinality is invalid")
    if tuple(item.ordinal for item in fixture.operations) != tuple(
        range(1, LINK_GRAPH_ARCHITECTURE_OPERATION_COUNT + 1)
    ):
        raise ValidationError("D10 operation ordinals are not contiguous")
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    if any(set(item.source_ids) - source_ids for item in (*fixture.operations, *fixture.cases)):
        raise ValidationError("D10 source join is unresolved")
    if any(item.operation_id not in operation_ids for item in fixture.cases):
        raise ValidationError("D10 operation join is unresolved")
    if len({item.family for item in fixture.operations}) != len(LinkGraphArchitectureFamily):
        raise ValidationError("D10 family coverage is incomplete")
    if any(
        sum(item.operation_id == operation.operation_id for item in fixture.cases)
        != LINK_GRAPH_ARCHITECTURE_CASES_PER_OPERATION
        for operation in fixture.operations
    ):
        raise ValidationError("D10 case balance is invalid")
    if any(not item.public_aggregate for item in fixture.sources):
        raise ValidationError("D10 source visibility is not public aggregate")
    if any(item.context_key != fixture.context_key for item in fixture.cases):
        raise ValidationError("D10 aggregate case context is inconsistent")
    return True


def link_graph_architecture_schema_descriptor() -> dict[str, object]:
    return {
        "schema_id": LINK_GRAPH_ARCHITECTURE_SCHEMA_ID,
        "boundary": LINK_GRAPH_ARCHITECTURE_BOUNDARY,
        "context_key": LINK_GRAPH_ARCHITECTURE_CONTEXT,
        "source_count": LINK_GRAPH_ARCHITECTURE_SOURCE_COUNT,
        "operation_count": LINK_GRAPH_ARCHITECTURE_OPERATION_COUNT,
        "case_count": LINK_GRAPH_ARCHITECTURE_CASE_COUNT,
        "cases_per_operation": LINK_GRAPH_ARCHITECTURE_CASES_PER_OPERATION,
        "family_count": len(LinkGraphArchitectureFamily),
        "scenarios": ["positive", "control_a", "control_b", "control_c"],
    }


__all__ = [
    "LINK_GRAPH_ARCHITECTURE_REQUIRED_FIELDS",
    "LINK_GRAPH_ARCHITECTURE_SCHEMA_ID",
    "link_graph_architecture_schema_descriptor",
    "normalize_link_graph_architecture_mapping",
    "validate_link_graph_architecture_fixture",
    "validate_link_graph_architecture_mapping",
]
