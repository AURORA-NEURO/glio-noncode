"""Operational matrix for platform control paths and responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierOperationalRow:
    operation: PlatformFrontierOperation
    accepted_state: str
    control_states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierOperationalMatrix:
    rows: tuple[PlatformFrontierOperationalRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_operational_matrix(evaluation: PlatformFrontierEvaluation) -> PlatformFrontierOperationalMatrix:
    rows = []
    for operation in PlatformFrontierOperation:
        selected = tuple(item for item in evaluation.executions if item.operation is operation)
        body = {"operation": operation, "accepted_state": selected[0].state.value, "control_states": tuple(item.state.value for item in selected[1:]), "issue_codes": tuple(issue for item in selected[1:] for issue in item.issue_codes), "action": "release positive path; review or retain every control"}
        rows.append(PlatformFrontierOperationalRow(**body, content_address=content_hash(body)))
    return PlatformFrontierOperationalMatrix(tuple(rows), len(rows) == 4, content_hash(tuple(rows)))


__all__ = ["PlatformFrontierOperationalMatrix", "PlatformFrontierOperationalRow", "build_platform_frontier_operational_matrix"]
