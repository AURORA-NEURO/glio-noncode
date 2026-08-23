"""Field dictionary and permitted values for D08 public interchange."""

from __future__ import annotations

from .cell_state_architecture_contracts import (
    CellStateArchitectureFamily,
    CellStateArchitectureOperation,
    CellStateArchitecturePlane,
    CellStateArchitectureScenario,
)


def cell_state_architecture_data_dictionary() -> dict[str, object]:
    return {
        "fixture_id": {
            "type": "string",
            "required": True,
            "meaning": "stable aggregate fixture identity",
        },
        "version": {"type": "string", "required": True, "meaning": "pinned D08 contract revision"},
        "boundary": {"type": "string", "required": True, "meaning": "public aggregate boundary"},
        "context_key": {
            "type": "string",
            "required": True,
            "meaning": "reference, disease, age, state, territory, recurrence context",
        },
        "source_ids": {
            "type": "array[string]",
            "required": True,
            "meaning": "public receipts joined to an operation or case",
        },
        "operation": {
            "type": "enum",
            "required": True,
            "values": [item.value for item in CellStateArchitectureOperation],
        },
        "family": {
            "type": "enum",
            "required": True,
            "values": [item.value for item in CellStateArchitectureFamily],
        },
        "plane": {
            "type": "enum",
            "required": True,
            "values": [item.value for item in CellStateArchitecturePlane],
        },
        "scenario": {
            "type": "enum",
            "required": True,
            "values": [item.value for item in CellStateArchitectureScenario],
        },
        "expected_counts": {
            "type": "object[string,integer]",
            "required": True,
            "meaning": "conserved primary and secondary receipt counts",
        },
        "content_address": {
            "type": "sha256 string",
            "required": True,
            "meaning": "immutable receipt address",
        },
    }


def required_d08_fields() -> tuple[str, ...]:
    return tuple(cell_state_architecture_data_dictionary())


__all__ = ["cell_state_architecture_data_dictionary", "required_d08_fields"]
