"""Operational matrix for ownership, inputs, outputs, and response actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierOperationalRow:
    operation: ControlFrontierOperation
    input_boundary: str
    output_boundary: str
    owner_role: str
    failure_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierOperationalMatrix:
    rows: tuple[ControlFrontierOperationalRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_operational_matrix() -> ControlFrontierOperationalMatrix:
    rows = []
    for operation in ControlFrontierOperation:
        body = {"operation": operation, "input_boundary": "declared aggregate payload", "output_boundary": "content-addressed operational receipt", "owner_role": "platform_reviewer", "failure_action": "retain issue and route review"}
        rows.append(ControlFrontierOperationalRow(**body, content_address=content_hash(body)))
    return ControlFrontierOperationalMatrix(tuple(rows), len(rows) == 8, content_hash(tuple(rows)))


__all__ = ["ControlFrontierOperationalMatrix", "ControlFrontierOperationalRow", "build_control_frontier_operational_matrix"]
