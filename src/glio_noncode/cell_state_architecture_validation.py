"""Validation facade combining schema, audit, execution, replay, and depth."""

from __future__ import annotations

from typing import Any

from .cell_state_architecture_contracts import CellStateArchitectureFixture
from .cell_state_architecture_depth import assess_cell_state_architecture_depth
from .cell_state_architecture_invariants import cell_state_architecture_invariants
from .cell_state_architecture_operations import evaluate_cell_state_architecture_fixture
from .cell_state_architecture_public_data import audit_cell_state_architecture_data
from .cell_state_architecture_replay import replay_cell_state_architecture_fixture
from .cell_state_architecture_schema import validate_cell_state_architecture_fixture


def validate_cell_state_architecture(fixture: CellStateArchitectureFixture) -> dict[str, Any]:
    typed = validate_cell_state_architecture_fixture(fixture)
    audit = audit_cell_state_architecture_data(fixture)
    evaluation = evaluate_cell_state_architecture_fixture(fixture)
    replay = replay_cell_state_architecture_fixture(fixture)
    invariants = cell_state_architecture_invariants(fixture)
    depth = assess_cell_state_architecture_depth(fixture, evaluation)
    return {
        "typed": typed,
        "audit": audit.accepted,
        "evaluation": evaluation.accepted,
        "replay": replay.accepted,
        "invariants": invariants,
        "depth": depth.to_dict(),
        "accepted": typed
        and audit.accepted
        and evaluation.accepted
        and replay.accepted
        and all(invariants.values()),
    }


__all__ = ["validate_cell_state_architecture"]
