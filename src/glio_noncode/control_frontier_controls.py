"""Control-class coverage across the Domain 16 operational surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierControlCoverage:
    operation: ControlFrontierOperation
    positive_count: int
    control_count: int
    states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierControlReport:
    rows: tuple[ControlFrontierControlCoverage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_control_coverage(evaluation: ControlFrontierEvaluation) -> ControlFrontierControlReport:
    rows = []
    for operation in ControlFrontierOperation:
        values = evaluation.by_operation(operation)
        body = {"operation": operation, "positive_count": sum(item.role.value == "positive" for item in values), "control_count": sum(item.role.value == "control" for item in values), "states": tuple(sorted({item.state.value for item in values})), "issue_codes": tuple(sorted({issue for item in values for issue in item.issue_codes})), "complete": len(values) == 4 and sum(item.role.value == "positive" for item in values) == 1 and sum(item.role.value == "control" for item in values) == 3}
        rows.append(ControlFrontierControlCoverage(**body, content_address=content_hash(body)))
    return ControlFrontierControlReport(tuple(rows), all(item.complete for item in rows), content_hash(tuple(rows)))


__all__ = ["ControlFrontierControlCoverage", "ControlFrontierControlReport", "build_control_frontier_control_coverage"]
