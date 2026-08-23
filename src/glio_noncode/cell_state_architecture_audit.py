"""Deep audit facade for D08 data, execution, control, and release surfaces."""

from __future__ import annotations

from typing import Any

from .cell_state_architecture_compliance import assess_cell_state_architecture_compliance
from .cell_state_architecture_contract_matrix import (
    build_cell_state_architecture_contract_matrix,
    contract_matrix_is_closed,
)
from .cell_state_architecture_contracts import CellStateArchitectureFixture, addressed
from .cell_state_architecture_invariants import cell_state_architecture_invariants
from .cell_state_architecture_lineage import build_cell_state_architecture_lineage, lineage_gaps
from .cell_state_architecture_metrics import cell_state_architecture_metrics, metric_invariants
from .cell_state_architecture_operations import evaluate_cell_state_architecture_fixture
from .cell_state_architecture_public_data import audit_cell_state_architecture_data
from .cell_state_architecture_replay import replay_cell_state_architecture_fixture
from .cell_state_architecture_schema import validate_cell_state_architecture_fixture


def deep_audit_cell_state_architecture(fixture: CellStateArchitectureFixture) -> dict[str, Any]:
    audit = audit_cell_state_architecture_data(fixture)
    evaluation = evaluate_cell_state_architecture_fixture(fixture)
    replay = replay_cell_state_architecture_fixture(fixture)
    compliance = assess_cell_state_architecture_compliance(fixture)
    invariants = cell_state_architecture_invariants(fixture)
    metrics = cell_state_architecture_metrics(fixture, evaluation)
    matrix = build_cell_state_architecture_contract_matrix(fixture)
    lineage = build_cell_state_architecture_lineage(fixture)
    checks = {
        "typed_fixture": validate_cell_state_architecture_fixture(fixture),
        "data_audit": audit.accepted,
        "evaluation": evaluation.accepted,
        "replay": replay.accepted,
        "compliance": compliance["accepted"],
        "invariants": all(invariants.values()),
        "metric_invariants": not metric_invariants(metrics),
        "contract_matrix": contract_matrix_is_closed(fixture),
        "lineage_gaps": not lineage_gaps(fixture),
    }
    report = {
        "fixture_id": fixture.fixture_id,
        "checks": checks,
        "accepted": all(checks.values()),
        "audit_address": audit.content_address,
        "evaluation_address": evaluation.content_address,
        "replay_address": replay.content_address,
        "lineage_address": lineage["content_address"],
        "matrix_count": len(matrix),
        "metrics": metrics,
    }
    return report | {"content_address": addressed(report, "cell-state-deep-audit")}


__all__ = ["deep_audit_cell_state_architecture"]
