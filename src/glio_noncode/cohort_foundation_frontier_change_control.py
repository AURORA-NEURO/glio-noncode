"""Change-control receipts for sources, schemas, thresholds, and policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFoundationChangeControlItem:
    change_id: str
    change_class: str
    required_review_role: str
    required_replay: bool
    required_quality_gate: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationChangeControlReport:
    report_id: str
    items: tuple[CohortFoundationChangeControlItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_foundation_frontier_change_control_report() -> CohortFoundationChangeControlReport:
    definitions = (("source-version", "source", "data-reviewer", True, True), ("schema-field", "schema", "methods-reviewer", True, True), ("distance-threshold", "threshold", "methods-reviewer", True, True), ("policy-disposition", "policy", "context-reviewer", True, True), ("export-format", "release", "release-reviewer", True, True))
    items = tuple(CohortFoundationChangeControlItem(change_id, change_class, role, replay, quality, content_hash((change_id, change_class, role, replay, quality))) for change_id, change_class, role, replay, quality in definitions)
    body = {"report_id": "cohort-foundation-frontier-change-control", "items": items}
    return CohortFoundationChangeControlReport(body["report_id"], items, len(items) == 5 and all(item.required_replay and item.required_quality_gate for item in items), content_hash(body))


__all__ = ["CohortFoundationChangeControlItem", "CohortFoundationChangeControlReport", "default_cohort_foundation_frontier_change_control_report"]
