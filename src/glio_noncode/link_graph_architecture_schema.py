"""D10 aggregate schema checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .link_graph_architecture_contracts import (
    LINK_GRAPH_ARCHITECTURE_BOUNDARY,
    LINK_GRAPH_ARCHITECTURE_CONTEXT,
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
    for field, expected in (("sources", 19), ("operations", 16), ("cases", 64)):
        if len(value[field]) != expected:
            errors.append(field)
    return tuple(errors)


def validate_link_graph_architecture_fixture(fixture: LinkGraphArchitectureFixture) -> bool:
    if not isinstance(fixture, LinkGraphArchitectureFixture):
        raise ValidationError("D10 fixture type is required")
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    if any(set(item.source_ids) - source_ids for item in (*fixture.operations, *fixture.cases)):
        raise ValidationError("D10 source join is unresolved")
    if any(item.operation_id not in operation_ids for item in fixture.cases):
        raise ValidationError("D10 operation join is unresolved")
    return True


def link_graph_architecture_schema_descriptor() -> dict[str, object]:
    return {
        "schema_id": LINK_GRAPH_ARCHITECTURE_SCHEMA_ID,
        "boundary": LINK_GRAPH_ARCHITECTURE_BOUNDARY,
        "context_key": LINK_GRAPH_ARCHITECTURE_CONTEXT,
        "source_count": 19,
        "operation_count": 16,
        "case_count": 64,
        "cases_per_operation": 4,
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
