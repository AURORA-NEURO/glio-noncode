"""Payload field validation for every fixture record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_adapters import CohortAlphaFrontierAdapterRegistry, validate_cohort_alpha_frontier_payload
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFieldValidationRow:
    record_id: str
    operation: str
    accepted: bool
    errors: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFieldValidationReport:
    rows: tuple[CohortAlphaFrontierFieldValidationRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def validate_cohort_alpha_frontier_fields(fixture: CohortAlphaFrontierFixture, registry: CohortAlphaFrontierAdapterRegistry) -> CohortAlphaFrontierFieldValidationReport:
    rows = []
    for record in fixture.records:
        result = validate_cohort_alpha_frontier_payload(record.operation, record.payload, registry)
        rows.append(CohortAlphaFrontierFieldValidationRow(record.record_id, record.operation, result.accepted, result.errors, content_hash({"record_id": record.record_id, "operation": record.operation, "accepted": result.accepted, "errors": result.errors}, prefix="alpha-field-validation")))
    values = tuple(rows)
    return CohortAlphaFrontierFieldValidationReport(values, len(values) == 16 and all(item.accepted for item in values), content_hash(values, prefix="alpha-field-validation-report"))


__all__ = ["CohortAlphaFrontierFieldValidationReport", "CohortAlphaFrontierFieldValidationRow", "validate_cohort_alpha_frontier_fields"]
