"""Cross-module invariants for D08 source, case, and release consistency."""

from __future__ import annotations

from .cell_state_architecture_contracts import (
    CellStateArchitectureFixture,
    CellStateArchitectureRuntime,
)


def cell_state_architecture_invariants(
    fixture: CellStateArchitectureFixture, runtime: CellStateArchitectureRuntime | None = None
) -> dict[str, bool]:
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    values = {
        "source_count": len(fixture.sources) == 18,
        "operation_count": len(fixture.operations) == 16,
        "case_count": len(fixture.cases) == 64,
        "source_join": all(
            set(item.source_ids) <= source_ids for item in (*fixture.operations, *fixture.cases)
        ),
        "operation_join": all(item.operation_id in operation_ids for item in fixture.cases),
        "operation_case_balance": all(
            sum(item.operation_id == op.operation_id for item in fixture.cases) == 4
            for op in fixture.operations
        ),
        "positive_control_balance": (len(fixture.positive_cases), len(fixture.control_cases))
        == (16, 48),
    }
    if runtime is not None:
        values |= {
            "audit_accepted": runtime.audit.accepted,
            "plan_accepted": runtime.plan.accepted,
            "evaluation_accepted": runtime.evaluation.accepted,
            "release_accepted": runtime.release.state.value == "published",
            "stage_count": len(runtime.stages) == 22,
        }
    return values


def failed_invariants(values: dict[str, bool]) -> tuple[str, ...]:
    return tuple(key for key, passed in values.items() if not passed)


__all__ = ["cell_state_architecture_invariants", "failed_invariants"]
