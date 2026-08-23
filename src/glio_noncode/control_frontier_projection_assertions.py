"""Assertions over public JSON/CSV projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation
from .control_frontier_exports import export_control_frontier_json, export_control_frontier_metrics_csv, export_control_frontier_review_csv
from .control_frontier_views import build_control_frontier_view
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierProjectionAssertion:
    assertion_id: str
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierProjectionReport:
    assertions: tuple[ControlFrontierProjectionAssertion, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assert_control_frontier_projection(evaluation: ControlFrontierEvaluation) -> ControlFrontierProjectionReport:
    view = build_control_frontier_view(evaluation)
    values = (
        ("json-nonempty", bool(export_control_frontier_json(evaluation)), True),
        ("review-header", export_control_frontier_review_csv(view).splitlines()[0], "record_id,operation,role,state,accepted,issue_codes"),
        ("metrics-header", export_control_frontier_metrics_csv(evaluation).splitlines()[0], "record_id,operation,state,accepted,issue_count"),
        ("review-count", len(view.entries), len(evaluation.executions)),
    )
    assertions = []
    for assertion_id, observed, required in values:
        body = {"assertion_id": assertion_id, "passed": observed == required, "observed": observed, "required": required}
        assertions.append(ControlFrontierProjectionAssertion(**body, content_address=content_hash(body)))
    return ControlFrontierProjectionReport(tuple(assertions), all(item.passed for item in assertions), content_hash(tuple(assertions)))


__all__ = ["ControlFrontierProjectionAssertion", "ControlFrontierProjectionReport", "assert_control_frontier_projection"]
