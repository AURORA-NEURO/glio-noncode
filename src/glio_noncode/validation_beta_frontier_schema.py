"""Closed field schema and projection checks for validation-beta outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable
from .validation_beta_frontier_contracts import default_validation_beta_frontier_contracts
from .validation_beta_frontier_public_data import ValidationBetaFrontierOperation


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierField:
    name: str
    value_kind: str
    required: bool
    description: str
    sensitive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierSchemaOperation:
    operation: ValidationBetaFrontierOperation
    input_fields: tuple[ValidationBetaFrontierField, ...]
    output_fields: tuple[ValidationBetaFrontierField, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierSchemaReport:
    version: str
    operations: tuple[ValidationBetaFrontierSchemaOperation, ...]
    accepted: bool
    content_address: str

    def operation(self, value: ValidationBetaFrontierOperation | str) -> ValidationBetaFrontierSchemaOperation:
        selected = value.value if isinstance(value, ValidationBetaFrontierOperation) else str(value)
        for item in self.operations:
            if item.operation.value == selected:
                return item
        raise KeyError(selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _field(name: str, kind: str, required: bool, description: str, sensitive: bool = False) -> ValidationBetaFrontierField:
    return ValidationBetaFrontierField(name, kind, required, description, sensitive)


def default_validation_beta_frontier_schema() -> ValidationBetaFrontierSchemaReport:
    """Build the public schema from the operation contracts."""

    common_outputs = (
        _field("state", "enum", True, "declared research-planning state"),
        _field("warnings", "array[string]", True, "limitations and review boundaries"),
        _field("content_address", "sha256", True, "content address of the operation result"),
    )
    operation_fields: dict[ValidationBetaFrontierOperation, tuple[tuple[ValidationBetaFrontierField, ...], tuple[ValidationBetaFrontierField, ...]]] = {
        ValidationBetaFrontierOperation.CRISPR_DESIGN: (
            (_field("targets", "array[target]", True, "context-qualified sequence targets"), _field("modes", "array[enum]", True, "CRISPRi and CRISPRa design modes"), _field("constraints", "object", True, "guide and control constraints")),
            common_outputs + (_field("modes", "object", True, "CRISPRi and CRISPRa packages"), _field("target_ids", "array[string]", True, "target identity projection")),
        ),
        ValidationBetaFrontierOperation.BASE_EDITING: (
            (_field("targets", "array[target]", True, "single-base edit targets"), _field("constraints", "object", True, "editing-window constraints")),
            common_outputs + (_field("modes", "object", True, "base-editing packages"), _field("target_ids", "array[string]", True, "target identity projection")),
        ),
        ValidationBetaFrontierOperation.PRIME_EDITING: (
            (_field("targets", "array[target]", True, "prime-edit targets"), _field("constraints", "object", True, "PBS, RTT, and edit constraints")),
            common_outputs + (_field("modes", "object", True, "prime-editing packages"), _field("target_ids", "array[string]", True, "target identity projection")),
        ),
        ValidationBetaFrontierOperation.ALLELE_REPORTER: (
            (_field("targets", "array[target]", True, "paired reference and alternate targets"), _field("constraints", "object", True, "construct and control constraints")),
            common_outputs + (_field("modes", "object", True, "reporter package"), _field("target_ids", "array[string]", True, "target identity projection")),
        ),
        ValidationBetaFrontierOperation.MODEL_ELIGIBILITY: (
            (_field("observations", "array[eligibility]", True, "declared model observations"), _field("model_system", "string", True, "requested model system"), _field("minimum_evidence_strength", "number", True, "minimum evidence floor")),
            common_outputs + (_field("results", "array[eligibility-result]", True, "per-target gate results"), _field("issues", "array[issue]", True, "quarantined rows")),
        ),
        ValidationBetaFrontierOperation.GUIDE_OLIGO: (
            (_field("source_id", "string", True, "design source identifier"), _field("source_version", "string", True, "design source version"), _field("input_format", "enum", True, "TSV or JSON input mode"), _field("text", "string", True, "public aggregate input text", True)),
            common_outputs + (_field("observations", "array[oligo]", True, "lossless sequence observations"), _field("issues", "array[issue]", True, "quarantined rows")),
        ),
        ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION: (
            (_field("targets", "array[target-ref]", True, "target assignment rows"), _field("plan_id", "string", True, "plan identifier"), _field("control_types", "array[enum]", True, "control categories"), _field("biological_replicates", "integer", True, "biological replicate count"), _field("technical_replicates", "integer", True, "technical replicate count"), _field("randomization_seed", "string", True, "deterministic seed")),
            common_outputs + (_field("assignments", "array[assignment]", True, "content-addressed assignments"), _field("target_ids", "array[string]", True, "target identity projection"), _field("blockers", "array[string]", True, "planning blockers")),
        ),
        ValidationBetaFrontierOperation.POWER_REPLICATION: (
            (_field("observations", "array[power-observation]", True, "effect, variance, alpha, and replicate inputs"),),
            common_outputs + (_field("results", "array[power-estimate]", True, "transparent replicate estimates"), _field("issues", "array[issue]", True, "quarantined observations")),
        ),
    }
    operations: list[ValidationBetaFrontierSchemaOperation] = []
    contracts = default_validation_beta_frontier_contracts()
    for operation in ValidationBetaFrontierOperation:
        inputs, outputs = operation_fields[operation]
        contract = contracts.for_operation(operation)
        declared_inputs = {item.name for item in inputs}
        declared_outputs = {item.name for item in outputs}
        if set(contract.input_fields) != declared_inputs or not set(contract.output_fields).issubset(declared_outputs):
            raise ValueError(f"schema and contract diverge for {operation.value}")
        body = {"operation": operation, "input_fields": inputs, "output_fields": outputs}
        operations.append(ValidationBetaFrontierSchemaOperation(**body, content_address=content_hash(body, prefix="validation-beta-schema-operation")))
    body = {"version": "2026.08.d13-c05-c12.schema.v1", "operations": tuple(operations), "accepted": len(operations) == 8}
    return ValidationBetaFrontierSchemaReport(**body, content_address=content_hash(body, prefix="validation-beta-schema"))


def validate_validation_beta_frontier_output(
    operation: ValidationBetaFrontierOperation | str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate required output keys and reject undeclared sensitive projection."""

    schema = default_validation_beta_frontier_schema()
    selected = schema.operation(operation)
    missing = tuple(item.name for item in selected.output_fields if item.required and item.name not in payload)
    sensitive = tuple(item.name for item in selected.output_fields if item.sensitive and item.name in payload)
    body = {"operation": selected.operation, "valid": not missing, "missing_fields": missing, "sensitive_projection_fields": sensitive}
    return body | {"content_address": content_hash(body, prefix="validation-beta-output-validation")}


__all__ = [
    "ValidationBetaFrontierField",
    "ValidationBetaFrontierSchemaOperation",
    "ValidationBetaFrontierSchemaReport",
    "default_validation_beta_frontier_schema",
    "validate_validation_beta_frontier_output",
]
