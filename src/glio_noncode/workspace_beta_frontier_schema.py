"""Field-level schema manifest for the C05-C08 projection package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_public_data import BetaFrontierOperation


@dataclass(frozen=True, slots=True)
class BetaFrontierFieldSpec:
    """Schema field with type, presence, and boundary notes."""

    field_id: str
    name: str
    value_type: str
    required: bool
    nullable: bool
    repeated: bool
    description: str
    allowed_values: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("field_id", "name", "value_type", "description", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierOperationSchema:
    """Schema slice for one operation."""

    operation: BetaFrontierOperation
    version: str
    fields: tuple[BetaFrontierFieldSpec, ...]
    output_order: tuple[str, ...]
    content_address: str

    def field(self, name: str) -> BetaFrontierFieldSpec:
        return next(item for item in self.fields if item.name == name)

    def required_fields(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields if item.required)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"required_fields": list(self.required_fields())}


@dataclass(frozen=True, slots=True)
class BetaFrontierSchemaManifest:
    """Complete schema manifest used by quality and release checks."""

    version: str
    operations: tuple[BetaFrontierOperationSchema, ...]
    state_values: tuple[str, ...]
    boundary: str
    content_address: str

    def by_operation(self, operation: BetaFrontierOperation) -> BetaFrontierOperationSchema:
        return next(item for item in self.operations if item.operation is operation)

    def field_names(self) -> tuple[str, ...]:
        return tuple(sorted({field.name for item in self.operations for field in item.fields}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"field_names": list(self.field_names())}


def _field(
    operation: BetaFrontierOperation,
    name: str,
    value_type: str,
    required: bool,
    nullable: bool,
    repeated: bool,
    description: str,
    allowed_values: tuple[str, ...] = (),
) -> BetaFrontierFieldSpec:
    body = {
        "field_id": f"{operation.value}:{name}",
        "name": name,
        "value_type": value_type,
        "required": required,
        "nullable": nullable,
        "repeated": repeated,
        "description": description,
        "allowed_values": allowed_values,
    }
    return BetaFrontierFieldSpec(**body, content_address=content_hash(body))


def _operation_schema(operation: BetaFrontierOperation, fields: tuple[BetaFrontierFieldSpec, ...], output_order: tuple[str, ...]) -> BetaFrontierOperationSchema:
    body = {"operation": operation, "version": "2026.08.d15.c05-c08.v1", "fields": fields, "output_order": output_order}
    return BetaFrontierOperationSchema(**body, content_address=content_hash(body))


def default_beta_frontier_schema() -> BetaFrontierSchemaManifest:
    """Return the deterministic field manifest used by the package."""

    text = ("string", True, False, False)
    shared = (
        _field(BetaFrontierOperation.TOPOLOGY_VIEWPORT, "context_key", *text, "exact six-part research context"),
        _field(BetaFrontierOperation.TOPOLOGY_VIEWPORT, "state", "enum", True, False, False, "projection state", ("supported", "partial", "absent", "out_of_domain", "invalid")),
    )
    topology_fields = shared + (
        _field(BetaFrontierOperation.TOPOLOGY_VIEWPORT, "nodes", "object", True, False, True, "renderable topology nodes"),
        _field(BetaFrontierOperation.TOPOLOGY_VIEWPORT, "edges", "object", True, False, True, "renderable topology edges"),
        _field(BetaFrontierOperation.TOPOLOGY_VIEWPORT, "focus", "object", True, False, False, "bounded focus interval"),
        _field(BetaFrontierOperation.TOPOLOGY_VIEWPORT, "warnings", "string", True, False, True, "context and research boundary warnings"),
    )
    causal_fields = (
        _field(BetaFrontierOperation.CAUSAL_CHAIN, "context_key", *text, "exact six-part research context"),
        _field(BetaFrontierOperation.CAUSAL_CHAIN, "results", "object", True, False, True, "typed mediator results"),
        _field(BetaFrontierOperation.CAUSAL_CHAIN, "state", "enum", True, False, False, "chain completeness state"),
        _field(BetaFrontierOperation.CAUSAL_CHAIN, "missing_mediator_kinds", "enum", True, False, True, "required kinds not observed"),
        _field(BetaFrontierOperation.CAUSAL_CHAIN, "alternative_edge_ids", "string", True, False, True, "alternative paths retained"),
        _field(BetaFrontierOperation.CAUSAL_CHAIN, "warnings", "string", True, False, True, "negative and missing evidence notes"),
    )
    posterior_fields = (
        _field(BetaFrontierOperation.POSTERIOR_DECOMPOSITION, "context_key", *text, "exact six-part research context"),
        _field(BetaFrontierOperation.POSTERIOR_DECOMPOSITION, "hypothesis_id", *text, "declared hypothesis identifier"),
        _field(BetaFrontierOperation.POSTERIOR_DECOMPOSITION, "declared_prior", "number", True, False, False, "declared prior proxy"),
        _field(BetaFrontierOperation.POSTERIOR_DECOMPOSITION, "evidence_support", "number", True, True, False, "declared support or missing"),
        _field(BetaFrontierOperation.POSTERIOR_DECOMPOSITION, "components", "object", True, False, True, "exact-context contributions"),
        _field(BetaFrontierOperation.POSTERIOR_DECOMPOSITION, "residual", "number", True, True, False, "unexplained support"),
        _field(BetaFrontierOperation.POSTERIOR_DECOMPOSITION, "normalized_shares", "number", True, False, False, "absolute contribution shares"),
        _field(BetaFrontierOperation.POSTERIOR_DECOMPOSITION, "calibration_status", *text, "calibration declaration"),
    )
    table_fields = (
        _field(BetaFrontierOperation.EVIDENCE_TABLE, "context_key", *text, "exact workspace context"),
        _field(BetaFrontierOperation.EVIDENCE_TABLE, "workspace_id", *text, "source workspace identifier"),
        _field(BetaFrontierOperation.EVIDENCE_TABLE, "filter", "object", True, False, False, "typed table filter"),
        _field(BetaFrontierOperation.EVIDENCE_TABLE, "rows", "object", True, False, True, "paged evidence rows"),
        _field(BetaFrontierOperation.EVIDENCE_TABLE, "total_matches", "integer", True, False, False, "pre-pagination match count"),
        _field(BetaFrontierOperation.EVIDENCE_TABLE, "facets", "object", True, False, False, "pre-pagination dimension counts"),
        _field(BetaFrontierOperation.EVIDENCE_TABLE, "warnings", "string", True, False, True, "filter and unresolved-state notes"),
    )
    operations = (
        _operation_schema(BetaFrontierOperation.TOPOLOGY_VIEWPORT, topology_fields, ("context_key", "nodes", "edges", "state", "focus", "warnings")),
        _operation_schema(BetaFrontierOperation.CAUSAL_CHAIN, causal_fields, ("context_key", "nodes", "edges", "state", "missing_mediator_kinds", "warnings")),
        _operation_schema(BetaFrontierOperation.POSTERIOR_DECOMPOSITION, posterior_fields, ("context_key", "hypothesis_id", "components", "residual", "warnings")),
        _operation_schema(BetaFrontierOperation.EVIDENCE_TABLE, table_fields, ("workspace_id", "filter", "rows", "total_matches", "facets", "warnings")),
    )
    body = {"version": "2026.08.d15.c05-c08.v1", "operations": operations, "state_values": ("supported", "partial", "complete", "incomplete", "absent", "abstained", "out_of_domain", "contradictory", "invalid"), "boundary": "public_aggregate_non_patient"}
    return BetaFrontierSchemaManifest(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierFieldSpec", "BetaFrontierOperationSchema", "BetaFrontierSchemaManifest", "default_beta_frontier_schema"]
