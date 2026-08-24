"""Machine-readable field manifest for the D01 boundary."""

from __future__ import annotations

from .intake_architecture_contracts import (
    INTAKE_ARCHITECTURE_VERSION,
    IntakeArchitectureSchemaField,
    IntakeArchitectureSchemaManifest,
    addressed,
)

_FIELDS = (
    ("fixture_id", "string", True, "public_aggregate", "Stable fixture identifier."),
    ("operation_id", "string", True, "public_aggregate", "Closed D01 operation identifier."),
    ("capability_id", "string", True, "public_aggregate", "Blueprint capability join."),
    ("context_key", "string", True, "public_aggregate", "Exact reference context used for gating."),
    ("source_ids", "array[string]", True, "public_aggregate", "HTTPS source receipt joins."),
    ("public_identifier", "string", True, "public_aggregate", "External public identifier only."),
    ("payload", "object", True, "public_aggregate", "Bounded non-subject input projection."),
    ("expected_state", "enum", True, "public_aggregate", "Fixture control expectation."),
    ("issue_codes", "array[string]", True, "public_aggregate", "Review or quarantine reasons."),
    ("content_address", "string", True, "public_aggregate", "Deterministic receipt address."),
    ("rollback_version", "string", True, "public_aggregate", "Release recovery pointer."),
    (
        "delegate_context_key",
        "string",
        True,
        "public_aggregate",
        "Canonical context used by control cases for safe comparison.",
    ),
    (
        "evaluation_check_id",
        "string",
        True,
        "public_aggregate",
        "Addressable case or fixture evaluation check.",
    ),
    ("stage_id", "string", True, "public_aggregate", "Ordered runtime stage identifier."),
    ("stage_state", "enum", True, "public_aggregate", "Runtime stage acceptance or review state."),
    (
        "compliance_check_id",
        "string",
        True,
        "public_aggregate",
        "Public-boundary compliance check identifier.",
    ),
    (
        "source_transport",
        "enum",
        True,
        "public_aggregate",
        "HTTPS transport requirement for public receipts.",
    ),
    (
        "claim_boundary",
        "string",
        True,
        "public_aggregate",
        "Explicit statement of what the intake output does not claim.",
    ),
)


def default_intake_architecture_schema() -> IntakeArchitectureSchemaManifest:
    fields = []
    for field_id, type_name, required, privacy_scope, description in _FIELDS:
        body = {
            "field_id": field_id,
            "type_name": type_name,
            "required": required,
            "privacy_scope": privacy_scope,
            "description": description,
        }
        fields.append(
            IntakeArchitectureSchemaField(
                **body, content_address=addressed(body, "intake-schema-field")
            )
        )
    body = {
        "schema_id": "intake-architecture-d01",
        "version": INTAKE_ARCHITECTURE_VERSION,
        "fields": tuple(fields),
        "accepted": all(field.privacy_scope == "public_aggregate" for field in fields),
    }
    return IntakeArchitectureSchemaManifest(
        **body, content_address=addressed(body, "intake-schema")
    )


def validate_intake_architecture_schema(
    schema: IntakeArchitectureSchemaManifest | None = None,
) -> tuple[str, ...]:
    value = schema or default_intake_architecture_schema()
    issues = []
    if value.version != INTAKE_ARCHITECTURE_VERSION:
        issues.append("schema_version")
    if len(value.fields) != len(_FIELDS):
        issues.append("field_count")
    if any(field.privacy_scope != "public_aggregate" for field in value.fields):
        issues.append("privacy_scope")
    if len({field.field_id for field in value.fields}) != len(value.fields):
        issues.append("field_ids")
    return tuple(sorted(set(issues)))


__all__ = ["default_intake_architecture_schema", "validate_intake_architecture_schema"]
