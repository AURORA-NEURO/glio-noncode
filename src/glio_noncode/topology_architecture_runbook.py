"""D09 operation and stage runbook."""

from __future__ import annotations

from .topology_architecture_contracts import TopologyArchitectureFixture
from .topology_architecture_runtime import TOPOLOGY_ARCHITECTURE_STAGE_IDS


def topology_architecture_runbook(
    fixture: TopologyArchitectureFixture,
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "ordinal": item.ordinal,
            "operation_id": item.operation_id,
            "operation": item.operation.value,
            "family": item.family.value,
            "plane": item.plane.value,
            "dependencies": list(item.dependencies),
            "source_count": len(item.source_ids),
            "verification": f"execute one positive and three control cases for {item.operation_id}",
        }
        for item in fixture.operations
    )


def topology_architecture_stage_runbook() -> tuple[dict[str, object], ...]:
    return tuple(
        {"ordinal": index, "stage_id": stage_id, "required_state": "accepted"}
        for index, stage_id in enumerate(TOPOLOGY_ARCHITECTURE_STAGE_IDS, start=1)
    )


def topology_architecture_module_inventory() -> tuple[str, ...]:
    return (
        "contracts",
        "public_data",
        "operations",
        "schema",
        "plan",
        "review",
        "lineage",
        "metrics",
        "ledger",
        "artifacts",
        "release",
        "replay",
        "depth",
        "quality",
        "runtime",
        "compliance",
        "reporting",
        "runbook",
        "exports",
    )


__all__ = [
    "topology_architecture_module_inventory",
    "topology_architecture_runbook",
    "topology_architecture_stage_runbook",
]
