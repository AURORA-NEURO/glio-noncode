"""Locked operation field dictionary for the alpha aggregate envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierFieldDefinition:
    operation: str
    field_name: str
    field_type: str
    required: bool
    unit: str
    description: str
    source_rule: str
    output_rule: str
    missingness_rule: str
    review_trigger: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierDataDictionary:
    fields: tuple[TopologyAlphaFrontierFieldDefinition, ...]
    operation_count: int
    field_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str | TopologyAlphaFrontierOperation) -> tuple[TopologyAlphaFrontierFieldDefinition, ...]:
        value = operation.value if isinstance(operation, TopologyAlphaFrontierOperation) else str(operation)
        return tuple(item for item in self.fields if item.operation == value)

    def field(self, operation: str, field_name: str) -> TopologyAlphaFrontierFieldDefinition:
        for item in self.for_operation(operation):
            if item.field_name == field_name:
                return item
        raise KeyError((operation, field_name))

    def required_fields(self, operation: str) -> tuple[str, ...]:
        return tuple(item.field_name for item in self.for_operation(operation) if item.required)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fields": [item.to_dict() for item in self.fields], "operation_count": self.operation_count, "field_count": self.field_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _field(operation: str, name: str, field_type: str, description: str, source_rule: str, output_rule: str, *, unit: str = "none", required: bool = True, review_trigger: str = "missing or contradictory input") -> TopologyAlphaFrontierFieldDefinition:
    return TopologyAlphaFrontierFieldDefinition(operation, name, field_type, required, unit, description, source_rule, output_rule, "retain explicit missingness" if required else "null is permitted", review_trigger)


def build_topology_alpha_frontier_data_dictionary() -> TopologyAlphaFrontierDataDictionary:
    c09, c10, c11, c12 = (item.value for item in TopologyAlphaFrontierOperation)
    fields = (
        _field(c09, "boundary_id", "string", "Stable boundary identity.", "source row identity", "copy to result"),
        _field(c09, "side", "enum", "Left or right boundary side.", "declared side", "retain side labels"),
        _field(c09, "motif_id", "string", "Stable motif observation identity.", "source row identity", "retain observation receipt"),
        _field(c09, "orientation", "enum", "Motif strand orientation.", "declared strand", "derive relationship label"),
        _field(c09, "score", "number", "Motif evidence score.", "declared numeric score", "apply minimum score"),
        _field(c09, "context_key", "string", "Exact biological context.", "source context", "gate transport"),
        _field(c10, "variant_id", "string", "Stable variant identity.", "source row identity", "copy to result"),
        _field(c10, "reference_ctcf", "number", "Reference CTCF channel.", "declared channel", "compute CTCF delta"),
        _field(c10, "alternate_ctcf", "number", "Alternate CTCF channel.", "declared channel", "compute CTCF delta"),
        _field(c10, "reference_cohesin", "number", "Reference cohesin channel.", "declared channel", "compute cohesin delta", required=False, review_trigger="cohesin channel is absent"),
        _field(c10, "alternate_cohesin", "number", "Alternate cohesin channel.", "declared channel", "compute cohesin delta", required=False, review_trigger="cohesin channel is absent"),
        _field(c10, "context_key", "string", "Exact biological context.", "source context", "gate transport"),
        _field(c11, "region_id", "string", "Stable insulator region identity.", "source row identity", "copy to result"),
        _field(c11, "molecular_state", "enum", "IDH mutant or wildtype state.", "controlled vocabulary", "pair state rows"),
        _field(c11, "insulator_score", "number", "Insulator measurement.", "declared numeric score", "compute state delta"),
        _field(c11, "methylation_fraction", "number", "Methylation measurement.", "declared bounded fraction", "retain separate channel", unit="fraction"),
        _field(c11, "context_key", "string", "Exact biological context.", "source context", "gate transport"),
        _field(c12, "sv_id", "string", "Stable structural event identity.", "source row identity", "copy to result"),
        _field(c12, "sv_kind", "enum", "Structural event kind.", "controlled vocabulary", "retain event label"),
        _field(c12, "deleted_edge_ids", "array", "Declared contact edges to remove.", "event edit set", "compute lost edges", required=False, review_trigger="edge set is absent or unresolved"),
        _field(c12, "gained_edge_ids", "array", "Declared contact edges to add.", "event edit set", "compute gained edges", required=False, review_trigger="edge set is absent"),
        _field(c12, "rewired_edge_ids", "array", "Declared contact edges to mark rewired.", "event edit set", "compute rewired edges", required=False, review_trigger="edge set is absent"),
        _field(c12, "affected_node_ids", "array", "Nodes named by the event.", "event node set", "copy to result"),
        _field(c12, "context_key", "string", "Exact biological context.", "source context", "gate transport"),
    )
    return TopologyAlphaFrontierDataDictionary(fields, len(set(item.operation for item in fields)), len(fields), len(set(item.operation for item in fields)) == 4 and len(fields) == 24)


__all__ = ["TopologyAlphaFrontierDataDictionary", "TopologyAlphaFrontierFieldDefinition", "build_topology_alpha_frontier_data_dictionary"]
