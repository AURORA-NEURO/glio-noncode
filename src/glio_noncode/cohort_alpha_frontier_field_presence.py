"""Presence counts that distinguish absent, empty, and populated channels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFieldPresenceRow:
    operation: str
    field: str
    populated_count: int
    empty_count: int
    missing_count: int
    status: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFieldPresenceReport:
    rows: tuple[CohortAlphaFrontierFieldPresenceRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_cohort_alpha_frontier_field_presence(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierFieldPresenceReport:
    fields = {
        "C09": ("observations", "clonal_threshold", "subclonal_threshold"),
        "C10": ("observations", "change_threshold"),
        "C11": ("observations", "change_threshold"),
        "C12": ("observations", "minimum_cohorts", "minimum_concordance"),
    }
    rows = []
    for operation, names in fields.items():
        records = tuple(record for record in fixture.records if record.operation == operation)
        for name in names:
            populated = sum(bool(record.payload.get(name)) or isinstance(record.payload.get(name), (int, float)) for record in records)
            empty = sum(name in record.payload and not record.payload.get(name) for record in records)
            missing = len(records) - populated - empty
            status = "complete" if missing == 0 else "partial"
            rows.append(CohortAlphaFrontierFieldPresenceRow(operation, name, populated, empty, missing, status, content_hash({"operation": operation, "field": name, "populated": populated, "empty": empty, "missing": missing, "status": status}, prefix="alpha-field-presence")))
    values = tuple(rows)
    return CohortAlphaFrontierFieldPresenceReport(values, len(values) == 10 and all(item.populated_count + item.empty_count + item.missing_count == 4 for item in values), content_hash(values, prefix="alpha-field-presence-report"))


__all__ = ["CohortAlphaFrontierFieldPresenceReport", "CohortAlphaFrontierFieldPresenceRow", "measure_cohort_alpha_frontier_field_presence"]
