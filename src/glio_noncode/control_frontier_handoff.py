"""Reproducible handoff package for control frontier review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import CONTROL_FRONTIER_BOUNDARY, ControlFrontierEvaluation, ControlFrontierFixture
from .control_frontier_metrics import ControlFrontierMetrics
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierHandoffItem:
    operation: str
    record_count: int
    accepted_count: int
    issue_codes: tuple[str, ...]
    next_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierHandoff:
    fixture_id: str
    boundary: str
    items: tuple[ControlFrontierHandoffItem, ...]
    source_addresses: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_handoff(fixture: ControlFrontierFixture, evaluation: ControlFrontierEvaluation, metrics: ControlFrontierMetrics) -> ControlFrontierHandoff:
    items = []
    for metric in metrics.operation_metrics:
        rows = evaluation.by_operation(metric.operation)
        issues = tuple(sorted({issue for row in rows for issue in row.issue_codes}))
        body = {"operation": metric.operation.value, "record_count": metric.record_count, "accepted_count": metric.accepted_count, "issue_codes": issues, "next_action": "review control receipt" if issues else "retain accepted receipt"}
        items.append(ControlFrontierHandoffItem(**body, content_address=content_hash(body)))
    return ControlFrontierHandoff(fixture.fixture_id, CONTROL_FRONTIER_BOUNDARY, tuple(items), tuple(item.content_address for item in fixture.sources), True, content_hash({"fixture_id": fixture.fixture_id, "items": tuple(items), "source_addresses": tuple(item.content_address for item in fixture.sources)}))


__all__ = ["ControlFrontierHandoff", "ControlFrontierHandoffItem", "build_control_frontier_handoff"]
