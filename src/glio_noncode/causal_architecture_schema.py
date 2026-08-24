"""D11 aggregate schema checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .causal_architecture_contracts import (
    CAUSAL_ARCHITECTURE_BOUNDARY,
    CAUSAL_ARCHITECTURE_CONTEXT,
    CausalArchitectureFixture,
)
from .errors import ValidationError
from .serialization import jsonable

CAUSAL_ARCHITECTURE_SCHEMA_ID = "causal-architecture.aggregate.v1"
CAUSAL_ARCHITECTURE_REQUIRED_FIELDS = (
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


def normalize_causal_architecture_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValidationError("D11 mapping must be an object")
    result = {str(key): jsonable(value) for key, value in raw.items()}
    missing = [key for key in CAUSAL_ARCHITECTURE_REQUIRED_FIELDS if key not in result]
    if missing:
        raise ValidationError(f"D11 mapping is missing: {', '.join(missing)}")
    return result


def validate_causal_architecture_mapping(raw: Mapping[str, Any]) -> tuple[str, ...]:
    value = normalize_causal_architecture_mapping(raw)
    errors = []
    if value["boundary"] != CAUSAL_ARCHITECTURE_BOUNDARY:
        errors.append("boundary")
    if value["context_key"] != CAUSAL_ARCHITECTURE_CONTEXT:
        errors.append("context_key")
    for field, expected in (("sources", 20), ("operations", 16), ("cases", 64)):
        if len(value[field]) != expected:
            errors.append(field)
    return tuple(errors)


def validate_causal_architecture_fixture(fixture: CausalArchitectureFixture) -> bool:
    if not isinstance(fixture, CausalArchitectureFixture):
        raise ValidationError("D11 fixture type is required")
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    if any(set(item.source_ids) - source_ids for item in (*fixture.operations, *fixture.cases)):
        raise ValidationError("D11 source join is unresolved")
    if any(item.operation_id not in operation_ids for item in fixture.cases):
        raise ValidationError("D11 operation join is unresolved")
    return True


def causal_architecture_schema_descriptor() -> dict[str, object]:
    return {
        "schema_id": CAUSAL_ARCHITECTURE_SCHEMA_ID,
        "boundary": CAUSAL_ARCHITECTURE_BOUNDARY,
        "context_key": CAUSAL_ARCHITECTURE_CONTEXT,
        "source_count": 20,
        "operation_count": 16,
        "case_count": 64,
        "cases_per_operation": 4,
        "scenarios": ["positive", "control_a", "control_b", "control_c"],
    }


__all__ = [
    "CAUSAL_ARCHITECTURE_REQUIRED_FIELDS",
    "CAUSAL_ARCHITECTURE_SCHEMA_ID",
    "causal_architecture_schema_descriptor",
    "normalize_causal_architecture_mapping",
    "validate_causal_architecture_fixture",
    "validate_causal_architecture_mapping",
]
