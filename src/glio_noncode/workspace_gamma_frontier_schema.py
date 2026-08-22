"""Field-level schema manifest for collaboration frontier records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_gamma_frontier_public_data import GammaFrontierOperation


@dataclass(frozen=True, slots=True)
class GammaFrontierFieldSpec:
    """One typed field declaration with review-facing meaning."""

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
class GammaFrontierOperationSchema:
    """Schema and stable output order for one operation."""

    operation: GammaFrontierOperation
    version: str
    fields: tuple[GammaFrontierFieldSpec, ...]
    output_order: tuple[str, ...]
    content_address: str

    def field(self, name: str) -> GammaFrontierFieldSpec:
        return next(item for item in self.fields if item.name == name)

    def required_fields(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields if item.required)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"required_fields": list(self.required_fields())}


@dataclass(frozen=True, slots=True)
class GammaFrontierSchemaManifest:
    """Complete schema used by contract, API, and release checks."""

    version: str
    operations: tuple[GammaFrontierOperationSchema, ...]
    state_values: tuple[str, ...]
    boundary: str
    content_address: str

    def by_operation(self, operation: GammaFrontierOperation) -> GammaFrontierOperationSchema:
        return next(item for item in self.operations if item.operation is operation)

    def field_names(self) -> tuple[str, ...]:
        return tuple(sorted({field.name for item in self.operations for field in item.fields}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"field_names": list(self.field_names())}


def _field(
    operation: GammaFrontierOperation,
    name: str,
    value_type: str,
    required: bool,
    nullable: bool,
    repeated: bool,
    description: str,
    allowed_values: tuple[str, ...] = (),
) -> GammaFrontierFieldSpec:
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
    return GammaFrontierFieldSpec(**body, content_address=content_hash(body))


def _schema(
    operation: GammaFrontierOperation,
    fields: tuple[GammaFrontierFieldSpec, ...],
    output_order: tuple[str, ...],
) -> GammaFrontierOperationSchema:
    body = {
        "operation": operation,
        "version": "2026.08.d15.c09-c12.v1",
        "fields": fields,
        "output_order": output_order,
    }
    return GammaFrontierOperationSchema(**body, content_address=content_hash(body))


def default_gamma_frontier_schema() -> GammaFrontierSchemaManifest:
    """Build a complete, explicit schema with no hidden fields."""

    context = ("context_key", "string", True, False, False, "exact six-part research context")
    board = (
        _field(GammaFrontierOperation.EXPERIMENT_BOARD, *context),
        _field(
            GammaFrontierOperation.EXPERIMENT_BOARD,
            "cards",
            "object",
            True,
            False,
            True,
            "declared experiment cards",
        ),
        _field(
            GammaFrontierOperation.EXPERIMENT_BOARD,
            "columns",
            "object",
            True,
            False,
            True,
            "accessible board columns",
        ),
        _field(
            GammaFrontierOperation.EXPERIMENT_BOARD,
            "dependency_edges",
            "object",
            True,
            False,
            True,
            "declared card dependencies",
        ),
        _field(
            GammaFrontierOperation.EXPERIMENT_BOARD,
            "blocked_card_ids",
            "string",
            True,
            False,
            True,
            "blocked card IDs",
        ),
        _field(
            GammaFrontierOperation.EXPERIMENT_BOARD,
            "issues",
            "string",
            True,
            False,
            True,
            "retained issue codes",
        ),
    )
    launch = (
        _field(GammaFrontierOperation.LAUNCH_PLAN, *context),
        _field(
            GammaFrontierOperation.LAUNCH_PLAN,
            "requests",
            "object",
            True,
            False,
            True,
            "declarative launch requests",
        ),
        _field(
            GammaFrontierOperation.LAUNCH_PLAN,
            "launches",
            "object",
            True,
            False,
            True,
            "bounded launch descriptors",
        ),
        _field(
            GammaFrontierOperation.LAUNCH_PLAN,
            "parameter_hash",
            "string",
            False,
            False,
            False,
            "canonical parameter address",
        ),
        _field(
            GammaFrontierOperation.LAUNCH_PLAN,
            "network_policy",
            "enum",
            True,
            False,
            False,
            "network review status",
        ),
        _field(
            GammaFrontierOperation.LAUNCH_PLAN,
            "issues",
            "string",
            True,
            False,
            True,
            "retained issue codes",
        ),
    )
    snapshot = (
        _field(GammaFrontierOperation.SHAREABLE_SNAPSHOT, *context),
        _field(
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            "snapshot_payload",
            "object",
            True,
            False,
            False,
            "portable aggregate payload",
        ),
        _field(
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            "snapshot_id",
            "string",
            True,
            False,
            False,
            "snapshot identifier",
        ),
        _field(
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            "signature_valid",
            "boolean",
            True,
            False,
            False,
            "HMAC result",
        ),
        _field(
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            "payload_hash_valid",
            "boolean",
            True,
            False,
            False,
            "payload address result",
        ),
        _field(
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            "expired",
            "boolean",
            True,
            False,
            False,
            "expiry result",
        ),
    )
    access = (
        _field(
            GammaFrontierOperation.COLLABORATION_ACCESS,
            "workspace_id",
            "string",
            True,
            False,
            False,
            "workspace identifier",
        ),
        _field(GammaFrontierOperation.COLLABORATION_ACCESS, *context),
        _field(
            GammaFrontierOperation.COLLABORATION_ACCESS,
            "members",
            "object",
            True,
            False,
            True,
            "role roster",
        ),
        _field(
            GammaFrontierOperation.COLLABORATION_ACCESS,
            "requests",
            "object",
            True,
            False,
            True,
            "requested actions",
        ),
        _field(
            GammaFrontierOperation.COLLABORATION_ACCESS,
            "decisions",
            "object",
            True,
            False,
            True,
            "policy decisions",
        ),
        _field(
            GammaFrontierOperation.COLLABORATION_ACCESS,
            "policy_receipt",
            "string",
            True,
            False,
            True,
            "decision receipt addresses",
        ),
    )
    operations = (
        _schema(
            GammaFrontierOperation.EXPERIMENT_BOARD,
            board,
            ("context_key", "cards", "columns", "dependency_edges", "blocked_card_ids", "issues"),
        ),
        _schema(
            GammaFrontierOperation.LAUNCH_PLAN,
            launch,
            ("context_key", "launches", "network_policy", "issues"),
        ),
        _schema(
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            snapshot,
            (
                "context_key",
                "snapshot_id",
                "signature_valid",
                "payload_hash_valid",
                "expired",
                "state",
            ),
        ),
        _schema(
            GammaFrontierOperation.COLLABORATION_ACCESS,
            access,
            ("workspace_id", "context_key", "decisions", "policy_receipt", "state", "issues"),
        ),
    )
    body = {
        "version": "2026.08.d15.c09-c12.v1",
        "operations": operations,
        "state_values": (
            "ready_for_review",
            "review_required",
            "partial",
            "blocked",
            "out_of_domain",
            "abstained",
            "allowed",
            "denied",
            "verified",
            "expired",
        ),
        "boundary": "public_aggregate_non_patient",
    }
    return GammaFrontierSchemaManifest(**body, content_address=content_hash(body))


__all__ = [
    "GammaFrontierFieldSpec",
    "GammaFrontierOperationSchema",
    "GammaFrontierSchemaManifest",
    "default_gamma_frontier_schema",
]
