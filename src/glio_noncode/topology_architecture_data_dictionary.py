"""D09 field dictionary for public aggregate topology data."""

from __future__ import annotations

from .topology_architecture_contracts import (
    TopologyArchitectureFamily,
    TopologyArchitectureOperation,
    TopologyArchitecturePlane,
    TopologyArchitectureScenario,
)


def topology_architecture_data_dictionary() -> dict[str, object]:
    return {
        "fixture_id": {"type": "string", "required": True},
        "version": {"type": "string", "required": True},
        "boundary": {"type": "string", "required": True},
        "context_key": {"type": "string", "required": True},
        "source_ids": {"type": "array[string]", "required": True},
        "operation": {
            "type": "enum",
            "values": [item.value for item in TopologyArchitectureOperation],
        },
        "family": {"type": "enum", "values": [item.value for item in TopologyArchitectureFamily]},
        "plane": {"type": "enum", "values": [item.value for item in TopologyArchitecturePlane]},
        "scenario": {
            "type": "enum",
            "values": [item.value for item in TopologyArchitectureScenario],
        },
        "expected_counts": {"type": "object[string,integer]", "required": True},
        "content_address": {"type": "sha256 string", "required": True},
    }


__all__ = ["topology_architecture_data_dictionary"]
