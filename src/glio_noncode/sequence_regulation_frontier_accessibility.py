"""Accessibility checks for tabular and serialized evidence views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_public_data import SequenceRegulationFixture
from .sequence_regulation_frontier_views import SequenceRegulationView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationAccessibilityCheck:
    check_id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationAccessibilityReport:
    checks: tuple[SequenceRegulationAccessibilityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("accessibility report requires checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_sequence_regulation_accessibility(
    fixture: SequenceRegulationFixture,
    view: SequenceRegulationView,
) -> SequenceRegulationAccessibilityReport:
    checks = (
        SequenceRegulationAccessibilityCheck(
            "column_labels",
            bool(view.column_order) and all(view.column_order),
            "every view column has a label",
        ),
        SequenceRegulationAccessibilityCheck(
            "row_identity",
            all(row.record_id for row in view.rows),
            "every row has a stable identity",
        ),
        SequenceRegulationAccessibilityCheck(
            "state_text", all(row.state for row in view.rows), "state is serialized as text"
        ),
        SequenceRegulationAccessibilityCheck(
            "issue_text",
            all(isinstance(row.issue_codes, tuple) for row in view.rows),
            "issue paths are structured",
        ),
        SequenceRegulationAccessibilityCheck(
            "source_context", bool(fixture.context_key), "context is available to consumers"
        ),
        SequenceRegulationAccessibilityCheck(
            "receipt_text",
            all(row.result_address.startswith("sha256:") for row in view.rows),
            "receipts are visible",
        ),
    )
    return SequenceRegulationAccessibilityReport(checks, all(check.passed for check in checks))


__all__ = [
    "SequenceRegulationAccessibilityCheck",
    "SequenceRegulationAccessibilityReport",
    "audit_sequence_regulation_accessibility",
]
