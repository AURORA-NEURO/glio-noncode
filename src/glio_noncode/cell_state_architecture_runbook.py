"""Operational runbook and module inventory for D08."""

from __future__ import annotations

from .cell_state_architecture_contracts import CellStateArchitectureFixture
from .cell_state_architecture_runtime import D08_STAGE_IDS


def cell_state_architecture_runbook(
    fixture: CellStateArchitectureFixture,
) -> tuple[dict[str, object], ...]:
    operations = tuple(sorted(fixture.operations, key=lambda item: item.ordinal))
    rows: list[dict[str, object]] = []
    for operation in operations:
        rows.append(
            {
                "ordinal": operation.ordinal,
                "operation_id": operation.operation_id,
                "capability_id": operation.capability_id,
                "operation": operation.operation.value,
                "family": operation.family.value,
                "plane": operation.plane.value,
                "dependencies": list(operation.dependencies),
                "control_policy": operation.control_policy,
                "verification": (
                    f"run the four cases for {operation.operation_id} and require "
                    "one positive plus three controls"
                ),
            }
        )
    return tuple(rows)


def cell_state_architecture_stage_runbook() -> tuple[dict[str, object], ...]:
    return tuple(
        {"ordinal": index, "stage_id": stage_id, "required_state": "accepted"}
        for index, stage_id in enumerate(D08_STAGE_IDS, start=1)
    )


def module_inventory() -> tuple[str, ...]:
    return (
        "contracts",
        "public_data",
        "operations",
        "schema",
        "plan",
        "policy",
        "review",
        "lineage",
        "metrics",
        "observability",
        "normalization",
        "invariants",
        "failures",
        "ledger",
        "artifacts",
        "release",
        "bundle",
        "access",
        "replay",
        "depth",
        "quality",
        "runtime",
        "query",
        "source_registry",
        "data_dictionary",
        "scenarios",
        "reporting",
        "runbook",
        "exports",
    )


__all__ = [
    "cell_state_architecture_runbook",
    "cell_state_architecture_stage_runbook",
    "module_inventory",
]
