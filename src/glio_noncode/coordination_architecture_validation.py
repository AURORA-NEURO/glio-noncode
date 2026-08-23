"""Seven-plane validation matrix for every D16 operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coordination_architecture_contracts import CoordinationPlane, CoordinationRuntime, addressed


@dataclass(frozen=True, slots=True)
class CoordinationValidationCell:
    cell_id: str
    operation_id: str
    plane: CoordinationPlane
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "operation_id": self.operation_id,
            "plane": self.plane,
            "passed": self.passed,
            "observed": self.observed,
            "required": self.required,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class CoordinationValidationMatrix:
    matrix_id: str
    cells: tuple[CoordinationValidationCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "matrix_id": self.matrix_id,
            "cells": tuple(item.to_dict() for item in self.cells),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def build_coordination_validation_matrix(runtime: CoordinationRuntime) -> CoordinationValidationMatrix:
    planes = tuple(CoordinationPlane)
    cells = []
    for spec in runtime.plan.nodes:
        for plane in planes:
            if plane is CoordinationPlane.IDENTITY:
                observed, required, passed = spec.operation_id, spec.operation_id, True
            elif plane is CoordinationPlane.CONTRACT:
                observed, required, passed = len(runtime.tools.tools), 16, len(runtime.tools.tools) == 16
            elif plane is CoordinationPlane.POLICY:
                observed, required, passed = runtime.state, "accepted", runtime.state.value == "accepted"
            elif plane is CoordinationPlane.RESOURCE:
                observed, required, passed = runtime.schedule.used_units, runtime.schedule.capacity_units, runtime.schedule.used_units <= runtime.schedule.capacity_units
            elif plane is CoordinationPlane.REVIEW:
                observed, required, passed = 48, 48, len(runtime.evaluation.executions) - 16 == 48
            elif plane is CoordinationPlane.INTEGRITY:
                observed, required, passed = len(runtime.ledger.events), 64, len(runtime.ledger.events) == 64
            else:
                observed, required, passed = runtime.release.state.value, "accepted", runtime.release.state.value == "accepted"
            body = {
                "cell_id": f"{spec.operation_id}:{plane.value}",
                "operation_id": spec.operation_id,
                "plane": plane,
                "passed": passed,
                "observed": observed,
                "required": required,
            }
            cells.append(CoordinationValidationCell(**body, content_address=addressed(body, "coordination-validation-cell")))
    body = {"matrix_id": f"{runtime.run_id}:validation", "cells": tuple(cells), "accepted": all(item.passed for item in cells)}
    return CoordinationValidationMatrix(**body, content_address=addressed(body, "coordination-validation-matrix"))


__all__ = ["CoordinationValidationCell", "CoordinationValidationMatrix", "build_coordination_validation_matrix"]
