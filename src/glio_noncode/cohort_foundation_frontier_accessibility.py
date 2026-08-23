"""Accessibility and field-visibility metadata for review projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_views import CohortFoundationReviewView


@dataclass(frozen=True, slots=True)
class CohortFoundationAccessibleField:
    field_id: str
    label: str
    description: str
    sort_key: int
    required: bool
    exposed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationAccessibilityReport:
    report_id: str
    fields: tuple[CohortFoundationAccessibleField, ...]
    row_count: int
    keyboard_order: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_accessibility_report(view: CohortFoundationReviewView) -> CohortFoundationAccessibilityReport:
    definitions = (
        ("record_id", "Record", "Stable aggregate record identifier", True),
        ("operation", "Operation", "C01-C04 operation name", True),
        ("role", "Role", "Positive or control role", True),
        ("actual_state", "State", "Observed descriptive state", True),
        ("disposition", "Disposition", "Publication or review disposition", True),
        ("issue_codes", "Issues", "Structured limitation codes", False),
        ("source_count", "Sources", "Number of cited source receipts", False),
    )
    fields = tuple(CohortFoundationAccessibleField(field_id, label, description, index, required, True, content_hash((field_id, label, description, index, required))) for index, (field_id, label, description, required) in enumerate(definitions, start=1))
    keyboard_order = tuple(item.field_id for item in fields)
    body = {"report_id": "cohort-foundation-frontier-accessibility", "fields": fields, "rows": len(view.rows), "keyboard_order": keyboard_order}
    return CohortFoundationAccessibilityReport(body["report_id"], fields, len(view.rows), keyboard_order, len(fields) == 7 and all(item.exposed for item in fields), content_hash(body))


__all__ = ["CohortFoundationAccessibilityReport", "CohortFoundationAccessibleField", "build_cohort_foundation_frontier_accessibility_report"]
