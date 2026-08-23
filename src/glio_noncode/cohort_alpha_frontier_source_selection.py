"""Deterministic source selection when multiple public receipts are available."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSourceSelection:
    operation: str
    selected_source_ids: tuple[str, ...]
    available_source_ids: tuple[str, ...]
    selection_rule: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSourceSelectionReport:
    selections: tuple[CohortAlphaFrontierSourceSelection, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_source_selection(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierSourceSelectionReport:
    available = tuple(sorted(source.source_id for source in fixture.sources))
    selections = []
    for operation in fixture.operations:
        selected = tuple(sorted({source_id for record in fixture.records if record.operation == operation for source_id in record.source_ids}))
        rule = "retain every referenced receipt; do not silently collapse sources"
        selections.append(CohortAlphaFrontierSourceSelection(operation, selected, available, rule, bool(selected) and set(selected) <= set(available), content_hash({"operation": operation, "selected": selected, "available": available, "rule": rule}, prefix="alpha-source-selection")))
    values = tuple(selections)
    return CohortAlphaFrontierSourceSelectionReport(values, len(values) == 4 and all(item.accepted for item in values), content_hash(values, prefix="alpha-source-selection-report"))


__all__ = ["CohortAlphaFrontierSourceSelection", "CohortAlphaFrontierSourceSelectionReport", "build_cohort_alpha_frontier_source_selection"]
