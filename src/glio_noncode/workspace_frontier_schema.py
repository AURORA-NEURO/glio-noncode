"""Field-level schema manifest for Domain 15 workspace contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_public_data import WorkspaceFrontierOperation


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierFieldSpec:
    field_name: str
    value_type: str
    required: bool
    nullable: bool
    semantic_role: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierOperationSchema:
    operation: WorkspaceFrontierOperation
    fields: tuple[WorkspaceFrontierFieldSpec, ...]
    state_values: tuple[str, ...]
    boundary_notes: tuple[str, ...]
    content_address: str

    def field(self, field_name: str) -> WorkspaceFrontierFieldSpec:
        return next(item for item in self.fields if item.field_name == field_name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierSchemaManifest:
    version: str
    operations: tuple[WorkspaceFrontierOperationSchema, ...]
    content_address: str

    def fields(self) -> tuple[WorkspaceFrontierFieldSpec, ...]:
        return tuple(field for operation in self.operations for field in operation.fields)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"field_count": len(self.fields())}


def _field(name: str, value_type: str, required: bool, nullable: bool, role: str) -> WorkspaceFrontierFieldSpec:
    body = {"field_name": name, "value_type": value_type, "required": required, "nullable": nullable, "semantic_role": role}
    return WorkspaceFrontierFieldSpec(**body, content_address=content_hash(body))


def _operation(operation: WorkspaceFrontierOperation, specs: tuple[WorkspaceFrontierFieldSpec, ...], notes: tuple[str, ...]) -> WorkspaceFrontierOperationSchema:
    body = {"operation": operation, "fields": specs, "state_values": ("supported", "partial", "absent", "abstained", "out_of_domain", "invalid"), "boundary_notes": notes}
    return WorkspaceFrontierOperationSchema(**body, content_address=content_hash(body))


def default_workspace_frontier_schema() -> WorkspaceFrontierSchemaManifest:
    operations = (
        _operation(WorkspaceFrontierOperation.CASE_WORKSPACE, tuple(_field(*item) for item in (("case_id", "string", True, False, "case identity"), ("context_key", "context-key", True, False, "exact applicability"), ("variants", "array[variant]", True, False, "canonical variants"), ("candidate_elements", "array[element]", False, False, "candidate intervals"), ("section_ids", "array[string]", True, False, "accessible sections"), ("record_ids", "array[string]", True, False, "stable row identities"), ("facets", "object", True, False, "bounded filters"), ("warnings", "array[string]", True, False, "limitations"))), ("optional dossier sections remain incomplete without source data", "records never cross exact context")),
        _operation(WorkspaceFrontierOperation.COHORT_WORKSPACE, tuple(_field(*item) for item in (("evidence_id", "string", True, False, "evidence identity"), ("query_id", "string", True, False, "selection identity"), ("context_key", "context-key", True, False, "exact applicability"), ("records", "array[cohort-record]", True, False, "selected rows"), ("excluded_count", "integer", True, False, "selection accounting"), ("excluded_reasons", "object", True, False, "exclusion accounting"), ("section_ids", "array[string]", True, False, "accessible sections"), ("facets", "object", True, False, "bounded filters"))), ("callability is a selection criterion", "controls and backgrounds remain separate sections")),
        _operation(WorkspaceFrontierOperation.VARIANT_EXPLORER, tuple(_field(*item) for item in (("workspace_id", "string", True, False, "workspace identity"), ("variant_id", "string", True, False, "requested identity"), ("variant_record_id", "string", False, True, "resolved identity"), ("related_record_ids", "array[string]", True, False, "declared relationships"), ("related_by_type", "object", True, False, "typed relationship groups"), ("warnings", "array[string]", True, False, "limitations"))), ("absence is abstention", "nearby records are not inferred as related")),
        _operation(WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, tuple(_field(*item) for item in (("source_id", "string", True, False, "track source"), ("genome_build", "string", True, False, "coordinate build"), ("context_key", "context-key", True, False, "exact applicability"), ("feature_count", "integer", True, False, "parsed intervals"), ("issue_count", "integer", True, False, "parse accounting"), ("coordinate_labels", "array[string]", True, False, "interval display"), ("facets", "object", True, False, "bounded filters"), ("accessibility", "object", True, False, "accessible labels"))), ("overlap is annotation navigation", "parse issues remain attached to the batch")),
    )
    body = {"version": "2026.08.d15.v1", "operations": operations}
    return WorkspaceFrontierSchemaManifest(**body, content_address=content_hash(body))


__all__ = [
    "WorkspaceFrontierFieldSpec",
    "WorkspaceFrontierOperationSchema",
    "WorkspaceFrontierSchemaManifest",
    "default_workspace_frontier_schema",
]
